// ─── Configuration ───────────────────────────────────────────────
const DEFAULTS = {
  fastModel: "opencode/deepseek-v4-flash-free",
  thinkingModel: "opencode/deepseek-v4-pro",
  voice: "af_heart",
  wakeWord: false,
  toggleMode: true,
  continuousMode: true,
  threshold: 0.5,
  wakeSensitivity: "0.5",
  visionEnabled: false,
  visionOnDemand: true,
};

let cfg = { ...DEFAULTS };
let state = "idle"; // idle | listening | transcribing | thinking | speaking | generating_speech | wake_listening
let currentModel = null;
let latencyStart = 0;
let conversationHistory = [];
let wakeStreamer = null;
let wakeMode = false;

// ─── DOM refs ────────────────────────────────────────────────────
const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

const matrixCanvas = $("#matrix-rain");
const reactorCanvas = $("#arc-reactor");
const statusDot = $("#status-indicator");
const statusLabel = $("#status-label");
const modelBadge = $("#model-badge");
const userText = $("#user-text");
const krishText = $("#krish-text");
const krishLine = $("#transcript-krish");
const interimLine = $("#interim-line");
const interimText = $("#interim-text");
const micBtn = $("#mic-btn");
const micHint = $("#mic-hint");
const footerModel = $("#footer-model");
const footerLatency = $("#footer-latency");
const footerAudio = $("#footer-audio");
const historyList = $("#history-list");
const historyPanel = $("#history-panel");
const settingsPanel = $("#settings-panel");
const toastContainer = $("#toast-container");
const btnHistory = $("#btn-history");
const btnSettings = $("#btn-settings");
const btnCloseHistory = $("#btn-close-history");
const btnCloseSettings = $("#btn-close-settings");
const btnClearHistory = $("#btn-clear-history");
const btnSaveSettings = $("#btn-save-settings");
const btnResetSettings = $("#btn-reset-settings");

const wakeIndicator = $("#wake-indicator");

// Vision refs
const visionPanel = $("#vision-panel");
const webcamFeed = $("#webcam-feed");
const screenFeed = $("#screen-feed");
const webcamFeedContainer = $("#webcam-feed-container");
const screenFeedContainer = $("#screen-feed-container");
const btnToggleWebcam = $("#btn-toggle-webcam");
const btnToggleScreen = $("#btn-toggle-screen");
const btnVisionMode = $("#btn-vision-mode");

// Settings inputs
const cfgFastModel = $("#cfg-fast-model");
const cfgThinkingModel = $("#cfg-thinking-model");
const cfgVoice = $("#cfg-voice");
const cfgWakeWord = $("#cfg-wake-word");
const cfgToggleMode = $("#cfg-toggle-mode");
const cfgContinuous = $("#cfg-continuous");
const cfgThreshold = $("#cfg-threshold");
const cfgThresholdVal = $("#cfg-threshold-val");
const cfgWakeSensitivity = $("#cfg-wake-sensitivity");
const cfgVisionEnabled = $("#cfg-vision-enabled");
const cfgVisionOnDemand = $("#cfg-vision-on-demand");

// ─── Matrix Rain ────────────────────────────────────────────────
const chars = "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ<>/{}[]|&^%$#@!";

class MatrixRain {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.columns = [];
    this.resize();
    window.addEventListener("resize", () => this.resize());
  }

  resize() {
    const dpr = window.devicePixelRatio || 1;
    this.canvas.width = window.innerWidth * dpr;
    this.canvas.height = window.innerHeight * dpr;
    this.ctx.scale(dpr, dpr);
    this.w = window.innerWidth;
    this.h = window.innerHeight;
    this.colWidth = 14;
    this.numCols = Math.floor(this.w / this.colWidth);
    this.columns = Array.from({ length: this.numCols }, () => ({
      y: Math.random() * this.h,
      speed: 0.5 + Math.random() * 2,
      chars: Array.from({ length: 8 + Math.floor(Math.random() * 12) }, () =>
        chars[Math.floor(Math.random() * chars.length)]
      ),
      opacity: 0.03 + Math.random() * 0.08,
    }));
  }

  draw(time) {
    const ctx = this.ctx;
    ctx.clearRect(0, 0, this.w, this.h);

    for (let i = 0; i < this.columns.length; i++) {
      const col = this.columns[i];
      const x = i * this.colWidth;

      col.y += col.speed * 0.5;
      if (col.y > this.h + 30) {
        col.y = -30;
        col.speed = 0.5 + Math.random() * 2;
      }

      for (let j = 0; j < col.chars.length; j++) {
        const y = col.y - j * this.colWidth;
        if (y < -20 || y > this.h + 20) continue;

        const alpha = col.opacity * (1 - j / col.chars.length);
        const isHead = j === 0;
        ctx.font = `${isHead ? 14 : 12}px "Share Tech Mono", monospace`;
        ctx.fillStyle = isHead
          ? `rgba(200, 255, 200, ${alpha * 1.5})`
          : `rgba(0, 255, 65, ${alpha})`;
        ctx.fillText(
          col.chars[Math.floor((time * 0.001 * col.speed + j) % col.chars.length)],
          x, y
        );
      }
    }
  }
}

