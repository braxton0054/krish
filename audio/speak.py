from piper import PiperVoice
import wave
import numpy as np
from config.settings import PIPER_VOICE, PIPER_CONFIG
from pathlib import Path

_voice: PiperVoice | None = None


def get_voice() -> PiperVoice:
    global _voice
    if _voice is None:
        voice_path = PIPER_VOICE
        config_path = PIPER_CONFIG
        if not Path(voice_path).exists():
            raise FileNotFoundError(
                f"Piper voice model not found at {voice_path}. "
                "Download from https://huggingface.co/rhasspy/piper-voices"
            )
        print(f"Loading Piper voice...")
        _voice = PiperVoice.load(voice_path, config_path=config_path, use_cuda=False)
    return _voice


def speak(text: str, output_path: str | None = None) -> str:
    voice = get_voice()
    path = output_path or str(Path(__file__).parent.parent / "temp" / "output.wav")

    chunks = list(voice.synthesize(text))
    if not chunks:
        raise RuntimeError("No audio generated")

    sr = chunks[0].sample_rate
    sw = chunks[0].sample_width
    sc = chunks[0].sample_channels
    audio = np.concatenate([c.audio_int16_array for c in chunks])

    with wave.open(path, "wb") as wf:
        wf.setnchannels(sc)
        wf.setsampwidth(sw)
        wf.setframerate(sr)
        wf.writeframes(audio.tobytes())

    return path
