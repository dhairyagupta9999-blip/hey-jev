"""Speech-to-Text worker using faster-whisper (small.en, CPU int8)."""
import time
from faster_whisper import WhisperModel
from config import WHISPER_MODEL, NO_SPEECH_MAX

_MODEL = None

def get_whisper_model():
    global _MODEL
    if _MODEL is None:
        print("  [stt] Loading Whisper model (small.en, cpu, int8)...")
        _MODEL = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
        print("  [stt] Whisper model loaded.")
    return _MODEL

def transcribe_audio(audio, prompt=None, drop_noise=False) -> tuple[str, int]:
    """Transcribe audio chunk. Returns (text, latency_ms)."""
    t0 = time.time()
    model = get_whisper_model()
    segs, _ = model.transcribe(
        audio,
        language="en",
        beam_size=1,
        vad_filter=True,
        initial_prompt=prompt
    )
    segs = [s for s in segs if not drop_noise or s.no_speech_prob <= NO_SPEECH_MAX]
    text = " ".join(s.text.strip() for s in segs).strip()
    latency_ms = int((time.time() - t0) * 1000)
    return text, latency_ms
