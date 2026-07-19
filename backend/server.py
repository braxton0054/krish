import asyncio
import base64
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from config_loader import load_config, save_config
from stt import transcribe
from tts import synthesize
from classifier import classify
from opencode_bridge import query_opencode
from gemini_bridge import query_gemini
from memory import read_soul, append_log, update_user_context
from wake_word import KeywordSpotter, pcm_to_wav, VAD
from vision_bridge import FrameStore

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("krish.server")

CONFIG_PATH = Path(__file__).parent.parent / "config.json"
config = load_config(CONFIG_PATH)

app = FastAPI(title="Krish")
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

# ─── Pre-load Whisper model so wake-word checks don't lag ───────
import threading
def _warmup():
    from stt import get_stt_model
    get_stt_model(config)
    logger.info("Whisper model pre-loaded for wake-word detection")
threading.Thread(target=_warmup, daemon=True).start()

# ─── Frontend routes ─────────────────────────────────────────────
@app.get("/")
@app.head("/")
async def serve_index():
    return FileResponse(str(FRONTEND_DIR / "index.html"))

@app.get("/styles.css")
@app.head("/styles.css")
async def serve_css():
    return FileResponse(str(FRONTEND_DIR / "styles.css"), media_type="text/css")

@app.get("/app.js")
@app.head("/app.js")
async def serve_js():
    return FileResponse(str(FRONTEND_DIR / "app.js"), media_type="text/javascript")


