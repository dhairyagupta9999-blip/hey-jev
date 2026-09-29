"""Dictation from Tatoscription: "Hey Jev, transcribe" records until "stop transcribing", then pastes the text at your cursor."""
import io, os, re, json, time, base64, subprocess
from concurrent.futures import ThreadPoolExecutor
import numpy as np, requests, soundfile as sf

MODEL = "openai/gpt-4o-mini-transcribe"
PROMPT = ("The following is a transcript of a person talking, you can remove and duplicated words and any fillers words. "
          "If its a longer transcript put into paragraphs for better readability.")
CHUNK_SECS = 30  # audio goes off in chunks this long while you talk, so stopping is quick
MAX_SECS = 15 * 60  # stops by itself after this, in case the stop phrase gets missed
HERE = os.path.dirname(os.path.abspath(__file__))
HISTORY = os.path.expanduser("~/Library/Logs/Hey Jev dictation.jsonl")
FAILED_DIR = os.path.expanduser("~/Library/Logs/Hey Jev dictation failed")
START = re.compile(r"^\W*(?:(?:please|can you|could you)\s+)?(?:start\s+)?(?:transcrib\w*|dictat\w*|take notes)"
                   r"(?:\s+(?:this|this meeting|this call|notes|mode|now|please|for me))?\W*$", re.I)

# your own words go in vocabulary.json (gitignored), the example is the fallback
VOCAB_FILE = next(p for p in (os.path.join(HERE, n) for n in ("vocabulary.json", "vocabulary.example.json")) if os.path.exists(p))
with open(VOCAB_FILE) as f:
    VOCAB = [(re.compile(r"\b" + re.escape(alt) + r"\b", re.I), word) for word, alts in json.load(f).items() for alt in alts]


def fix_vocab(text):
    for rx, word in VOCAB:
        text = rx.sub(word, text)
    return text


def strip_prompt(text):
    # gpt-4o transcribers sometimes echo the prompt back, same filter as Tatoscription
    cleaned = text
    for part in (PROMPT, *PROMPT.split(", "), *PROMPT.split(". ")):
        cleaned = re.sub(re.escape(part.strip(" .")), "", cleaned, flags=re.I)
    cleaned = re.sub(r"[ \t]+", " ", cleaned).strip(" ,.")
    return cleaned if cleaned else text


def paste(text):
    subprocess.run(["pbcopy"], input=text.encode(), check=True)  # stays on the clipboard too, in case the paste misses
    time.sleep(0.2)
    # System Events, not pynput: pynput reads the keyboard layout, which crashes the app off the main thread
    subprocess.run(["osascript", "-e", 'tell application "System Events" to keystroke "v" using command down'], check=True)


class Dictation:
    def __init__(self, names, get_key, sample_rate):
        self.stop_rx = re.compile(rf"(?:\b(?:hey|hi|hay|okay|ok)\W+)?(?:\b(?:{names})\W+)?\b(?:stop|end|finish)\W+(?:the\W+)?"
                                  r"(?:transcri|dictat)\w*\W*$", re.I)
        self.get_key, self.rate = get_key, sample_rate
        self.pool = ThreadPoolExecutor(3)
        self.active = False

    def start(self):
        self.active, self.started = True, time.time()
        self.buffer, self.chunks = [], []

    def timed_out(self):
        return self.active and time.time() - self.started > MAX_SECS

    def add(self, audio, heard):
        """Keep this phrase, returns True if it was the stop command."""
        self.buffer.append(audio)
        stop = bool(self.stop_rx.search(heard)) or self.timed_out()
        if stop or sum(map(len, self.buffer)) >= CHUNK_SECS * self.rate:
            self._send()
        return stop

    def _send(self):
        if self.buffer:
            self.chunks.append(self.pool.submit(self._transcribe, np.concatenate(self.buffer)))
            self.buffer = []

    def finish(self):
        """Wait for every chunk and return the finished text."""
        self._send()
        self.active = False
        parts = []
        for chunk in self.chunks:
            try:
                parts.append(chunk.result())
            except Exception as exc:
                print(f"  dictation chunk failed: {exc}")
        text = " ".join(p for p in parts if p)
        text = self.stop_rx.sub("", text).strip(" ,")
        text = fix_vocab(strip_prompt(text)) if text else ""
        if text:
            with open(HISTORY, "a", encoding="utf-8") as f:
                f.write(json.dumps({"time": time.strftime("%Y-%m-%d %H:%M:%S"), "text": text}) + "\n")
        return text

    def _transcribe(self, audio):
        wav = io.BytesIO()
        sf.write(wav, audio, self.rate, format="WAV")
        for attempt in range(3):
            try:
                t = time.time()
                r = requests.post("https://openrouter.ai/api/v1/audio/transcriptions",
                                  headers={"Authorization": f"Bearer {self.get_key()}"},
                                  json={"model": MODEL, "language": "en", "provider": {"options": {"openai": {"prompt": PROMPT}}},  # OpenRouter only passes the prompt on this way
                                        "input_audio": {"data": base64.b64encode(wav.getvalue()).decode(), "format": "wav"}},
                                  timeout=90)
                if not r.ok:
                    print(f"  openrouter said: {r.status_code} {r.text[:200]}")
                r.raise_for_status()
                text = r.json().get("text", "").strip()
                print(f"  dictation chunk {len(audio) / self.rate:.0f}s -> {len(text.split())} words  {int((time.time() - t) * 1000)}ms")
                return text
            except Exception as exc:
                if attempt == 2 or (isinstance(exc, requests.HTTPError) and exc.response.status_code < 500
                                    and exc.response.status_code != 429):
                    os.makedirs(FAILED_DIR, exist_ok=True)  # keep the audio so nothing is lost
                    sf.write(os.path.join(FAILED_DIR, time.strftime("%Y-%m-%d %H-%M-%S") + ".wav"), audio, self.rate)
                    raise
                time.sleep(2 ** attempt)
