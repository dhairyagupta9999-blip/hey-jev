"""Audio input (WASAPI capture + VAD) and output (MP3/WAV playback) for Hey Jev."""
import io
import os
import sys
import time
import queue
import threading
import collections
import numpy as np
import sounddevice as sd
import soundfile as sf
from config import SAMPLE_RATE, WAKE_CHIME, DICTATE_CHIME, TIMER_CHIME

MIC_LEVELS = collections.deque(maxlen=40)  # RMS loudness for dictation bubble

# --------------------------------------------------------------------------- Output: MP3 / WAV Player
def load_audio_file(path):
    """Load any audio file (WAV, MP3, FLAC, OGG) into (float32 numpy array, sample_rate)."""
    try:
        data, sr = sf.read(path, dtype="float32")
        return data, sr
    except Exception:
        # Fallback to PyAV if soundfile does not have mp3 support on this build
        import av
        container = av.open(path)
        stream = container.streams.audio[0]
        sr = stream.rate
        frames = []
        for frame in container.decode(stream):
            # Convert to float32
            arr = frame.to_ndarray()
            if arr.dtype == np.int16:
                arr = arr.astype(np.float32) / 32768.0
            elif arr.dtype == np.int32:
                arr = arr.astype(np.float32) / 2147483648.0
            frames.append(arr)
        if not frames:
            raise RuntimeError(f"Could not decode audio from {path}")
        data = np.concatenate(frames, axis=-1)
        if data.ndim == 2:
            data = data.T  # shape (samples, channels)
            if data.shape[1] == 1:
                data = data[:, 0]
        return data, sr


def play_audio(path, blocking=True):
    """Play a WAV or MP3 audio file cleanly via sounddevice without winsound."""
    if not os.path.exists(path):
        print(f"  [audio_player] File not found: {path}")
        return
    data, sr = load_audio_file(path)
    sd.play(data, sr)
    if blocking:
        sd.wait()


def play_chime(kind):
    """Play wake, pop, or timer chimes."""
    chimes = {
        "wake": WAKE_CHIME,
        "pop": DICTATE_CHIME,
        "timer": TIMER_CHIME,
    }
    path = chimes.get(kind)
    if path and os.path.exists(path):
        threading.Thread(target=play_audio, args=(path, False), daemon=True).start()


# --------------------------------------------------------------------------- Input: WASAPI Capture + VAD
class Recorder:
    BLOCK = 1600  # 100ms at 16kHz

    def __init__(self, mic=""):
        self.frames = []
        self.on = False
        self.wake = False
        self.paused = False
        self.dictating = False
        self.segments = queue.Queue()
        self.noise = 0.005
        self._reset_segment()
        self.mic_lock = threading.Lock()
        self.stream = self._open(mic)

    def _open(self, mic):
        kwargs = {
            "samplerate": SAMPLE_RATE,
            "channels": 1,
            "dtype": "float32",
            "blocksize": self.BLOCK,
            "callback": self._cb,
        }
        if mic:
            try:
                return sd.InputStream(device=mic, **kwargs)
            except Exception as exc:
                print(f"\n[mic {mic!r} not available, using default: {exc}]")
        return sd.InputStream(**kwargs)

    def set_device(self, mic):
        """Swap to another microphone, carrying on listening if active."""
        with self.mic_lock:
            was_active = self.stream.active
            self.stream.close()
            self.stream = self._open(mic)
            if was_active:
                self._reset_segment()
                self.stream.start()
        print(f"\n[mic: {mic or 'system default'}]")

    def sync_mic(self):
        """Only keep WASAPI stream active when listening/dictating/recording."""
        with self.mic_lock:
            needed = self.wake or self.dictating or self.on
            if needed and not self.stream.active:
                self._reset_segment()
                self.stream.start()
            elif not needed and self.stream.active:
                self.stream.stop()

    def _reset_segment(self):
        self.speech = []
        self.silent = 0
        self.preroll = collections.deque(maxlen=3)

    def _cb(self, indata, frames, time_info, status):
        if self.on:
            self.frames.append(indata.copy())
        if not (self.wake or self.dictating) or self.paused:
            if self.speech:
                self._reset_segment()
            return

        block = indata[:, 0].copy()
        rms = float(np.sqrt(np.mean(block ** 2)))
        if self.dictating:
            MIC_LEVELS.append(rms)

        # Dynamic room-noise threshold
        loud = rms > max(self.noise * 3, 0.01)
        if not self.speech:
            if loud:
                self.speech = list(self.preroll) + [block]
                self.silent = 0
            else:
                self.noise = 0.95 * self.noise + 0.05 * rms  # track background noise
                self.preroll.append(block)
            return

        self.speech.append(block)
        self.silent = 0 if loud else self.silent + 1

        # 0.8s pause ends phrase; max 15s (30s during dictation)
        max_blocks = 300 if self.dictating else 150
        if self.silent >= 8 or len(self.speech) >= max_blocks:
            if len(self.speech) - self.silent >= 4:
                self.segments.put(np.concatenate(self.speech))
            self._reset_segment()

    def start(self):
        self.frames = []
        self.on = True
        self.sync_mic()

    def stop(self):
        self.on = False
        audio = np.concatenate(self.frames)[:, 0] if self.frames else np.zeros(0, dtype="float32")
        self.sync_mic()
        return audio
