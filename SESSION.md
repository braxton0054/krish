# Krish — Session State (Jul 19, 2026)

## What was done (this session)
- **Vision support added**: Krish can now see webcam + screen capture
- **`backend/vision_bridge.py`**: `FrameStore` — receives base64 frames from browser, resizes, saves to temp JPEG files
- **`backend/gemini_bridge.py`**: Updated `query_gemini()` to accept optional `image_bytes` — sends JPEG to Gemini 2.5 Flash via `Part.from_bytes()`
- **`backend/opencode_bridge.py`**: Updated `query_opencode()` to accept optional `image_path` — attaches image via `--file` flag
- **`backend/server.py`**: Wire vision frames into both `StreamSession` and `WakeSession` processing pipelines; added `vision_frame` and `vision_config` WebSocket message handlers
- **`frontend/app.js`**: Added `VisionCapture` class — `getUserMedia` for webcam, `getDisplayMedia` for screen, canvas frame capture at 640px max width, JPEG base64 output; on-demand frame sent on audio_end or wake_detected
- **`frontend/index.html`**: Added vision panel with WEBCAM/SCREEN buttons, mode toggle (ON DEMAND / STREAMING); vision settings toggles in CFG panel
- **`frontend/styles.css`**: Vision feed styling — 4:3 aspect ratio, terminal glow border, HUD-matching controls
- **`config.json`**: Added `vision` section
- **`requirements.txt`**: Added `Pillow>=10.0.0`

## File changes
- `backend/vision_bridge.py` — NEW
- `backend/gemini_bridge.py` — `query_gemini` gets `image_bytes` param
- `backend/opencode_bridge.py` — `query_opencode` gets `image_path` param
- `backend/server.py` — FrameStore import, vision WS handlers, vision in pipeline
- `frontend/app.js` — VisionCapture class, vision init/settings/buttons
- `frontend/index.html` — vision-panel, vision settings toggles
- `frontend/styles.css` — .vision-panel, .vision-feed, .vision-btn rules
- `config.json` — vision block
- `requirements.txt` — +Pillow
- `README.md` — vision section + updated structure

## To continue
```bash
# Rebuild with new deps
source .venv/bin/activate
pip install -r requirements.txt

# Restart server
systemctl restart krish.service
# or
journalctl -u krish.service -n 50 --no-pager
```