// ─── Arc Reactor ────────────────────────────────────────────────
class ArcReactor {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.time = 0;
    this.amplitude = 0;
    this.targetAmp = 0;
    this.resize();
    window.addEventListener("resize", () => this.resize());
  }

  resize() {
    const dpr = window.devicePixelRatio || 1;
    this.canvas.width = window.innerWidth * dpr;
    this.canvas.height = window.innerHeight * dpr;
    this.ctx.scale(dpr, dpr);
    this.w = window.innerWidth;
    this.h = window.innerHeight;
  }

  setAmplitude(val) {
    this.targetAmp = Math.max(0, Math.min(1, val));
  }

  draw(time, currentState) {
    this.time += 0.016;
    this.amplitude += (this.targetAmp - this.amplitude) * 0.1;

    const ctx = this.ctx;
    ctx.clearRect(0, 0, this.w, this.h);

    const cx = this.w / 2;
    const cy = this.h / 2 + 20;
    const baseR = Math.min(this.w, this.h) * 0.18;

    const isActive = currentState !== "idle";
    const primaryColor = currentState === "thinking" ? "#00d4ff" : "#00ff41";
    const secondaryColor = currentState === "thinking" ? "#00ff41" : "#00d4ff";

    const pulse = 0.85 + 0.15 * Math.sin(this.time * (isActive ? 3 : 1.2));
    const rotSpeed = isActive ? 1.5 : 0.4;

    // Outer glow
    const grad = ctx.createRadialGradient(cx, cy, baseR * 0.2, cx, cy, baseR * 1.6);
    grad.addColorStop(0, `rgba(0, 255, 65, ${isActive ? 0.06 : 0.02})`);
    grad.addColorStop(0.5, `rgba(0, 212, 255, ${currentState === "thinking" ? 0.05 : 0.01})`);
    grad.addColorStop(1, "transparent");
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(cx, cy, baseR * 1.6, 0, Math.PI * 2);
    ctx.fill();

    // Speech amplitude rings
    if (currentState === "speaking" || currentState === "listening") {
      const amp = this.amplitude;
      for (let i = 0; i < 4; i++) {
        const r = baseR * (0.8 + i * 0.25 + amp * 0.2);
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.strokeStyle = i % 2 === 0 ? primaryColor : secondaryColor;
        ctx.lineWidth = 1 + amp * 2;
        ctx.globalAlpha = 0.15 + amp * 0.2 - i * 0.03;
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
    }

    // Orbit rings
    const ringCount = currentState === "thinking" ? 6 : 4;
    for (let i = 0; i < ringCount; i++) {
      const r = baseR * (0.7 + i * 0.15);
      const rot = this.time * rotSpeed * (i % 2 === 0 ? 1 : -1) * (0.5 + i * 0.3);

      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(rot);

      const dashLen = 4 + i * 2;
      const gapLen = 12 - i;
      ctx.setLineDash([dashLen, gapLen]);
      ctx.lineDashOffset = -this.time * (20 + i * 5);

      ctx.beginPath();
      ctx.arc(0, 0, r, 0, Math.PI * 2);
      ctx.strokeStyle = i % 2 === 0 ? primaryColor : secondaryColor;
      ctx.lineWidth = 1.5 - i * 0.15;
      ctx.globalAlpha = 0.4 * pulse - i * 0.05;
      ctx.stroke();
      ctx.restore();
    }
    ctx.setLineDash([]);
    ctx.globalAlpha = 1;

    // Center glow
    const cg = ctx.createRadialGradient(cx, cy, 0, cx, cy, baseR * 0.4);
    cg.addColorStop(0, isActive ? "rgba(0, 255, 65, 0.3)" : "rgba(0, 255, 65, 0.08)");
    cg.addColorStop(0.5, isActive ? "rgba(0, 212, 255, 0.15)" : "transparent");
    cg.addColorStop(1, "transparent");
    ctx.fillStyle = cg;
    ctx.beginPath();
    ctx.arc(cx, cy, baseR * 0.4, 0, Math.PI * 2);
    ctx.fill();

    // Crosshairs
    const chLen = baseR * 0.15;
    ctx.strokeStyle = primaryColor;
    ctx.lineWidth = 1;
    ctx.globalAlpha = 0.3 * pulse;
    const angles = [0, Math.PI / 2, Math.PI, 3 * Math.PI / 2];
    for (const a of angles) {
      const x1 = cx + Math.cos(a) * baseR * 0.5;
      const y1 = cy + Math.sin(a) * baseR * 0.5;
      const x2 = cx + Math.cos(a) * (baseR * 0.5 + chLen);
      const y2 = cy + Math.sin(a) * (baseR * 0.5 + chLen);
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.stroke();
    }
    ctx.globalAlpha = 1;

    // Thinking scan
    if (currentState === "thinking") {
      const scanAngle = (this.time * 2) % (Math.PI * 2);
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(scanAngle);
      const grad2 = ctx.createLinearGradient(0, -baseR * 0.3, 0, baseR * 0.4);
      grad2.addColorStop(0, "rgba(0, 212, 255, 0)");
      grad2.addColorStop(0.5, "rgba(0, 212, 255, 0.1)");
      grad2.addColorStop(1, "rgba(0, 212, 255, 0)");
      ctx.fillStyle = grad2;
      ctx.fillRect(-2, -baseR * 0.3, 4, baseR * 0.7);
      ctx.restore();
    }

    // Status text at bottom of reactor
    ctx.font = '9px "Orbitron", monospace';
    ctx.fillStyle = primaryColor;
    ctx.globalAlpha = 0.4;
    ctx.textAlign = "center";
    const statusText = currentState.toUpperCase();
    ctx.fillText(`[ ${statusText} ]`, cx, cy + baseR * 1.4 + 30);
    ctx.globalAlpha = 1;
  }
}