# ─── Streaming session helpers ──────────────────────────────────
class StreamSession:
    def __init__(self, ws, config):
        self.ws = ws
        self.config = config
        self.buffer = bytearray()
        self.streaming = False
        self.interim_task = None
        self.last_chunk_time = 0
        self.silence_timer = None
        self.silence_seconds = 0
        self.frame_store = FrameStore(config)
        self.vision_enabled = False
        self.vision_source = "webcam"

    async def start(self):
        self.streaming = True
        self.buffer.clear()
        self.interim_task = asyncio.create_task(self._interim_loop())

    async def add_chunk(self, data: bytes):
        self.buffer.extend(data)
        self.last_chunk_time = asyncio.get_event_loop().time()

    async def stop_and_process(self):
        self.streaming = False
        if self.interim_task:
            self.interim_task.cancel()
            self.interim_task = None

        audio_data = bytes(self.buffer)
        self.buffer.clear()

        if len(audio_data) < 1000:
            await self.ws.send_json({"type": "status", "state": "idle"})
            return

        await self.ws.send_json({"type": "status", "state": "transcribing"})

        text = ""
        try:
            text, _ = transcribe(audio_data, self.config)
        except Exception as e:
            logger.exception("Transcription failed")
            await self.ws.send_json({"type": "error", "message": f"Transcription failed: {e}"})
            await self.ws.send_json({"type": "status", "state": "idle"})
            return

        if not text.strip():
            await self.ws.send_json({"type": "status", "state": "idle"})
            return

        await self.ws.send_json({"type": "transcript", "text": text, "final": True})

        # ─── Vision frame (consume on-demand) ────────────────────
        image_bytes = None
        image_path = None
        if self.frame_store.enabled and self.frame_store.has_frame:
            raw_b64, src = self.frame_store.consume_frame()
            if raw_b64:
                image_bytes = self.frame_store.get_frame_bytes(raw_b64)
                image_path = self.frame_store.get_frame_path(raw_b64)
                logger.info(f"Vision frame consumed (source: {src})")

        # ─── Route through Gemini? ────────────────────────────────
        gemini_cfg = self.config.get("gemini", {})
        gemini_enabled = gemini_cfg.get("enabled", True)
        gemini_mode = gemini_cfg.get("mode", "gemini_first")

        response_text = ""
        used_gemini = False

        if gemini_enabled and gemini_mode == "gemini_first":
            await self.ws.send_json({
                "type": "status", "state": "thinking", "model": "gemini-2.5-flash",
            })

            soul = read_soul()
            try:
                gemini_result = await query_gemini(
                    text, soul, gemini_cfg.get("model", "gemini-2.5-flash"),
                    image_bytes=image_bytes,
                )
                if gemini_result:
                    used_gemini = True
                    response_text = gemini_result["response"]

                    if gemini_result["task"]:
                        await self.ws.send_json({
                            "type": "status", "state": "thinking",
                            "model": "opencode/deepseek-v4-flash-free",
                            "note": "Handing off to OpenCode for task execution",
                        })
                        task = gemini_result["task"]
                        opencode_result = ""
                        try:
                            opencode_result = await query_opencode(
                                task, "thinking", self.config,
                                image_path=image_path,
                            )
                        except Exception as e:
                            logger.exception("OpenCode task failed")
                            opencode_result = f"I ran into an error: {e}"

                        summarize = gemini_cfg.get("summarize_opencode", True)
                        if summarize and opencode_result:
                            brief = f"The user asked: \"{text}\"\n\nThe coding task was: \"{task}\"\n\nThe result: \"{opencode_result[:2000]}\"\n\nProvide a brief conversational summary of the result for the user."
                            try:
                                summary = await query_gemini(brief, soul, gemini_cfg.get("model"))
                                if summary:
                                    response_text = summary["response"]
                                else:
                                    response_text = opencode_result[:500]
                            except Exception:
                                response_text = opencode_result[:500]
                        else:
                            response_text = opencode_result[:500]

            except Exception as e:
                logger.warning(f"Gemini query failed, falling back to OpenCode: {e}")
                used_gemini = False

        # ─── Fallback: classifier + OpenCode ──────────────────────
        if not used_gemini:
            model_choice = classify(text, self.config)
            await self.ws.send_json({
                "type": "status", "state": "thinking", "model": model_choice,
            })
            try:
                response_text = await query_opencode(
                    text, model_choice, self.config,
                    image_path=image_path,
                )
            except Exception as e:
                logger.exception("OpenCode query failed")
                await self.ws.send_json({"type": "error", "message": f"Reasoning failed: {e}"})
                await self.ws.send_json({"type": "status", "state": "idle"})
                return

        # ─── Speak the response ───────────────────────────────────
        await self.ws.send_json({"type": "response_text", "text": response_text})
        await self.ws.send_json({"type": "status", "state": "generating_speech"})

        audio_bytes = None
        try:
            audio_bytes = synthesize(response_text, self.config)
        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}")

        if audio_bytes:
            await self.ws.send_json({
                "type": "response_audio",
                "data": base64.b64encode(audio_bytes).decode("ascii"),
                "format": "wav",
            })

        await self.ws.send_json({"type": "status", "state": "idle"})

        # ─── Update soul.md memory ────────────────────────────────
        try:
            mem_cfg = self.config.get("memory", {})
            if mem_cfg.get("update_after_session", True):
                summary = (
                    f"User: \"{text[:100]}\" → "
                    f"Krish: \"{response_text[:100]}\""
                    + (" [Gemini → OpenCode]" if used_gemini else "")
                )
                append_log(summary)
        except Exception as e:
            logger.warning(f"Memory update failed: {e}")

    async def _interim_loop(self):
        try:
            while self.streaming:
                await asyncio.sleep(2)
                if not self.streaming or len(self.buffer) < 10000:
                    continue
                chunk = bytes(self.buffer)
                try:
                    text, _ = transcribe(chunk, self.config)
                    if text.strip():
                        await self.ws.send_json({
                            "type": "interim", "text": text.strip(),
                        })
                except Exception:
                    pass
        except asyncio.CancelledError:
            pass


