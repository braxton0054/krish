import asyncio
import os
import re
from typing import Optional

from google import genai
from google.genai import types as genai_types

SYSTEM_PROMPT_TPL = """{soul}

## Response Protocol

You are Krish's conversational voice layer, powered by Gemini. Respond naturally and concisely (spoken-word friendly, no markdown).

When the user asks for something that involves **writing code, debugging, file operations, system commands, or multi-step tool execution**: end your response with:

<task>
the exact instructions for the coding assistant to follow
</task>

For everything else (chat, questions, advice, explanations, identity questions) — just respond as yourself, no tags needed. Never wrap identity or casual questions in <task> tags.

Identity rule: If asked "what model are you" or "who are you", answer that you are Krish (Gemini-powered). Do NOT emit <task> tags for such questions.

Keep responses short and spoken-word natural. Ask follow-up questions when appropriate.

## Vision Capability

You can see webcam or screen-capture images when the user provides them. Use this to:
- Describe what the user is showing you
- Answer questions about the image content
- Help debug visual issues the user encounters
- Guide the user through UI they're looking at
"""


def build_system_prompt(soul_content: str) -> str:
    return SYSTEM_PROMPT_TPL.format(soul=soul_content or "(no memory loaded)")


def get_client() -> genai.Client | None:
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return None
    return genai.Client(api_key=api_key)


def parse_gemini_response(text: str) -> dict:
    task_match = re.search(r"<task>(.*?)</task>", text, re.DOTALL)
    clean = re.sub(r"<task>.*?</task>", "", text, flags=re.DOTALL).strip()
    return {
        "response": clean or "Let me work on that.",
        "task": task_match.group(1).strip() if task_match else None,
    }


def _query_sync(user_text: str, soul_content: str, model: str,
                image_bytes: Optional[bytes] = None) -> dict | None:
    client = get_client()
    if not client:
        return None

    parts = [genai_types.Part.from_text(text=user_text)]
    if image_bytes:
        parts.insert(0, genai_types.Part.from_bytes(
            data=image_bytes, mime_type="image/jpeg",
        ))

    response = client.models.generate_content(
        model=model,
        contents=genai_types.Content(parts=parts, role="user"),
        config={"system_instruction": build_system_prompt(soul_content)},
    )
    return parse_gemini_response(response.text)


async def query_gemini(user_text: str, soul_content: str,
                       model: str = "gemini-2.5-flash",
                       image_bytes: Optional[bytes] = None) -> dict | None:
    return await asyncio.to_thread(
        _query_sync, user_text, soul_content, model, image_bytes,
    )