// ─── Audio Recorder ─────────────────────────────────────────────
class AudioRecorder {
  constructor() {
    this.mediaRecorder = null;
    this.stream = null;
    this.audioContext = null;
    this.analyser = null;
    this.recording = false;
    this.vadTimer = null;
    this.silenceStart = null;
    this.onSilence = null;
    this.onChunk = null;
    this.silenceTimeout = 1500;
    this.vadThreshold = 0.02;
  }

  startVAD(onSilence) {
    this.onSilence = onSilence;
    this.silenceStart = null;
    const check = () => {
      if (!this.recording || !this.analyser) return;
      const amp = getMicAmplitude(this.analyser);
      if (amp < this.vadThreshold) {
        if (this.silenceStart === null) this.silenceStart = Date.now();
        else if (Date.now() - this.silenceStart > this.silenceTimeout) {
          if (this.onSilence) this.onSilence();
          return;
        }
      } else {
        this.silenceStart = null;
      }
      this.vadTimer = requestAnimationFrame(check);
    };
    this.vadTimer = requestAnimationFrame(check);
  }

  stopVAD() {
    if (this.vadTimer) cancelAnimationFrame(this.vadTimer);
    this.vadTimer = null;
    this.silenceStart = null;
  }

  async start(onChunk) {
    this.onChunk = onChunk;
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        sampleRate: 16000,
      },
    });

    this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const source = this.audioContext.createMediaStreamSource(this.stream);
    this.analyser = this.audioContext.createAnalyser();
    this.analyser.fftSize = 256;
    source.connect(this.analyser);

    const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
      ? "audio/webm;codecs=opus"
      : "audio/webm";

    this.mediaRecorder = new MediaRecorder(this.stream, { mimeType });
    this.mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0 && this.onChunk) this.onChunk(e.data);
    };
    this.mediaRecorder.start(500);
    this.recording = true;
  }

  stop() {
    return new Promise((resolve) => {
      if (!this.mediaRecorder || !this.recording) {
        resolve(null);
        return;
      }
      this.mediaRecorder.onstop = () => {
        this.recording = false;
        if (this.stream) {
          this.stream.getTracks().forEach((t) => t.stop());
        }
        resolve(true);
      };
      if (this.mediaRecorder.state !== "inactive") {
        this.mediaRecorder.stop();
      } else {
        this.recording = false;
        resolve(null);
      }
    });
  }

  getAnalyser() {
    return this.analyser;
  }
}

// ─── Wake Word Streamer (PCM via ScriptProcessorNode) ───────────
class WakeWordStreamer {
  constructor() {
    this.stream = null;
    this.audioContext = null;
    this.processor = null;
    this.source = null;
    this.analyser = null;
    this.active = false;
    this.onPcm = null;
    this.sampleRate = 16000;
  }

  async start(onPcm) {
    this.onPcm = onPcm;
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true },
    });

    this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
    console.log(`[Krish] AudioContext state: ${this.audioContext.state}`);
    if (this.audioContext.state === "suspended") {
      await this.audioContext.resume();
      console.log(`[Krish] AudioContext resumed: ${this.audioContext.state}`);
    }
    this.sampleRate = this.audioContext.sampleRate;
    this.targetRate = 16000;
    console.log(`[Krish] Mic sample rate: ${this.sampleRate} Hz, target: ${this.targetRate} Hz`);
    this.source = this.audioContext.createMediaStreamSource(this.stream);

    // Load AudioWorklet processor
    const workletUrl = new URL("wake-processor.js", window.location.href).href;
    await this.audioContext.audioWorklet.addModule(workletUrl);
    console.log("[Krish] AudioWorklet module loaded");

    this.processor = new AudioWorkletNode(this.audioContext, "wake-processor");
    let pcmCount = 0;
    this.processor.port.onmessage = (event) => {
      if (!this.active) return;
      const pcmBuffer = event.data;
      if (this.onPcm) {
        this.onPcm(pcmBuffer);
        pcmCount++;
        if (pcmCount % 50 === 0) console.log(`[Krish] PCM chunks sent: ${pcmCount}`);
      }
    };

    this.source.connect(this.processor);
    this.processor.connect(this.audioContext.destination);
    this.active = true;
    console.log("[Krish] WakeWordStreamer active (AudioWorklet)");
  }

  stop() {
    this.active = false;
    if (this.processor) {
      this.processor.disconnect();
      this.processor.port.onmessage = null;
      this.processor = null;
    }
    if (this.source) {
      this.source.disconnect();
      this.source = null;
    }
    if (this.audioContext) {
      this.audioContext.close().catch(() => {});
      this.audioContext = null;
    }
    if (this.stream) {
      this.stream.getTracks().forEach((t) => t.stop());
      this.stream = null;
    }
  }

  getAnalyser() {
    return this.analyser;
  }
}

