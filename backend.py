"""Decision backend abstraction for Hey Jev.

Supports:
- "jev": TypeSafe hosted System 1 API (default parity target).
- "laya": Local open-weight Laya decision model running non-autoregressively in-process on CPU.
"""
import os
import time
import json
import threading
from typing import Dict, Any, Tuple, Optional
import requests

from config import LOG_FILE
from secrets_store import get_secret
from logger import trace_line

class DecisionBackend:
    """Abstract base interface for decision backends."""
    name: str = "base"
    default_gate: float = 0.65

    def decide(self, questions: dict, utterance: str) -> Tuple[Dict[str, Tuple[Any, float]], int, float]:
        """Evaluate a question battery against an utterance.
        
        Args:
            questions: Dictionary defining the question battery.
            utterance: The user's input phrase.
            
        Returns:
            answers: Mapping of question_id -> (value, confidence)
            latency_ms: Execution time in milliseconds
            cost: Estimated cost in USD
        """
        raise NotImplementedError


class JevBackend(DecisionBackend):
    """TypeSafe hosted System 1 Jev decision backend."""
    name: str = "jev"
    default_gate: float = 0.65
    ENDPOINT: str = "https://api.typesafe.ai/v1/systemone"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or get_secret("TYPESAFE_API_KEY")

    def reload_key(self):
        self.api_key = get_secret("TYPESAFE_API_KEY")

    def decide(self, questions: dict, utterance: str) -> Tuple[Dict[str, Tuple[Any, float]], int, float]:
        t0 = time.time()
        if not self.api_key:
            self.reload_key()
        
        if not self.api_key:
            raise requests.exceptions.HTTPError(
                "Missing TypeSafe API key. Set TYPESAFE_API_KEY in .env or Settings.",
                response=None
            )

        resp = requests.post(
            self.ENDPOINT,
            json={"model": "jev-latest", "state": utterance, "questions": questions},
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30
        )
        resp.raise_for_status()
        data = resp.json()

        ans = {}
        for k, a in data["answers"].items():
            if a["type"] == "noul":
                val = a["noul"] >= 0.5
                conf = max(a["noul"], 1.0 - a["noul"])
                ans[k] = (val, conf)
            elif a["type"] == "score":
                score_int = int(round(a["score"]))
                legend = a.get("legend", {})
                val = legend.get(str(score_int), str(score_int))
                ans[k] = (val, a.get("confidence", 0.0))
            else:
                ans[k] = (a.get("choice", "none"), a.get("confidence", 0.0))

        cost = data.get("usage", {}).get("input_tokens", 0) * 0.042 / 1e6
        latency_ms = int((time.time() - t0) * 1000)
        return ans, latency_ms, cost


class LayaBackend(DecisionBackend):
    """Local open-weight Laya decision backend running non-autoregressively on CPU."""
    name: str = "laya"
    default_gate: float = 0.45  # Calibrated threshold for Laya's normalized probabilities

    def __init__(self, checkpoint: Optional[str] = None, fallback_to_jev: bool = True):
        self.checkpoint = checkpoint or os.getenv("LAYA_CHECKPOINT", "convaiinnovations/laya")
        self.fallback_to_jev = fallback_to_jev
        self._router = None
        self._loading = False
        self._load_error = None
        self._lock = threading.Lock()
        self._jev_fallback = None

    def preload_async(self):
        """Preload the model in a background thread so the main/event loop is never blocked."""
        t = threading.Thread(target=self._ensure_loaded, daemon=True, name="LayaPreloadThread")
        t.start()

    def _ensure_loaded(self):
        with self._lock:
            if self._router is not None:
                return self._router
            if self._load_error is not None:
                return None
            try:
                t0 = time.time()
                from laya import Router
                model_name = "english" if self.checkpoint in (None, "english", "convaiinnovations/laya") else self.checkpoint
                self._router = Router(device="cpu", default=model_name, preload=True)
                load_time = time.time() - t0
                print(f"[laya] initialized router for {model_name!r} in {load_time:.2f}s on CPU")
                return self._router
            except Exception as exc:
                self._load_error = exc
                err_msg = f"[FALLBACK] Laya failed to load checkpoint {self.checkpoint!r}: {exc}. Falling back to Jev."
                print(err_msg)
                trace_line(f"  {err_msg}")
                return None

    def _get_jev_fallback(self) -> JevBackend:
        if self._jev_fallback is None:
            self._jev_fallback = JevBackend()
        return self._jev_fallback

    def calibrate_confidence(self, raw_prob: float, num_choices: int) -> float:
        """Calibrate uniform prior probability to [0.0, 1.0] scale."""
        if num_choices <= 1:
            return raw_prob
        # (N * p - 1) / (N - 1)
        scaled = (num_choices * raw_prob - 1.0) / (num_choices - 1.0)
        return max(0.0, min(1.0, scaled))

    def decide(self, questions: dict, utterance: str) -> Tuple[Dict[str, Tuple[Any, float]], int, float]:
        router = self._ensure_loaded()
        if router is None:
            if self.fallback_to_jev:
                trace_line(f"  [fallback]: routing turn to Jev backend due to Laya load error ({self._load_error})")
                return self._get_jev_fallback().decide(questions, utterance)
            raise RuntimeError(f"Laya failed to load: {self._load_error}")

        t0 = time.time()
        try:
            # Predict in a single forward pass over all questions
            result = router.predict(state=utterance, questions=questions)
            latency_ms = int((time.time() - t0) * 1000)
            
            raw_answers = result.get("answers", {})
            ans = {}
            for qid, qdef in questions.items():
                res = raw_answers.get(qid, {})
                qtype = qdef.get("type", "choice")
                
                if qtype == "noul":
                    noul_val = res.get("noul", 0.0)
                    val = noul_val >= 0.5
                    conf = max(noul_val, 1.0 - noul_val)
                    ans[qid] = (val, conf)
                elif qtype == "score":
                    score_val = res.get("score", 0.0)
                    criteria = qdef.get("criteria", [])
                    idx = int(round(score_val))
                    idx = max(0, min(len(criteria) - 1, idx))
                    label = criteria[idx] if criteria else str(idx)
                    ans[qid] = (label, res.get("confidence", 0.5))
                else:
                    choice = res.get("choice", "none")
                    prob = res.get("confidence", res.get("probability", 0.0))
                    # Number of choices in criteria
                    criteria = qdef.get("criteria", {})
                    num_c = len(criteria) if isinstance(criteria, dict) else len(criteria or [])
                    calibrated = self.calibrate_confidence(prob, num_c)
                    ans[qid] = (choice, calibrated)

            cost = 0.0  # Local inference has zero API cost
            return ans, latency_ms, cost

        except Exception as exc:
            trace_line(f"  [FALLBACK] Laya inference failed: {exc}. Falling back to Jev backend.")
            if self.fallback_to_jev:
                return self._get_jev_fallback().decide(questions, utterance)
            raise exc


# Singleton backends
_BACKENDS = {
    "jev": JevBackend(),
    "laya": LayaBackend()
}

def get_backend(name: Optional[str] = None) -> DecisionBackend:
    """Resolve active decision backend by name or HEYJEV_BACKEND env var (default 'jev')."""
    chosen = (name or os.getenv("HEYJEV_BACKEND", "jev")).lower().strip()
    if chosen not in _BACKENDS:
        print(f"[warning] Unknown backend {chosen!r}, falling back to 'jev'")
        chosen = "jev"
    return _BACKENDS[chosen]
