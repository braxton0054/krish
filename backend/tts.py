import io
import logging
import numpy as np
import soundfile as sf

logger = logging.getLogger("krish.tts")


def _to_numpy(audio):
    if isinstance(audio, np.ndarray):
        return audio
    try:
        import torch
        if isinstance(audio, torch.Tensor):
            return audio.cpu().numpy()
    except ImportError:
        pass
    try:
        return np.array(audio)
    except Exception:
        return None

_pipeline = None

def get_tts_pipeline(config):
    global _pipeline
    if _pipeline is not None:
        return _pipeline

    tts_cfg = config.get("tts", {})
    lang_code = tts_cfg.get("lang_code", "a")

    logger.info(f"Loading Kokoro TTS pipeline (lang={lang_code})...")
    try:
        from kokoro import KPipeline
        _pipeline = KPipeline(lang_code=lang_code)
        logger.info("Kokoro TTS pipeline loaded.")
    except Exception as e:
        logger.warning(f"Failed to load Kokoro TTS: {e}. TTS will send text-only.")
        _pipeline = None
    return _pipeline


def synthesize(text: str, config: dict) -> bytes | None:
    pipeline = get_tts_pipeline(config)
    if pipeline is None:
        return None

    tts_cfg = config.get("tts", {})
    voice = tts_cfg.get("voice", "af_heart")
    speed = tts_cfg.get("speed", 1.0)

    try:
        generator = pipeline(text, voice=voice, speed=speed)
        audio_chunks = []
        sample_rate = 24000
        for gs, ps, audio in generator:
            arr = _to_numpy(audio)
            if arr is not None and arr.size > 0:
                audio_chunks.append(arr)

        if not audio_chunks:
            return None

        full_audio = np.concatenate(audio_chunks) if len(audio_chunks) > 1 else audio_chunks[0]

        buf = io.BytesIO()
        sf.write(buf, full_audio, samplerate=sample_rate or 24000, format="WAV")
        buf.seek(0)
        return buf.read()
    except Exception as e:
        logger.error(f"TTS synthesis failed: {e}")
        return None