// ─── Vision Capture ─────────────────────────────────────────────
class VisionCapture {
  constructor() {
    this.webcamStream = null;
    this.screenStream = null;
    this.webcamActive = false;
    this.screenActive = false;
    this.captureTimer = null;
    this.captureInterval = 500;
    this.onDemand = true;
    this.activeSource = null;
  }

  async startWebcam() {
    if (this.webcamActive) return;
    try {
      this.webcamStream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 }, frameRate: { ideal: 15 } },
        audio: false,
      });
      webcamFeed.srcObject = this.webcamStream;
      webcamFeedContainer.style.display = "flex";
      this.webcamActive = true;
      btnToggleWebcam.classList.add("active");
      return true;
    } catch (e) {
      showToast("Webcam denied: " + e.message);
      return false;
    }
  }

  stopWebcam() {
    if (this.webcamStream) {
      this.webcamStream.getTracks().forEach((t) => t.stop());
      this.webcamStream = null;
    }
    webcamFeed.srcObject = null;
    webcamFeedContainer.style.display = "none";
    this.webcamActive = false;
    btnToggleWebcam.classList.remove("active");
  }

  async startScreen() {
    if (this.screenActive) return;
    try {
      this.screenStream = await navigator.mediaDevices.getDisplayMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 }, frameRate: { ideal: 10 } },
        audio: false,
      });
      screenFeed.srcObject = this.screenStream;
      screenFeedContainer.style.display = "flex";

      this.screenStream.getVideoTracks()[0].addEventListener("ended", () => {
        this.stopScreen();
      });

      this.screenActive = true;
      btnToggleScreen.classList.add("active");
      return true;
    } catch (e) {
      showToast("Screen share cancelled");
      return false;
    }
  }

  stopScreen() {
    if (this.screenStream) {
      this.screenStream.getTracks().forEach((t) => t.stop());
      this.screenStream = null;
    }
    screenFeed.srcObject = null;
    screenFeedContainer.style.display = "none";
    this.screenActive = false;
    btnToggleScreen.classList.remove("active");
  }

  captureFrame() {
    if (!this.webcamActive && !this.screenActive) return null;
    const source = this.screenActive ? "screen" : "webcam";
    const video = this.screenActive ? screenFeed : webcamFeed;
    if (!video || !video.videoWidth) return null;

    const canvas = document.createElement("canvas");
    const maxW = 640;
    const scale = Math.min(1, maxW / video.videoWidth);
    canvas.width = Math.round(video.videoWidth * scale);
    canvas.height = Math.round(video.videoHeight * scale);
    const ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    return { data: canvas.toDataURL("image/jpeg", 0.7).split(",")[1], source };
  }

  sendFrame(ws) {
    if (!ws || !this.webcamActive && !this.screenActive) return;
    const frame = this.captureFrame();
    if (frame) {
      ws.sendJson({
        type: "vision_frame",
        data: frame.data,
        source: frame.source,
      });
    }
  }

  startCapturing(ws) {
    this.stopCapturing();
    this.onDemand = cfg.visionOnDemand;

    if (!this.onDemand) {
      this.captureTimer = setInterval(() => {
        this.sendFrame(ws);
      }, this.captureInterval);
    }
  }

  stopCapturing() {
    if (this.captureTimer) {
      clearInterval(this.captureTimer);
      this.captureTimer = null;
    }
  }

  sendOnDemandFrame(ws) {
    if (!this.onDemand) return;
    this.sendFrame(ws);
  }

  stopAll() {
    this.stopCapturing();
    this.stopWebcam();
    this.stopScreen();
  }
}

// ─── WebSocket Manager ──────────────────────────────────────────
class WSClient {
  constructor() {
    this.ws = null;
    this.reconnectTimer = null;
  }

