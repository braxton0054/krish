from faster_whisper import WhisperModel
from config.settings import WHISPER_MODEL, WHISPER_DEVICE, WHISPER_COMPUTE

_model: WhisperModel | None = None


def get_model() -> WhisperModel:
    global _model
    if _model is None:
        print(f"Loading Whisper model ({WHISPER_MODEL})...")
        _model = WhisperModel(WHISPER_MODEL, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE)
    return _model


def transcribe(audio_path: str) -> str:
    model = get_model()
    segments, _ = model.transcribe(audio_path)
    return " ".join(seg.text for seg in segments)