# ─── Wake Word Session ────────────────────────────────────────────
class WakeSession:
    WAKE = "wake_listening"
    RECORDING = "recording"

    def __init__(self, ws, config, frame_store=None):
        self.ws = ws
        self.config = config
        self.state = self.WAKE
        self.pcm_buffer = bytearray()
        self.spotter = KeywordSpotter(config)
        self._processing = False
        self._last_check = 0.0
        self.frame_store = frame_store

        ww_cfg = config.get("wake_word", {})
        vad_ms = ww_cfg.get("vad_silence_ms", 1500)
        vad_threshold = ww_cfg.get("vad_threshold", 0.02)
        self.vad = VAD(threshold=vad_threshold, silence_ms=vad_ms)
        self._active = True
        self._kw_ring = bytearray()
        logger.info("WakeSession started (Whisper keyword spotter)")

    async def feed_pcm(self, pcm_bytes: bytes, sample_rate: int = None):
        if not self._active:
            return

        if self.state == self.WAKE:
            self._kw_ring.extend(pcm_bytes)
            if len(self._kw_ring) > self.spotter.min_samples * 3:
                self._kw_ring = self._kw_ring[-self.spotter.min_samples * 2:]
            now = asyncio.get_event_loop().time()
            kw_len = len(self._kw_ring)
            # Measure RMS of incoming chunk for diagnostics
            if len(pcm_bytes) >= 2:
                import struct as _struct
                vals = _struct.unpack(f"<{len(pcm_bytes)//2}h", pcm_bytes)
                rms = (sum(v*v for v in vals) / len(vals)) ** 0.5
                if kw_len % (self.spotter.min_samples) < (self.spotter.check_interval * 16000 * 2):
                    logger.info(f"KW PCM RMS: {rms:.1f} (silence if ~0)")
            if kw_len >= self.spotter.min_samples \
               and now - self._last_check >= self.spotter.check_interval \
               and not self._processing:
                self._last_check = now
                self._processing = True
                data = bytes(self._kw_ring)
                logger.debug(f"KW check: {len(data)} bytes in ring")
                hit = await asyncio.to_thread(self.spotter.check, data)
                self._processing = False
                if hit:
                    logger.info("Wake word detected!")
                    self.state = self.RECORDING
                    self.pcm_buffer.clear()
                    self._kw_ring.clear()
                    self.vad.reset()
                    await self.ws.send_json({"type": "wake_detected"})
                    await self.ws.send_json({
                        "type": "status", "state": "listening",
                        "note": "Wake word detected — speak your command",
                    })
            return

        elif self.state == self.RECORDING:
            self.pcm_buffer.extend(pcm_bytes)
            if self.vad.feed(bytes(pcm_bytes)):
                logger.info("Silence after command — processing")
                await self._process_command()
                self.state = self.WAKE
                self.vad.reset()

    async def _process_command(self):
        self._processing = True
        audio = bytes(self.pcm_buffer)
        self.pcm_buffer.clear()

        if len(audio) < 2000:
            await self.resume_listening()
            return

        wav_data = pcm_to_wav(audio)
        text = ""
        try:
            text, _ = transcribe(wav_data, self.config)
        except Exception as e:
            logger.exception("Wake transcription failed")
            await self.ws.send_json({"type": "error", "message": f"Transcription failed: {e}"})
            await self.resume_listening()
            self._processing = False
            return

        if not text.strip():
            await self.resume_listening()
            self._processing = False
            return

        await self.ws.send_json({"type": "transcript", "text": text, "final": True})

        # ─── Vision frame (consume on-demand) ────────────────────
        image_bytes = None
        image_path = None
        if self.frame_store and self.frame_store.enabled and self.frame_store.has_frame:
            raw_b64, src = self.frame_store.consume_frame()
            if raw_b64:
                image_bytes = self.frame_store.get_frame_bytes(raw_b64)
                image_path = self.frame_store.get_frame_path(raw_b64)
                logger.info(f"Wake: vision frame consumed (source: {src})")

        # ─── Route through Gemini / OpenCode ──────────────────────
        gemini_cfg = self.config.get("gemini", {})
        gemini_enabled = gemini_cfg.get("enabled", True)
        gemini_mode = gemini_cfg.get("mode", "gemini_first")

        response_text = ""
        used_gemini = False

        if gemini_enabled and gemini_mode == "gemini_first":
            await self.ws.send_json({
                "type": "status", "state": "thinking", "model": "gemini-2.5-flash",
            })
            soul = read_soul()
            try:
                gemini_result = await query_gemini(
                    text, soul, gemini_cfg.get("model", "gemini-2.5-flash"),
                    image_bytes=image_bytes,
                )
                if gemini_result:
                    used_gemini = True
                    response_text = gemini_result["response"]
                    if gemini_result["task"]:
                        await self.ws.send_json({
                            "type": "status", "state": "thinking",
                            "model": "opencode/deepseek-v4-flash-free",
                        })
                        task = gemini_result["task"]
                        opencode_result = ""
                        try:
                            opencode_result = await query_opencode(
                                task, "thinking", self.config,
                                image_path=image_path,
                            )
                        except Exception as e:
                            opencode_result = f"Error: {e}"
                        summarize = gemini_cfg.get("summarize_opencode", True)
                        if summarize and opencode_result:
                            brief = f"User asked: \"{text}\"\nTask: \"{task}\"\nResult: \"{opencode_result[:2000]}\"\nGive a brief conversational summary."
                            try:
                                summary = await query_gemini(brief, soul, gemini_cfg.get("model"))
                                response_text = summary["response"] if summary else opencode_result[:500]
                            except Exception:
                                response_text = opencode_result[:500]
                        else:
                            response_text = opencode_result[:500]
            except Exception as e:
                logger.warning(f"Gemini failed in wake mode: {e}")
                used_gemini = False

        if not used_gemini:
            model_choice = classify(text, self.config)
            await self.ws.send_json({
                "type": "status", "state": "thinking", "model": model_choice,
            })
            try:
                response_text = await query_opencode(
                    text, model_choice, self.config,
                    image_path=image_path,
                )
            except Exception as e:
                await self.ws.send_json({"type": "error", "message": f"Reasoning failed: {e}"})
                await self.resume_listening()
                self._processing = False
                return

        await self.ws.send_json({"type": "response_text", "text": response_text})
        await self.ws.send_json({"type": "status", "state": "generating_speech"})

        audio_bytes = None
        try:
            audio_bytes = synthesize(response_text, self.config)
        except Exception as e:
            logger.error(f"Wake TTS failed: {e}")

        if audio_bytes:
            await self.ws.send_json({
                "type": "response_audio",
                "data": base64.b64encode(audio_bytes).decode("ascii"),
                "format": "wav",
            })

        await self.ws.send_json({"type": "status", "state": "idle"})

        try:
            mem_cfg = self.config.get("memory", {})
            if mem_cfg.get("update_after_session", True):
                append_log(f"User: \"{text[:100]}\" → Krish: \"{response_text[:100]}\" [wake]")
        except Exception as e:
            logger.warning(f"Memory update failed: {e}")

        self._processing = False

    async def resume_listening(self):
        self.state = self.WAKE
        self.pcm_buffer.clear()
        self.vad.reset()
        await self.ws.send_json({"type": "resume_wake_listen"})
        await self.ws.send_json({
            "type": "status", "state": "wake_listening",
        })

    def stop(self):
        self._active = False