  connect(url) {
    if (this.ws) this.disconnect();
    this.ws = new WebSocket(url);
    this.ws.binaryType = "arraybuffer";

    this.ws.onopen = () => {
      showToast("CONNECTED");
      setStatus("idle");
    };

    this.ws.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer) {
        // Binary audio
        handleAudioResponse(event.data);
        return;
      }
      try {
        const msg = JSON.parse(event.data);
        handleMessage(msg);
      } catch (e) {
        console.warn("Invalid message:", e);
      }
    };

    this.ws.onclose = () => {
      showToast("DISCONNECTED — reconnecting...");
      this.scheduleReconnect(url);
    };

    this.ws.onerror = () => {
      showToast("WS ERROR");
    };
  }

  scheduleReconnect(url) {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = setTimeout(() => this.connect(url), 3000);
  }

  sendJson(obj) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(obj));
      return true;
    }
    return false;
  }

  sendBinary(buf) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(buf);
      return true;
    }
    return false;
  }

  sendAudioChunk(blob) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      blob.arrayBuffer().then((buf) => this.ws.send(buf));
      return true;
    }
    return false;
  }

  sendPing() {
    this.sendJson({ type: "ping" });
  }

  disconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    if (this.ws) {
      this.ws.onclose = null;
      this.ws.close();
      this.ws = null;
    }
  }
}

// ─── Audio Player ───────────────────────────────────────────────
let audioCtx = null;
let audioAnalyser = null;
let audioSourceNode = null;

function getAudioContext() {
  if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  return audioCtx;
}

function playAudioFromBase64(b64, format) {
  return new Promise((resolve) => {
    try {
      const binary = atob(b64);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);

      getAudioContext().decodeAudioData(bytes.buffer, (buffer) => {
        const ctx = getAudioContext();
        const source = ctx.createBufferSource();
        source.buffer = buffer;

        const analyser = ctx.createAnalyser();
        analyser.fftSize = 256;
        source.connect(analyser);
        analyser.connect(ctx.destination);

        audioSourceNode = source;
        audioAnalyser = analyser;

        source.start(0);
        source.onended = resolve;
      }, resolve);
    } catch (e) {
      console.error("Audio playback error:", e);
      resolve();
    }
  });
}

function getAudioAmplitude() {
  if (!audioAnalyser) return 0;
  const data = new Uint8Array(audioAnalyser.frequencyBinCount);
  audioAnalyser.getByteTimeDomainData(data);
  let sum = 0;
  for (let i = 0; i < data.length; i++) {
    const v = (data[i] - 128) / 128;
    sum += v * v;
  }
  return Math.min(1, Math.sqrt(sum / data.length) * 3);
}

function getMicAmplitude(analyser) {
  if (!analyser) return 0;
  const data = new Uint8Array(analyser.frequencyBinCount);
  analyser.getByteTimeDomainData(data);
  let sum = 0;
  for (let i = 0; i < data.length; i++) {
    const v = (data[i] - 128) / 128;
    sum += v * v;
  }
  return Math.min(1, Math.sqrt(sum / data.length) * 2);
}

// ─── State Management ───────────────────────────────────────────
function setStatus(newState) {
  state = newState;
  statusDot.className = "status-dot " + newState;
  statusLabel.textContent = newState.toUpperCase().replace("_", " ");
  if (newState === "wake_listening") {
    statusLabel.textContent = "WAKE LISTENING";
  }
  footerAudio.textContent = `AUDIO:${newState.toUpperCase().slice(0, 4)}`;

  // Wake indicator visibility
  if (wakeIndicator) {
    wakeIndicator.style.display = newState === "wake_listening" ? "flex" : "none";
  }

  if (newState === "idle") {
    micHint.textContent = ns("toggleMode") ? "CLICK TO TALK" : "HOLD TO TALK";
  }
}

function setModelBadge(model) {
  currentModel = model;
  const text = model === "thinking" ? "THINKING" : model === "fast" ? "FAST" : "—";
  modelBadge.textContent = text;
  modelBadge.style.color = model === "thinking" ? "var(--cyan)" : "var(--green)";
  modelBadge.style.borderColor = model === "thinking" ? "var(--cyan-dark)" : "var(--green-dark)";
  footerModel.textContent = `MODEL:${text}`;
}

function showToast(msg) {
  const el = document.createElement("div");
  el.className = "toast";
  el.textContent = msg;
  toastContainer.appendChild(el);
  setTimeout(() => el.remove(), 3000);
}

// ─── Settings helpers ───────────────────────────────────────────
function ns(key) {
  if (key === "toggleMode") return cfg.toggleMode;
  if (key === "wakeWord") return cfg.wakeWord;
  return cfg[key];
}

function loadSettings() {
  try {
    const saved = localStorage.getItem("krish-config");
    if (saved) {
      const parsed = JSON.parse(saved);
      cfg = { ...DEFAULTS, ...parsed };
    }
  } catch (e) { /* ignore */ }
  applySettingsToUI();
}

function saveSettingsToStorage() {
  try {
    localStorage.setItem("krish-config", JSON.stringify(cfg));
  } catch (e) { /* ignore */ }
}

