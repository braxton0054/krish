# KRISH — Voice AI Assistant

JARVIS-style voice AI assistant with a Matrix / Iron Man HUD interface. Runs **offline** with Faster-Whisper + Kokoro + OpenCode, with an optional **Gemini 2.5 Flash** conversational layer for fast back-and-forth.

## Architecture

```
┌──────────┐     WebSocket      ┌──────────────────────┐
│ Browser  │ ◄──────────────►   │   FastAPI Server      │
│ (HUD UI) │     audio/text     │   (Python 3.12)       │
└──────────┘                    └──────────────────────┘
                                       │
         ┌─────────────────────────────┼─────────────────────────────┐
         ▼                             ▼                             ▼
  ┌────────────┐              ┌──────────────┐              ┌──────────────┐
  │ Faster-    │              │ Gemini 2.5   │              │ OpenCode CLI │
  │ Whisper    │──── text ───►│ Flash (fast) │── task? ───►│ DeepSeek     │
  │ (STT)      │              │ (opt./cloud) │◄── result───│ (reasoning)  │
  └────────────┘              └──────┬───────┘              └──────────────┘
                                     │ response
                                     ▼
                              ┌──────────────┐
                              │   Kokoro TTS  │
                              │   (speech)    │
                              └──────────────┘
```

| Component | Role | Model |
|-----------|------|-------|
| **Faster-Whisper** | Speech-to-text | `base` (CPU, int8) |
| **Gemini Flash** | Conversational AI (fast path) | `gemini-2.0-flash` (free tier) |
| **OpenCode CLI** | Reasoning & code gen | `deepseek-v4-flash-free` / `deepseek-v4-pro` |
| **Kokoro TTS** | Text-to-speech | 82M param (CPU) |
| **soul.md** | Persistent memory | Rolling log + durable facts |

### Routing

```
Transcribed text → Gemini Flash (fast conversational path)
                    ├── Chat / question → Gemini responds directly → TTS
                    └── Code / task → <task> tag → OpenCode/DeepSeek → Gemini summarizes → TTS
                                        (falls back to classifier + OpenCode if Gemini is disabled)
```

## Prerequisites

- **Kali Linux** (or any Debian-based distro)
- **Python 3.10+**, pip, venv
- **Node.js 18+** (for OpenCode CLI)
- **ffmpeg** (for audio processing)

## Installation

### 1. System dependencies

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv ffmpeg espeak-ng
```

### 2. OpenCode CLI

```bash
npm install -g @opencode/cli

# Verify:
opencode --version

# List available models (optional):
opencode models
```

### 3. Gemini API Key (optional — skip for offline-only)

1. Go to https://aistudio.google.com/apikey
2. Click **Create API Key** (free, no credit card required)
3. Copy the key and add it to `.env`:

```bash
echo 'GEMINI_API_KEY=your_key_here' >> .env
```

Without a key, Krish runs entirely offline using OpenCode/DeepSeek only.

### 4. Krish project

```bash
# Clone or copy the project, then:
cd krish
chmod +x start.sh

# Run the startup script:
./start.sh
```

The startup script will:
- Create a Python virtual environment
- Install `faster-whisper`, `kokoro`, `fastapi`, `uvicorn`, `google-genai`
- Pre-download the Whisper and Kokoro models (first run only)
- Launch the backend server on `http://0.0.0.0:3000`

## Usage

1. Open **http://5.189.191.35:3000** in a browser (Chrome/Firefox recommended)
2. Click the **HOLD TO TALK** mic button (or press **Space**) and speak
3. Release to send — Krish transcribes, reasons, and speaks back

### Controls

| Action | Input |
|--------|-------|
| Record audio | Hold mic button / press Space |
| Toggle recording | Enable "Toggle mode" in settings |
| Open history | Click **HIST** button |
| Open settings | Click **CFG** button |
| Navigate settings | Standard form inputs |

### Model Routing

**Gemini-first mode** (default, requires `GEMINI_API_KEY`):
- Gemini Flash handles conversation, questions, chat
- When Gemini detects a coding/problem-solving request, it tags it with `<task>` and OpenCode/DeepSeek handles it
- OpenCode's result is summarized back through Gemini for natural speech

**OpenCode-only mode** (fully offline):
- Set `"mode": "opencode_only"` in config.json
- Falls back to classifier + OpenCode (DeepSeek) for everything

## Configuration

Edit `config.json`:

```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 3000
  },
  "stt": {
    "model_size": "base",
    "device": "cpu",
    "compute_type": "int8"
  },
  "tts": {
    "voice": "af_heart",
    "speed": 1.0
  },
  "gemini": {
    "enabled": true,
    "model": "gemini-2.0-flash",
    "mode": "gemini_first"
  },
  "opencode": {
    "path": "opencode",
    "fast_model": "opencode/deepseek-v4-flash-free",
    "thinking_model": "opencode/deepseek-v4-pro",
    "thinking_variant": "high"
  },
  "classifier": {
    "type": "heuristic",
    "complexity_threshold": 0.5
  }
}
```

### Voice Options (Kokoro)

| Voice | Gender |
|-------|--------|
| `af_heart` | Female (default) |
| `af_bella` | Female |
| `af_nicole` | Female |
| `am_adam` | Male |
| `am_michael` | Male |

## Wake-Word Detection ("Krish")

Krish supports hands-free wake-word activation using a **local Whisper-based keyword spotter** — no cloud, no API keys, works immediately with any wake word.

### Setup

No setup required. The keyword is configured in `config.json` under `wake_word.keyword` (default: `"krish"`). Change it to any word or phrase you like.

