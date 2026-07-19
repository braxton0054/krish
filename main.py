#!/usr/bin/env python3
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from audio.listen import record
from audio.transcribe import transcribe
from audio.speak import speak
from llm.chat import ask
from config.settings import INPUT_FILE
import config.settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(Path(__file__).parent / "logs" / "krish.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("krish")


def single_turn(text: str | None):
    if text:
        user_input = text
    else:
        record()
        print("Transcribing...")
        user_input = transcribe(str(INPUT_FILE))
        print(f"You: {user_input}")

    if not user_input.strip():
        print("Nothing heard.")
        return

    print("Thinking...")
    reply = ask(user_input)
    print(f"Krish: {reply}")

    print("Speaking...")
    speak(reply)
    print("Done.")


def chat_loop():
    print("Krish voice assistant. Press Ctrl+C to exit.")
    while True:
        try:
            record()
            print("Transcribing...")
            user_input = transcribe(str(INPUT_FILE))
            print(f"You: {user_input}")

            if not user_input.strip():
                continue

            reply = ask(user_input)
            print(f"Krish: {reply}")

            speak(reply)
        except KeyboardInterrupt:
            print("\nGoodbye.")
            break
        except Exception as e:
            log.error(f"Error: {e}")


def main():
    parser = argparse.ArgumentParser(description="Krish - Voice assistant CLI")
    parser.add_argument("--text", "-t", help="Send text directly (skip recording)")
    parser.add_argument("--loop", "-l", action="store_true", help="Continuous conversation loop")
    parser.add_argument("--record-duration", "-d", type=int, help="Recording duration in seconds")
    parser.add_argument("--model", "-m", help="Ollama model override")
    args = parser.parse_args()

    if args.record_duration:
        config.settings.DURATION = args.record_duration
    if args.model:
        config.settings.OLLAMA_MODEL = args.model

    if args.loop:
        chat_loop()
    else:
        single_turn(args.text)


if __name__ == "__main__":
    main()