function applySettingsToUI() {
  cfgFastModel.value = cfg.fastModel;
  cfgThinkingModel.value = cfg.thinkingModel;
  cfgVoice.value = cfg.voice;
  cfgWakeWord.checked = cfg.wakeWord;
  cfgToggleMode.checked = cfg.toggleMode;
  cfgContinuous.checked = cfg.continuousMode;
  cfgThreshold.value = cfg.threshold;
  cfgThresholdVal.textContent = cfg.threshold.toFixed(2);
  cfgWakeSensitivity.value = cfg.wakeSensitivity || "0.5";
  cfgVisionEnabled.checked = cfg.visionEnabled;
  cfgVisionOnDemand.checked = cfg.visionOnDemand;
}

function applySettingsFromUI() {
  cfg.fastModel = cfgFastModel.value.trim();
  cfg.thinkingModel = cfgThinkingModel.value.trim();
  cfg.voice = cfgVoice.value;
  cfg.wakeWord = cfgWakeWord.checked;
  cfg.toggleMode = cfgToggleMode.checked;
  cfg.continuousMode = cfgContinuous.checked;
  cfg.threshold = parseFloat(cfgThreshold.value);
  cfg.wakeSensitivity = cfgWakeSensitivity.value;
  cfg.visionEnabled = cfgVisionEnabled.checked;
  cfg.visionOnDemand = cfgVisionOnDemand.checked;
  saveSettingsToStorage();
}

// ─── WebSocket Message Handler ──────────────────────────────────
function handleMessage(msg) {
  switch (msg.type) {
    case "status":
      setStatus(msg.state);
      if (msg.model) setModelBadge(msg.model);
      if (msg.state === "thinking") {
        latencyStart = performance.now();
      }
      if (msg.state === "idle" || msg.state === "speaking" || msg.state === "wake_listening") {
        if (latencyStart) {
          const ms = (performance.now() - latencyStart).toFixed(0);
          footerLatency.textContent = `LATENCY:${ms}ms`;
          latencyStart = 0;
        }
      }
      break;

    case "interim":
      userText.textContent = msg.text + " ▍";
      interimLine.style.display = "flex";
      interimText.textContent = msg.text;
      break;

    case "transcript":
      userText.textContent = msg.text;
      interimLine.style.display = "none";
      break;

    case "wake_detected":
      setStatus("listening");
      userText.textContent = "Wake word detected — listening...";
      // Send vision frame on wake
      if (cfg.visionEnabled && vision.onDemand) {
        vision.sendOnDemandFrame(ws);
      }
      break;

    case "resume_wake_listen":
      setStatus("wake_listening");
      userText.textContent = "Awaiting input...";
      krishLine.style.display = "none";
      break;

    case "response_text":
      krishText.textContent = msg.text;
      krishLine.style.display = "flex";
      addToHistory(
        userText.textContent || "(audio input)",
        msg.text
      );
      break;

    case "response_audio":
      if (msg.data) {
        setStatus("speaking");
        playAudioFromBase64(msg.data, msg.format || "wav").then(() => {
          if (state === "speaking") {
            if (wakeMode) {
              setStatus("wake_listening");
              userText.textContent = "Awaiting input...";
              krishLine.style.display = "none";
            } else {
              setStatus("idle");
              if (cfg.continuousMode) {
                setTimeout(() => startRecording(), 400);
              }
            }
          }
        });
      }
      break;

    case "error":
      showToast("ERROR: " + msg.message);
      if (wakeMode) {
        setStatus("wake_listening");
      } else {
        setStatus("idle");
      }
      break;

    case "pong":
      break;
  }
}

function handleAudioResponse(arrayBuffer) {
  showToast("AUDIO RESPONSE");
}

// ─── History ────────────────────────────────────────────────────
function addToHistory(userMsg, krishMsg) {
  const entry = {
    user: userMsg,
    krish: krishMsg,
    timestamp: new Date().toLocaleTimeString(),
  };
  conversationHistory.push(entry);
  renderHistory();
}

function renderHistory() {
  historyList.innerHTML = conversationHistory
    .map(
      (e) => `
      <div class="history-entry">
        <div class="history-user">${escHtml(e.user)}</div>
        <div class="history-krish">${escHtml(e.krish)}</div>
        <span class="history-timestamp">${e.timestamp}</span>
      </div>`
    )
    .join("");
  historyList.scrollTop = historyList.scrollHeight;
}

function escHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

// ─── Audio Processing ───────────────────────────────────────────
let recorder = null;
let isRecording = false;

async function startRecording() {
  if (isRecording) return;
  try {
    recorder = new AudioRecorder();
    ws.sendJson({ type: "audio_start" });
    await recorder.start((chunk) => {
      ws.sendAudioChunk(chunk);
    });
    isRecording = true;
    micBtn.className = "mic-btn active";
    micHint.textContent = "RECORDING...";
    setStatus("listening");
    interimLine.style.display = "none";
    if (cfg.continuousMode) {
      recorder.startVAD(() => {
        if (isRecording) stopRecording();
      });
    }
  } catch (e) {
    showToast("Mic access denied");
    console.error(e);
  }
}

