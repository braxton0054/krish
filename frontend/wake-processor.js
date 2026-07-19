// AudioWorklet processor: downsamples input to 16kHz and posts PCM Int16 frames
class WakeProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.targetRate = 16000;
    this.sampleRateIn = sampleRate; // AudioWorkletGlobalScope.sampleRate
    this.step = this.sampleRateIn / this.targetRate;
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || input.length === 0) return true;
    const channel = input[0];
    if (!channel || channel.length === 0) return true;

    const outLen = Math.floor(channel.length / this.step);
    const pcm = new Int16Array(outLen);
    for (let i = 0; i < outLen; i++) {
      const srcIdx = Math.floor(i * this.step);
      let s = channel[srcIdx];
      // Clamp to [-1, 1] then scale to int16
      s = s < -1 ? -1 : s > 1 ? 1 : s;
      pcm[i] = s * 32767;
    }
    this.port.postMessage(pcm.buffer, [pcm.buffer]);
    return true;
  }
}

registerProcessor("wake-processor", WakeProcessor);
