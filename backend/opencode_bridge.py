import asyncio
import json
import logging
from typing import Optional

logger = logging.getLogger("krish.opencode_bridge")

async def query_opencode(text: str, model_choice: str, config: dict,
                         image_path: Optional[str] = None) -> str:
    oc_cfg = config.get("opencode", {})
    opencode_path = oc_cfg.get("path", "opencode")
    timeout_ms = oc_cfg.get("timeout_ms", 120000)

    if model_choice == "thinking":
        model = oc_cfg.get("thinking_model")
        variant = oc_cfg.get("thinking_variant")
    else:
        model = oc_cfg.get("fast_model")
        variant = oc_cfg.get("fast_variant")

    cmd = [opencode_path, "run", "--pure", "--format", "json"]
    if model:
        cmd.extend(["--model", model])
    if variant:
        cmd.extend(["--variant", variant])
    if image_path:
        cmd.extend(["--file", image_path])
    cmd.append(text)

    logger.info(f"Running opencode: {' '.join(cmd)}")

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        full_response = []
        try:
            while True:
                raw_line = await proc.stdout.readline()
                if not raw_line:
                    break
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    if isinstance(event, dict):
                        content = ""
                        if event.get("type") == "text" and "part" in event:
                            content = event["part"].get("text", "")
                        elif event.get("type") == "error":
                            content = event.get("part", {}).get("text", str(event))
                        if not content:
                            content = event.get("text", "")
                        if not content:
                            content = event.get("content", "")
                        if isinstance(content, str) and content.strip():
                            full_response.append(content)
                except json.JSONDecodeError:
                    full_response.append(line)

            _, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout_ms / 1000
            )
        except asyncio.TimeoutError:
            proc.kill()
            _, stderr = await proc.communicate()
            full_response.append("\n[Response timed out]")

        result = " ".join(full_response).strip()
        if not result:
            stderr_text = stderr.decode("utf-8", errors="replace").strip()
            if stderr_text:
                logger.warning(f"Falling back to stderr output: {stderr_text[:200]}")
                result = stderr_text
            else:
                result = "I'm sorry, I couldn't process that request."

        logger.info(f"OpenCode response ({len(result)} chars)")
        return result

    except FileNotFoundError:
        logger.error(f"OpenCode CLI not found at '{opencode_path}'")
        return "Error: OpenCode CLI not found. Please ensure opencode is installed and in your PATH."
    except Exception as e:
        logger.exception(f"OpenCode subprocess failed: {e}")
        return f"Error processing request: {e}"
