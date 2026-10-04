"""Speech-to-Text worker using faster-whisper (small.en, CPU int8)."""
import time
import os
import psutil
import numpy as np
from faster_whisper import WhisperModel
from config import WHISPER_MODEL, NO_SPEECH_MAX, SAMPLE_RATE

_MODEL = None

def get_cpu_threads() -> int:
    """Choose optimal CPU threads to avoid hyperthreading contention on CPU."""
    try:
        physical = psutil.cpu_count(logical=False)
        return max(1, min(physical or 2, 4))
    except Exception:
        return 2

def get_whisper_model():
    global _MODEL
    if _MODEL is None:
        threads = get_cpu_threads()
        print(f"  [stt] Loading Whisper model ({WHISPER_MODEL}, cpu, int8, cpu_threads={threads})...")
        _MODEL = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8", cpu_threads=threads)
        print("  [stt] Whisper model loaded.")
    return _MODEL

def warmup_whisper():
    """Run Whisper model once at startup on a short silent buffer so the first real turn is not slow."""
    t0 = time.time()
    model = get_whisper_model()
    try:
        warm_buf = np.zeros(SAMPLE_RATE, dtype=np.float32)
        list(model.transcribe(warm_buf, language="en", beam_size=1, vad_filter=True)[0])
        dur = int((time.time() - t0) * 1000)
        print(f"  [stt] Whisper model warmed up ({dur}ms).")
    except Exception as exc:
        print(f"  [stt] Whisper warmup warning: {exc}")

def trim_silence(audio: np.ndarray, threshold: float = 0.01, frame_ms: int = 50, margin_ms: int = 150) -> np.ndarray:
    """Trim leading and trailing silence from audio buffer using energy (RMS)."""
    if len(audio) == 0:
        return audio
    frame_len = int(SAMPLE_RATE * frame_ms / 1000)
    margin = int(SAMPLE_RATE * margin_ms / 1000)
    if len(audio) < frame_len:
        return audio
    rms = [np.sqrt(np.mean(audio[i:i + frame_len] ** 2)) for i in range(0, len(audio) - frame_len + 1, frame_len)]
    active = [i for i, r in enumerate(rms) if r > threshold]
    if not active:
        return audio
    start = max(0, active[0] * frame_len - margin)
    end = min(len(audio), (active[-1] + 1) * frame_len + margin)
    return audio[start:end]

def transcribe_audio(audio, prompt=None, drop_noise=False) -> tuple[str, int]:
    """Transcribe audio chunk. Returns (text, latency_ms)."""
    t0 = time.time()
    audio_secs = len(audio) / float(SAMPLE_RATE) if len(audio) else 0.0
    trimmed_audio = trim_silence(audio)
    trimmed_secs = len(trimmed_audio) / float(SAMPLE_RATE) if len(trimmed_audio) else 0.0

    model = get_whisper_model()
    segs, _ = model.transcribe(
        trimmed_audio,
        language="en",
        beam_size=1,
        best_of=1,
        vad_filter=True,
        initial_prompt=prompt,
        without_timestamps=True,
        condition_on_previous_text=False
    )
    segs = [s for s in segs if not drop_noise or s.no_speech_prob <= NO_SPEECH_MAX]
    text = " ".join(s.text.strip() for s in segs).strip()
    latency_ms = int((time.time() - t0) * 1000)
    print(f"  [stt] {latency_ms}ms ({audio_secs:.2f}s audio, trimmed to {trimmed_secs:.2f}s)")
    return text, latency_ms