async function stopRecording() {
  if (!isRecording || !recorder) return;
  isRecording = false;
  recorder.stopVAD();
  recorder.stop();
  recorder = null;
  // Send vision frame on demand if enabled
  if (cfg.visionEnabled && vision.onDemand) {
    vision.sendOnDemandFrame(ws);
  }
  ws.sendJson({ type: "audio_end" });
  micBtn.className = "mic-btn idle";
  micHint.textContent = cfg.continuousMode ? "LISTENING..." : "CLICK TO TALK";
}

// ─── Wake Word Mode ─────────────────────────────────────────────
async function startWakeStreaming() {
  if (wakeStreamer) return;
  try {
    wakeStreamer = new WakeWordStreamer();
    setStatus("wake_listening");
    userText.textContent = "Awaiting input...";
    ws.sendJson({
      type: "enter_wake_mode",
      sensitivity: parseFloat(cfg.wakeSensitivity || "0.5"),
    });
    await wakeStreamer.start((pcmBuffer) => {
      ws.sendBinary(pcmBuffer);
    });
    wakeMode = true;
    micBtn.style.display = "none";
    showToast("WAKE WORD ACTIVE");
  } catch (e) {
    showToast("Wake stream failed: " + e.message);
    wakeMode = false;
    setStatus("idle");
    micBtn.style.display = "flex";
  }
}

function stopWakeStreaming() {
  if (wakeStreamer) {
    wakeStreamer.stop();
    wakeStreamer = null;
  }
  wakeMode = false;
  ws.sendJson({ type: "exit_wake_mode" });
  micBtn.style.display = "flex";
  setStatus("idle");
  userText.textContent = "Awaiting input...";
  showToast("WAKE WORD OFF");
}

// ─── Vision Init ────────────────────────────────────────────────
function initVision() {
  if (!cfg.visionEnabled) {
    vision.stopAll();
    visionPanel.style.display = "none";
    ws.sendJson({ type: "vision_config", enabled: false });
    return;
  }

  visionPanel.style.display = "flex";
  ws.sendJson({
    type: "vision_config",
    enabled: true,
    source: vision.screenActive ? "screen" : "webcam",
  });
  vision.startCapturing(ws);
}

btnToggleWebcam.addEventListener("click", async () => {
  if (vision.webcamActive) {
    vision.stopWebcam();
    ws.sendJson({ type: "vision_config", source: vision.screenActive ? "screen" : "webcam" });
  } else {
    await vision.startWebcam();
    if (vision.screenActive) vision.stopScreen();
    ws.sendJson({ type: "vision_config", source: "webcam" });
  }
});

btnToggleScreen.addEventListener("click", async () => {
  if (vision.screenActive) {
    vision.stopScreen();
    ws.sendJson({ type: "vision_config", source: vision.webcamActive ? "webcam" : "webcam" });
  } else {
    await vision.startScreen();
    if (vision.webcamActive) vision.stopWebcam();
    ws.sendJson({ type: "vision_config", source: "screen" });
  }
});

btnVisionMode.addEventListener("click", () => {
  vision.onDemand = !vision.onDemand;
  cfg.visionOnDemand = vision.onDemand;
  btnVisionMode.classList.toggle("active");
  btnVisionMode.textContent = vision.onDemand ? "ON DEMAND" : "STREAMING";
  if (!vision.onDemand) {
    vision.captureInterval = 500;
    vision.startCapturing(ws);
  } else {
    vision.stopCapturing();
  }
});

// ─── Init ───────────────────────────────────────────────────────
const matrix = new MatrixRain(matrixCanvas);
const reactor = new ArcReactor(reactorCanvas);
const ws = new WSClient();
const vision = new VisionCapture();

