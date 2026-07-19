import asyncio
import logging
import struct
import time

import numpy as np

from stt import transcribe

logger = logging.getLogger("krish.wake_word")


def pcm_to_wav(pcm_int16: bytes, sample_rate: int = 16000) -> bytes:
    data_size = len(pcm_int16)
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,
        1,
        1,
        sample_rate,
        sample_rate * 2,
        2,
        16,
        b"data",
        data_size,
    )
    return header + pcm_int16


def pcm_energy(pcm_int16: bytes) -> float:
    data = np.frombuffer(pcm_int16, dtype=np.int16).astype(np.float32)
    return float(np.sqrt(np.mean(data ** 2)) / 32768.0)


class KeywordSpotter:
    """Local wake-word spotter using Faster-Whisper.

    Buffers PCM audio and periodically runs a small Whisper transcription
    to check for the configured keyword.  No cloud APIs, no extra models.
    """

    def __init__(self, config: dict):
        ww_cfg = config.get("wake_word", {})
        self.keyword = ww_cfg.get("keyword", "krish").lower()
        self.sensitivity = ww_cfg.get("sensitivity", 0.5)
        self.config = config
        self.last_check = 0.0
        self.check_interval = ww_cfg.get("check_interval_ms", 400) / 1000.0
        self.min_buffer_ms = ww_cfg.get("min_buffer_ms", 1000)
        self.min_samples = int(16000 * self.min_buffer_ms / 1000) * 2
        self._warmed = False

    def _matches(self, text: str) -> bool:
        lower = text.lower()
        if self.keyword in lower:
            return True
        for word in lower.split():
            word = word.strip(".,!?;:")
            if len(word) < 3:
                continue
            if word == self.keyword:
                return True
            if abs(len(word) - len(self.keyword)) > 2:
                continue
            if self._levenshtein(word, self.keyword) <= 2:
                return True
        return False

    @staticmethod
    def _levenshtein(a: str, b: str) -> int:
        m, n = len(a), len(b)
        dp = list(range(n + 1))
        for i in range(1, m + 1):
            prev = dp[0]
            dp[0] = i
            for j in range(1, n + 1):
                tmp = dp[j]
                dp[j] = min(
                    prev + (0 if a[i - 1] == b[j - 1] else 1),
                    dp[j] + 1,
                    dp[j - 1] + 1,
                )
                prev = tmp
        return dp[n]

    def check(self, pcm_bytes: bytes) -> bool:
        """Stateless check: transcribe the given PCM buffer and test for keyword."""
        if len(pcm_bytes) < self.min_samples:
            logger.debug(f"KW check: buffer too small ({len(pcm_bytes)} < {self.min_samples})")
            return False

        wav = pcm_to_wav(pcm_bytes)
        logger.info(f"KW check: transcribing {len(pcm_bytes)} bytes of PCM")

        # Debug dump: save first few checks to files
        import os
        dump_dir = "/tmp/kw_debug"
        os.makedirs(dump_dir, exist_ok=True)
        existing = len(os.listdir(dump_dir))
        if existing < 5:
            with open(f"{dump_dir}/kw_{existing:03d}.wav", "wb") as f:
                f.write(wav)
            logger.info(f"KW check: saved debug audio to {dump_dir}/kw_{existing:03d}.wav")

        try:
            text, _ = transcribe(wav, self.config)
        except Exception as e:
            logger.info(f"KW check: transcribe failed: {e}")
            return False

        text = text.strip()
        logger.info(f"KW check: whisper returned: {text!r}")

        if not text:
            return False

        if self._matches(text):
            logger.info(f"Wake word detected (fuzzy) in: {text!r}")
            return True

        logger.info(f"KW check: no match for keyword '{self.keyword}'")
        return False


class VAD:
    def __init__(self, threshold: float = 0.02, silence_ms: int = 1500, sample_rate: int = 16000):
        self.threshold = threshold
        self.silence_samples = int(sample_rate * silence_ms / 1000)
        self.sample_rate = sample_rate
        self.silent_count = 0

    def reset(self):
        self.silent_count = 0

    def feed(self, pcm_int16: bytes) -> bool:
        energy = pcm_energy(pcm_int16)
        if energy < self.threshold:
            self.silent_count += len(pcm_int16) // 2
        else:
            self.silent_count = 0
        return self.silent_count >= self.silence_samples


def is_available() -> bool:
    return True


def cleanup():
    pass
