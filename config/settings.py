from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv(Path(__file__).parent.parent / ".env")

BASE_DIR = Path(__file__).parent.parent

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "sam860/lfm2.5:350m")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE = os.getenv("WHISPER_COMPUTE", "int8")

PIPER_VOICE = os.getenv("PIPER_VOICE", str(BASE_DIR / "models" / "en_US-lessac-medium.onnx"))
PIPER_CONFIG = os.getenv("PIPER_CONFIG", str(BASE_DIR / "models" / "en_US-lessac-medium.onnx.json"))

INPUT_FILE = BASE_DIR / "temp" / "input.wav"
SAMPLE_RATE = int(os.getenv("SAMPLE_RATE", "16000"))
DURATION = int(os.getenv("RECORD_DURATION", "5"))
INPUT_DEVICE = os.getenv("INPUT_DEVICE", None)
