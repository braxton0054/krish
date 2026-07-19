import base64
import io
import logging
import tempfile
from pathlib import Path

from PIL import Image

logger = logging.getLogger("krish.vision")

TEMP_DIR = Path(tempfile.gettempdir()) / "krish_vision"
TEMP_DIR.mkdir(parents=True, exist_ok=True)


class FrameStore:
    def __init__(self, config: dict):
        self._latest_frame: bytes | None = None
        self._latest_source: str | None = None
        self._enabled = False
        vision_cfg = config.get("vision", {})
        self._on_demand = vision_cfg.get("send_frames_on_demand", True)
        self._max_width = vision_cfg.get("max_width", 640)
        self._jpeg_quality = vision_cfg.get("jpeg_quality", 70)

    @property
    def has_frame(self) -> bool:
        return self._latest_frame is not None

    @property
    def source(self) -> str | None:
        return self._latest_source

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, val: bool):
        self._enabled = val

    def store_frame(self, data: bytes, source: str):
        self._latest_frame = data
        self._latest_source = source

    def consume_frame(self) -> tuple[bytes | None, str | None]:
        frame = self._latest_frame
        src = self._latest_source
        if self._on_demand:
            self._latest_frame = None
            self._latest_source = None
        return frame, src

    def clear(self):
        self._latest_frame = None
        self._latest_source = None

    def get_frame_path(self, raw_b64: str) -> str | None:
        try:
            raw = base64.b64decode(raw_b64)
            img = Image.open(io.BytesIO(raw))
            if img.mode != "RGB":
                img = img.convert("RGB")
            if max(img.size) > self._max_width:
                ratio = self._max_width / max(img.size)
                new_size = (int(img.width * ratio), int(img.height * ratio))
                img = img.resize(new_size, Image.LANCZOS)
            out_path = TEMP_DIR / "latest_frame.jpg"
            img.save(str(out_path), "JPEG", quality=self._jpeg_quality)
            return str(out_path)
        except Exception as e:
            logger.warning(f"Failed to process frame: {e}")
            return None

    def get_frame_bytes(self, raw_b64: str) -> bytes | None:
        try:
            return base64.b64decode(raw_b64)
        except Exception as e:
            logger.warning(f"Failed to decode frame: {e}")
            return None
