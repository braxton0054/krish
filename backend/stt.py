import os
import tempfile
import logging

logger = logging.getLogger("krish.stt")

_model = None

def get_stt_model(config):
    global _model
    if _model is not None:
        return _model
    stt_cfg = config.get("stt", {})
    model_size = stt_cfg.get("model_size", "base")
    device = stt_cfg.get("device", "cpu")
    compute_type = stt_cfg.get("compute_type", "int8")
    logger.info(f"Loading Faster-Whisper model '{model_size}' on {device} ({compute_type})...")
    from faster_whisper import WhisperModel
    _model = WhisperModel(model_size, device=device, compute_type=compute_type)
    logger.info("Faster-Whisper model loaded.")
    return _model

def transcribe(audio_data: bytes, config: dict) -> tuple[str, float]:
    model = get_stt_model(config)
    stt_cfg = config.get("stt", {})
    suffix = ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(audio_data)
        tmp_path = tmp.name
    try:
        segments, info = model.transcribe(
            tmp_path,
            beam_size=stt_cfg.get("beam_size", 5),
            language=stt_cfg.get("language"),
        )
        text_parts = []
        for seg in segments:
            text_parts.append(seg.text)
        text = " ".join(text_parts).strip()
        return text, info.duration if info else 0.0
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
