"""Wake word detection abstraction for Hey Jev on Windows.

Supports:
1. Baseline 'whisper': Whisper-prefix regex gate on speech transcripts.
2. 'openwakeword': Low-CPU local streaming ONNX wake word engine (dscripka/openWakeWord).
"""
import os
import re
import numpy as np
from typing import Optional, Tuple, Dict, Any
from config import NAMES, SAMPLE_RATE, APPDATA_DIR

# Baseline Whisper prefix regex
DEFAULT_WAKE_REGEX = re.compile(
    rf"(?:(?:^\W*a|\b(?:hey|hi|hay|okay|ok))\W+(?:{NAMES})\b|^\W*(?:{NAMES})\s*,)\W*",
    re.I
)

class WakeDetector:
    """Base class for wake word detectors."""
    def detect_utterance(self, text: str) -> Optional[re.Match]:
        """Check text transcript for wake trigger (for whisper-prefix detectors)."""
        return None

    def feed_audio(self, audio_chunk: np.ndarray) -> Tuple[bool, str, float]:
        """Feed an audio chunk (16kHz mono). Returns (detected, model_name, score)."""
        return False, "", 0.0

    def reset(self):
        pass


class WhisperPrefixDetector(WakeDetector):
    """Baseline Whisper-prefix regex detector."""
    def __init__(self, regex: Optional[re.Pattern] = None):
        self.regex = regex or DEFAULT_WAKE_REGEX

    def detect_utterance(self, text: str) -> Optional[re.Match]:
        return self.regex.search(text)


class OpenWakeWordDetector(WakeDetector):
    """Low-CPU streaming wake detector using openWakeWord ONNX runtime."""
    def __init__(self, model_path: Optional[str] = None, threshold: float = 0.5):
        self.threshold = threshold
        self.model_path = model_path
        self._model = None
        self._load_model()

    def _load_model(self):
        try:
            import openwakeword
            from openwakeword.model import Model

            # Check if custom hey_jev model exists in APPDATA or local dir
            custom_candidate = self.model_path or os.path.join(APPDATA_DIR, "models", "hey_jev.onnx")
            if os.path.exists(custom_candidate):
                fw = "tflite" if custom_candidate.endswith(".tflite") else "onnx"
                self._model = Model(wakeword_models=[custom_candidate], inference_framework=fw)
                self.model_name = os.path.splitext(os.path.basename(custom_candidate))[0]
            else:
                models = openwakeword.get_pretrained_model_paths()
                if models:
                    first = models[0]
                    fw = "tflite" if first.endswith(".tflite") else "onnx"
                    self._model = Model(wakeword_models=[first], inference_framework=fw)
                    self.model_name = os.path.splitext(os.path.basename(first))[0]
                else:
                    self._model = Model()
                    self.model_name = "openwakeword_default"
        except Exception as e:
            print(f"[OpenWakeWord] Failed to initialize openWakeWord: {e}. Falling back to Whisper prefix.")
            self._model = None

    @property
    def is_available(self) -> bool:
        return self._model is not None

    def feed_audio(self, audio_chunk: np.ndarray) -> Tuple[bool, str, float]:
        """Accepts 16kHz audio chunk (float32 or int16), feeds to openWakeWord."""
        if not self._model:
            return False, "", 0.0

        try:
            if audio_chunk.dtype == np.float32:
                # Convert float32 [-1, 1] to int16
                audio_int16 = (audio_chunk * 32767).astype(np.int16)
            else:
                audio_int16 = audio_chunk.astype(np.int16)

            # openWakeWord expects 1280 samples (80ms at 16kHz) per step
            predictions = self._model.predict(audio_int16)
            for name, score in predictions.items():
                if score >= self.threshold:
                    self.reset()
                    return True, name, float(score)
        except Exception as e:
            pass

        return False, "", 0.0

    def reset(self):
        if self._model:
            try:
                self._model.reset()
            except Exception:
                pass


def get_wake_detector(backend: str = "whisper", model_path: Optional[str] = None, threshold: float = 0.5) -> WakeDetector:
    """Factory creating the configured wake word detector."""
    if backend.lower() == "openwakeword":
        det = OpenWakeWordDetector(model_path=model_path, threshold=threshold)
        if det.is_available:
            return det
        # Graceful fallback to baseline
        return WhisperPrefixDetector()
    return WhisperPrefixDetector()
