#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "╔══════════════════════════════════════════╗"
echo "║          KRISH — Voice AI v1.0          ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# ─── Check Python ────────────────────────────────────────────────
PYTHON="python3"
if ! command -v "$PYTHON" &>/dev/null; then
  echo "✖ Python 3 not found."
  echo "  Install: sudo apt install python3 python3-venv python3-pip"
  exit 1
fi
echo "✓ Python: $($PYTHON --version)"

# ─── Check OpenCode ─────────────────────────────────────────────
if ! command -v opencode &>/dev/null; then
  echo "✖ OpenCode CLI not found in PATH."
  echo "  Install: npm install -g @opencode/cli"
  echo "  Or download from: https://opencode.ai"
  exit 1
fi
echo "✓ OpenCode: $(which opencode) v$(opencode --version 2>&1 | head -1)"

# ─── Check ffmpeg ───────────────────────────────────────────────
if ! command -v ffmpeg &>/dev/null; then
  echo "✖ ffmpeg not found."
  echo "  Install: sudo apt install ffmpeg"
  exit 1
fi
echo "✓ ffmpeg: $(ffmpeg -version 2>&1 | head -1 | sed 's/ffmpeg version //')"

# ─── Virtual environment ─────────────────────────────────────────
VENV_DIR="$SCRIPT_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
  echo ""
  echo "── Creating Python virtual environment..."
  $PYTHON -m venv "$VENV_DIR"
fi

# Activate venv
source "$VENV_DIR/bin/activate"
PYTHON="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"
echo "✓ Virtual env: $($PYTHON --version) @ $VENV_DIR"

# ─── Install Python dependencies ─────────────────────────────────
echo ""
echo "── Installing Python dependencies..."
$PIP install -q --upgrade pip setuptools wheel 2>&1 | tail -1
$PIP install -q -r "$SCRIPT_DIR/requirements.txt" 2>&1 | tail -1
echo "✓ Dependencies installed"

# ─── Pre-download models ─────────────────────────────────────────
echo ""
echo "── Pre-downloading models (first run only)..."
echo "   (This may take a few minutes on first launch)"

echo -n "   • Faster-Whisper (base)... "
$PYTHON -c "
from faster_whisper import WhisperModel
WhisperModel('base', device='cpu', compute_type='int8')
print('ready')
" 2>/dev/null || echo "download scheduled (will load on first request)"

echo -n "   • Kokoro TTS... "
$PYTHON -c "
from kokoro import KPipeline
KPipeline(lang_code='a')
print('ready')
" 2>/dev/null || echo "download scheduled (will load on first request)"

echo ""

# ─── Launch backend ──────────────────────────────────────────────
echo "── Starting Krish backend server..."
echo "   URL:  http://127.0.0.1:3000"
echo "   WS:   ws://127.0.0.1:3000/ws"
echo ""

cd "$SCRIPT_DIR/backend"
exec "$VENV_DIR/bin/uvicorn" server:app \
  --host 0.0.0.0 \
  --port 3000 \
  --log-level info