### How It Works

When wake word is enabled:
1. Browser opens a continuous PCM audio stream (16kHz, downsampled in-browser)
2. Server buffers ~2 seconds of audio and periodically runs **Faster-Whisper tiny** transcription
3. If the keyword appears in the transcription → server signals the browser and switches to command capture mode
4. Server-side VAD detects when you stop speaking → transcribes → processes with Gemini/OpenCode → speaks response via TTS
5. After TTS finishes, Krish automatically goes back to listening for the wake word

The UI shows a subtle `"LISTENING FOR ACTIVATION..."` indicator with a pulsing dot. When activated, the full HUD brightens and shows the active state. The mic button is hidden in wake mode but can be re-enabled via settings.

### Mode Toggle

In the settings panel, you can toggle between:
- **Wake word mode** — hands-free, always listening (say "Krish" then your command)
- **Manual PTT mode** — hold-to-talk / click-to-talk (default behavior)

## Persistent Memory (`soul.md`)

Krish keeps a `soul.md` file at the project root that acts as persistent identity + memory across sessions.

**Sections:**
- `## Identity` — Personality, tone, self-reference
- `## User Context` — Name, preferences, projects (learned over time)
- `## Conversation Log` — Rolling summary (last 20 exchanges)

The file is human-readable — you can open and edit it directly. After each voice exchange, Krish appends a one-line summary to the log. Durable facts (name, projects, preferences) can be extracted from the log into User Context.

## Project Structure

```
krish/
├── README.md
├── start.sh                  # Launch script
├── config.json               # All settings
├── requirements.txt          # Python dependencies
├── .env                      # API keys (git-ignore this)
├── .env.example              # Template for .env
├── soul.md                   # Persistent memory (identity + context)
├── backend/
│   ├── server.py             # FastAPI + WebSocket endpoint
│   ├── config_loader.py      # Config loader
│   ├── stt.py                # Faster-Whisper wrapper
│   ├── tts.py                # Kokoro TTS wrapper
│   ├── classifier.py         # Request complexity classifier
│   ├── opencode_bridge.py    # OpenCode CLI subprocess
│   ├── gemini_bridge.py      # Gemini Flash API + task handoff (supports image input)
│   ├── memory.py             # soul.md read/write
│   ├── wake_word.py          # Porcupine wake-word + VAD
│   └── vision_bridge.py      # FrameStore: vision frame management
└── frontend/
    ├── index.html            # HUD layout + video feeds
    ├── styles.css            # Matrix/HUD theme + vision styles
    └── app.js                # WebSocket, audio, canvas, VisionCapture
```

## Vision Support (Webcam + Screen Capture)

Krish can see — both your webcam and your screen. Vision frames are captured on-demand when you speak and sent alongside your voice for visual context.

### How It Works

1. Enable vision in the **CFG** panel (toggle "Enable vision")
2. Click **WEBCAM** or **SCREEN** in the vision bar to start a feed
3. By default, a single frame is captured when you speak ("On Demand" mode)
4. The frame is sent to the backend alongside your transcribed voice
5. Gemini 2.5 Flash (which natively supports vision) analyzes the image + text
6. If a coding task is detected, the image is also passed to OpenCode via `--file`

### Vision Configuration (config.json)

```json
{
  "vision": {
    "enabled": true,
    "webcam": false,
    "screen_capture": false,
    "frame_capture_interval_ms": 500,
    "send_frames_on_demand": true,
    "max_width": 640,
    "jpeg_quality": 70
  }
}
```

| Setting | Description |
|---------|-------------|
| `enabled` | Master toggle |
| `frame_capture_interval_ms` | Frame interval in streaming mode |
| `send_frames_on_demand` | Capture only when user speaks (vs. constant streaming) |
| `max_width` | Max image width (maintains aspect ratio) |
| `jpeg_quality` | JPEG quality 1-100 |

### Modes

- **On Demand** (default): A single frame is captured when you press-to-talk or say "Krish" — minimal bandwidth, no overhead
- **Streaming**: Frames are sent every 500ms — continuous visual awareness

**Note:** Gemini 2.5 Flash is used for vision analysis since it natively supports images. OpenCode receives the image as a file attachment (`--file`) for context during coding tasks. For text-only models, vision will not function via OpenCode.

### Prerequisites

- **Browser permission**: Webcam requires `getUserMedia()` permission; screen capture requires `getDisplayMedia()`
- **Gemini API key** (required for vision): Vision analysis goes through Gemini 2.5 Flash which natively supports image input
- **Pillow**: Installed automatically via requirements.txt — used for server-side image resizing

## File Structure (updated)

```
krish/
├── backend/
│   ├── ...
│   ├── vision_bridge.py        # FrameStore: receive, store, process frames
│   └── vision.py               # (legacy, removed)
└── frontend/
    ├── ...
    └── app.js                  # +VisionCapture class for webcam/screen
```

## Troubleshooting

**Whisper model download fails**
```bash
# The model cache is at ~/.cache/huggingface/hub/
# You can manually download from: https://huggingface.co/guillaumeklfaster-whisper-base
```

**Kokoro model issues**
```bash
# Kokoro downloads models on first use automatically
# Cache location: ~/.cache/kokoro/
```

**OpenCode model errors**
```bash
opencode models
# Update config.json with a model name from the list
```

**No microphone access**
- Ensure the page is served over `http://` (not `file://`)
- Grant microphone permission when prompted
- Check `about://settings/content/microphone` in Chrome

**Audio playback not working**
- Check browser autoplay policies
- Click anywhere on the page first (user gesture required)
