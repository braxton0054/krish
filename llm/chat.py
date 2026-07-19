import ollama
from config.settings import OLLAMA_MODEL, OLLAMA_HOST

ollama_client = ollama.Client(host=OLLAMA_HOST)


def ask(prompt: str, system: str | None = None) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    response = ollama_client.chat(model=OLLAMA_MODEL, messages=messages)
    return response["message"]["content"]