function init() {
  loadSettings();

  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${proto}//${location.host}/ws`;
  ws.connect(wsUrl);

  // Start wake word streaming if enabled
  ws.ws.onopen = () => {
    showToast("CONNECTED");
    if (cfg.wakeWord) {
      setTimeout(() => startWakeStreaming(), 500);
    } else {
      setStatus("idle");
    }
    if (cfg.visionEnabled) {
      initVision();
    }
  };

  // Reconnect wake word
  const origReconnect = ws.scheduleReconnect.bind(ws);
  ws.scheduleReconnect = (url) => {
    if (ws.reconnectTimer) clearTimeout(ws.reconnectTimer);
    ws.reconnectTimer = setTimeout(() => {
      ws.connect(url);
      const oldOnOpen = ws.ws.onopen;
      ws.ws.onopen = () => {
        if (oldOnOpen) oldOnOpen();
        if (cfg.wakeWord) {
          setTimeout(() => startWakeStreaming(), 500);
        }
        if (cfg.visionEnabled) {
          setTimeout(() => initVision(), 600);
        }
      };
    }, 3000);
  };

  // Mic button
  micBtn.addEventListener("mousedown", (e) => {
    e.preventDefault();
    if (cfg.toggleMode) {
      if (isRecording) {
        stopRecording();
      } else {
        startRecording();
      }
    } else {
      startRecording();
    }
  });

  micBtn.addEventListener("mouseup", () => {
    if (!cfg.toggleMode) stopRecording();
  });

  micBtn.addEventListener("mouseleave", () => {
    if (!cfg.toggleMode && isRecording) stopRecording();
  });

  // Touch support
  micBtn.addEventListener("touchstart", (e) => {
    e.preventDefault();
    if (cfg.toggleMode) {
      if (isRecording) {
        stopRecording();
      } else {
        startRecording();
      }
    } else {
      startRecording();
    }
  });

  micBtn.addEventListener("touchend", (e) => {
    e.preventDefault();
    if (!cfg.toggleMode) stopRecording();
  });

  // Keyboard shortcut: Space to toggle
  document.addEventListener("keydown", (e) => {
    if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT") return;
    if (e.code === "Space" && !e.repeat) {
      e.preventDefault();
      if (isRecording) {
        stopRecording();
      } else {
        startRecording();
      }
    }
  });

  // Panels
  btnHistory.addEventListener("click", () => {
    historyPanel.classList.toggle("open");
    settingsPanel.classList.remove("open");
  });
  btnCloseHistory.addEventListener("click", () => historyPanel.classList.remove("open"));

  btnSettings.addEventListener("click", () => {
    settingsPanel.classList.toggle("open");
    historyPanel.classList.remove("open");
    applySettingsToUI();
  });
  btnCloseSettings.addEventListener("click", () => settingsPanel.classList.remove("open"));

  btnClearHistory.addEventListener("click", () => {
    conversationHistory = [];
    renderHistory();
    showToast("HISTORY CLEARED");
  });

  btnSaveSettings.addEventListener("click", () => {
    const wasWake = cfg.wakeWord;
    const wasVision = cfg.visionEnabled;
    applySettingsFromUI();
    settingsPanel.classList.remove("open");
    showToast("SETTINGS SAVED");
    if (cfg.wakeWord && !wasWake) {
      startWakeStreaming();
    } else if (!cfg.wakeWord && wasWake) {
      stopWakeStreaming();
    }
    if (cfg.visionEnabled && !wasVision) {
      initVision();
    } else if (!cfg.visionEnabled && wasVision) {
      vision.stopAll();
      visionPanel.style.display = "none";
      ws.sendJson({ type: "vision_config", enabled: false });
    }
    // Send model config to server for hot-reload
    ws.sendJson({
      type: "config_update",
      fast_model: cfg.fastModel,
      thinking_model: cfg.thinkingModel,
      voice: cfg.voice,
      threshold: cfg.threshold,
      wake_sensitivity: parseFloat(cfg.wakeSensitivity || "0.5"),
    });
  });

  btnResetSettings.addEventListener("click", () => {
    const wasWake = cfg.wakeWord;
    const wasVision = cfg.visionEnabled;
    cfg = { ...DEFAULTS };
    applySettingsToUI();
    saveSettingsToStorage();
    showToast("SETTINGS RESET");
    if (cfg.wakeWord && !wasWake) {
      startWakeStreaming();
    } else if (!cfg.wakeWord && wasWake) {
      stopWakeStreaming();
    }
    if (cfg.visionEnabled && !wasVision) {
      initVision();
    } else if (!cfg.visionEnabled && wasVision) {
      vision.stopAll();
      visionPanel.style.display = "none";
      ws.sendJson({ type: "vision_config", enabled: false });
    }
    ws.sendJson({
      type: "config_update",
      fast_model: DEFAULTS.fastModel,
      thinking_model: DEFAULTS.thinkingModel,
      voice: DEFAULTS.voice,
      threshold: DEFAULTS.threshold,
      wake_sensitivity: parseFloat(DEFAULTS.wakeSensitivity || "0.5"),
    });
  });

  cfgThreshold.addEventListener("input", () => {
    cfgThresholdVal.textContent = parseFloat(cfgThreshold.value).toFixed(2);
  });

  // Animation loop
  let animTime = 0;
  function animate(t) {
    animTime = t;
    matrix.draw(t);
    reactor.draw(t, state);

    // Update reactor amplitude from mic or audio
    if (state === "wake_listening" && wakeStreamer && wakeStreamer.getAnalyser()) {
      const amp = getMicAmplitude(wakeStreamer.getAnalyser());
      reactor.setAmplitude(amp);
    } else if (state === "listening" && recorder && recorder.getAnalyser()) {
      const amp = getMicAmplitude(recorder.getAnalyser());
      reactor.setAmplitude(amp);
    } else if (state === "speaking") {
      const amp = getAudioAmplitude();
      reactor.setAmplitude(amp);
    } else {
      reactor.setAmplitude(0);
    }

    requestAnimationFrame(animate);
  }

  requestAnimationFrame(animate);

  // Periodic ping
  setInterval(() => ws.sendPing(), 30000);

  // Load font check
  document.fonts.ready.then(() => {
    showToast("KRISH ONLINE");
  });
}

document.addEventListener("DOMContentLoaded", init);