# ─── WebSocket ───────────────────────────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    logger.info("WebSocket client connected")

    session = StreamSession(ws, config)
    wake_session = None

    try:
        while True:
            msg = await ws.receive()

            if msg.get("type") == "websocket.disconnect":
                logger.info("WebSocket client disconnected")
                if session.streaming:
                    await session.stop_and_process()
                if wake_session:
                    wake_session.stop()
                break

            if "text" in msg:
                try:
                    data = json.loads(msg["text"])

                    if data["type"] == "audio_start":
                        await session.start()

                    elif data["type"] == "audio_end":
                        await session.stop_and_process()

                    elif data["type"] == "enter_wake_mode":
                        logger.info("enter_wake_mode received from client")
                        wake_session = WakeSession(ws, config, frame_store=session.frame_store)
                        if data.get("sensitivity"):
                            try:
                                sens = float(data["sensitivity"])
                                wake_session.vad.threshold = 0.02 * (sens * 2)
                            except (ValueError, TypeError):
                                pass
                        await ws.send_json({
                            "type": "status", "state": "wake_listening",
                        })

                    elif data["type"] == "exit_wake_mode":
                        if wake_session:
                            wake_session.stop()
                            wake_session = None
                        await ws.send_json({
                            "type": "status", "state": "idle",
                        })

                    elif data["type"] == "ping":
                        await ws.send_json({"type": "pong"})

                    elif data.get("type") == "pcm_config" and wake_session:
                        if data.get("sample_rate"):
                            wake_session._browser_rate = data["sample_rate"]

                    elif data["type"] == "vision_frame":
                        raw = data.get("data", "")
                        source = data.get("source", "webcam")
                        if raw:
                            session.frame_store.store_frame(raw, source)
                            logger.debug(f"Vision frame received ({len(raw)} b64 chars, source: {source})")

                    elif data["type"] == "vision_config":
                        session.vision_enabled = data.get("enabled", False)
                        session.frame_store.set_enabled(session.vision_enabled)
                        session.vision_source = data.get("source", "webcam")
                        if data.get("source"):
                            session.frame_store._latest_source = data["source"]
                        logger.info(f"Vision config: enabled={session.vision_enabled}, source={session.vision_source}")

                    elif data["type"] == "config_update":
                        changed = []
                        if "fast_model" in data:
                            config["opencode"]["fast_model"] = data["fast_model"]
                            changed.append(f"fast_model={data['fast_model']}")
                        if "thinking_model" in data:
                            config["opencode"]["thinking_model"] = data["thinking_model"]
                            changed.append(f"thinking_model={data['thinking_model']}")
                        if "voice" in data:
                            config["tts"]["voice"] = data["voice"]
                            changed.append(f"voice={data['voice']}")
                        if "threshold" in data:
                            config["classifier"]["complexity_threshold"] = data["threshold"]
                            changed.append(f"threshold={data['threshold']}")
                        if "wake_sensitivity" in data and wake_session:
                            wake_session.vad.threshold = 0.02 * (data["wake_sensitivity"] * 2)
                            changed.append(f"wake_sens={data['wake_sensitivity']}")
                        try:
                            save_config(config)
                        except Exception as e:
                            logger.warning(f"Failed to persist config: {e}")
                        logger.info(f"Config hot-reloaded: {', '.join(changed)}")
                        await ws.send_json({"type": "config_ack", "updated": changed})

                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning(f"JSON parse error: {e}")

            elif "bytes" in msg:
                if wake_session and wake_session._active and wake_session.state in (
                    wake_session.WAKE, wake_session.RECORDING,
                ):
                    await wake_session.feed_pcm(msg["bytes"])
                elif session.streaming:
                    await session.add_chunk(msg["bytes"])
                elif not wake_session:
                    logger.debug(f"Received {len(msg['bytes'])} bytes but no wake_session active")
                else:
                    logger.warning(f"Received {len(msg['bytes'])} bytes — not routed (state={wake_session.state if wake_session else 'none'})")

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.exception("WebSocket error")
    finally:
        if wake_session:
            wake_session.stop()
        try:
            await ws.close()
        except Exception:
            pass


if __name__ == "__main__":
    import uvicorn
    host = config.get("server", {}).get("host", "127.0.0.1")
    port = config.get("server", {}).get("port", 3000)
    uvicorn.run(app, host=host, port=port, log_level="info")
