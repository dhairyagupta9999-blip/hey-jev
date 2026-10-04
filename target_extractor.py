"""Target extractor for open-vocabulary spoken requests (Tier 2).

Extracts intent (open, close, focus, close_all, refresh_apps) and target names
from natural transcripts, stripping polite fillers ("please", "the", "can you").
"""
from __future__ import annotations

import re

# Polite wrappers & filler words
LEADING_FILLERS = re.compile(
    r"^(?:hey\s+jev,?\s*)?(?:please\s+)?(?:can\s+you\s+)?(?:could\s+you\s+)?(?:would\s+you\s+)?(?:just\s+)?",
    re.IGNORECASE
)
TRAILING_FILLERS = re.compile(
    r"(?:\s+please|\s+for\s+me|\s+now|\s+right\s+now)+$",
    re.IGNORECASE
)

# Open / launch intent patterns
OPEN_PATTERNS = [
    re.compile(r"^(?:open|launch|start|run|bring\s+up|fire\s+up)\s+(?:the\s+|an\s+|a\s+)?(.+?)$", re.IGNORECASE),
    re.compile(r"^(?:switch\s+to|jump\s+to|go\s+to)\s+(?:the\s+)?(.+?)$", re.IGNORECASE),
]

# Close / quit intent patterns
CLOSE_PATTERNS = [
    re.compile(r"^(?:close|quit|kill|exit|terminate|shut\s+down)\s+(?:the\s+|an\s+|a\s+)?(.+?)$", re.IGNORECASE),
]

# Focus intent patterns
FOCUS_PATTERNS = [
    re.compile(r"^(?:focus|bring\s+to\s+front|show)\s+(?:the\s+)?(.+?)$", re.IGNORECASE),
]

# Close all / close everything
CLOSE_ALL_PATTERN = re.compile(
    r"^(?:close\s+everything|close\s+all\s+windows|close\s+all\s+apps|quit\s+all|kill\s+all)$",
    re.IGNORECASE
)

# App refresh
REFRESH_APPS_PATTERN = re.compile(
    r"^(?:refresh\s+apps|refresh\s+the\s+app\s+index|update\s+apps\s+list|reload\s+apps)$",
    re.IGNORECASE
)

def clean_transcript(text: str) -> str:
    """Strip wake prefix, polite fillers, and extraneous punctuation."""
    t = text.strip()
    t = LEADING_FILLERS.sub("", t).strip()
    t = TRAILING_FILLERS.sub("", t).strip()
    t = re.sub(r"[?!.,]+$", "", t).strip()
    return t

def extract_target(text: str) -> tuple[str | None, str | None]:
    """Extract (action, target) from spoken transcript.
    
    Actions:
      - 'open'
      - 'close'
      - 'focus'
      - 'close_all'
      - 'refresh_apps'
    Returns (None, None) if no pattern matches.
    """
    cleaned = clean_transcript(text)
    if not cleaned:
        return None, None

    if REFRESH_APPS_PATTERN.match(cleaned):
        return "refresh_apps", None

    if CLOSE_ALL_PATTERN.match(cleaned):
        return "close_all", "all"

    for pat in OPEN_PATTERNS:
        m = pat.match(cleaned)
        if m:
            tgt = m.group(1).strip()
            # Clean leading 'app' word if phrased as e.g. "open the app Spotify"
            tgt = re.sub(r"^app\s+", "", tgt, flags=re.IGNORECASE).strip()
            # If phrased as "switch to X", classify as focus
            action = "focus" if cleaned.lower().startswith("switch to") else "open"
            return action, tgt

    for pat in CLOSE_PATTERNS:
        m = pat.match(cleaned)
        if m:
            tgt = m.group(1).strip()
            tgt = re.sub(r"^app\s+", "", tgt, flags=re.IGNORECASE).strip()
            if tgt.lower() in ("everything", "all", "all windows", "all apps"):
                return "close_all", "all"
            return "close", tgt

    for pat in FOCUS_PATTERNS:
        m = pat.match(cleaned)
        if m:
            tgt = m.group(1).strip()
            return "focus", tgt

    return None, None
