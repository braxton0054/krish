import sounddevice as sd
import numpy as np
import wave
from config.settings import INPUT_FILE, SAMPLE_RATE, DURATION, INPUT_DEVICE


def record(duration: int | None = None, filename: str | None = None) -> str:
    dur = duration or DURATION
    path = filename or str(INPUT_FILE)

    print(f"Recording for {dur} seconds...")
    audio = sd.rec(
        int(dur * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
        device=INPUT_DEVICE,
    )
    sd.wait()

    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio.tobytes())

    print(f"Saved to {path}")
    return path
