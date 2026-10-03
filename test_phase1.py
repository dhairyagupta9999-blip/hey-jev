"""Unit tests for Phase 1 Core Loop on Windows."""
import os
import time
import json

from config import (
    APPDATA_DIR, LOG_FILE, TIMERS_FILE, WAKE_CHIME, DICTATE_CHIME, TIMER_CHIME
)
from secrets_store import get_secret, missing_secrets, save_secret, SERVICE
import audio_io
import timers
import logger
import actions_win

def test_paths_and_appdata():
    assert os.path.exists(APPDATA_DIR)
    assert os.path.exists(WAKE_CHIME)
    assert os.path.exists(DICTATE_CHIME)
    assert os.path.exists(TIMER_CHIME)

def test_audio_loader():
    # Test loading generated sound assets via soundfile/av
    data, sr = audio_io.load_audio_file(WAKE_CHIME)
    assert len(data) > 0
    assert sr > 0
    assert data.dtype.kind == "f"  # float array

def test_timer_durations_and_reminders():
    # Test duration parser
    assert timers.parse_duration("five minutes") == 300
    assert timers.parse_duration("half an hour") == 1800
    assert timers.parse_duration("45 seconds") == 45
    assert timers.parse_duration("2 hours and a half") == 9000

    # Test reminder extraction
    rem = timers.parse_reminder("remind me in 10 minutes to take out the trash")
    assert rem == "take out the trash"

    rem2 = timers.parse_reminder("remind me to call Mom in two hours")
    assert rem2 == "call mom"

def test_monotonic_timers_persistence():
    # Add a 10s timer
    t = timers.add_timer(10, label="Test Timer")
    assert t["secs"] == 10
    assert t["label"] == "Test Timer"

    snaps = timers.timer_snapshot()
    assert len(snaps) >= 1
    assert any("Test timer" in s[0] for s in snaps)

    # Check persistence on disk
    assert os.path.exists(TIMERS_FILE)
    with open(TIMERS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert any(item["label"] == "Test Timer" for item in data)

    # Cancel timer
    timers.cancel_timer(all_timers=True)
    assert len(timers.timer_snapshot()) == 0

def test_logger_trace():
    test_phrase = "test turn for Operation Nightingale"
    logger.trace_heard(test_phrase, stt_ms=120)
    logger.trace_answers({"category": ("mac_command", 0.95)}, gate=0.65)
    logger.trace_decision("jev", 310, 0.000042)
    logger.trace_action("volume_up", None)
    logger.trace_say("Louder it is.")
    logger.trace_fish(0)

    assert os.path.exists(LOG_FILE)
    with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    assert test_phrase in content
    assert "mac_command" in content
    assert "[backend: jev]" in content
    assert "fish cached" in content

def test_volume_actions():
    vol = actions_win.get_volume()
    assert isinstance(vol, int)
    assert 0 <= vol <= 100

if __name__ == "__main__":
    print("Running Phase 1 validation tests...")
    test_paths_and_appdata()
    print("  [PASS] Paths and AppData directories")
    test_audio_loader()
    print("  [PASS] Audio loader (MP3/WAV)")
    test_timer_durations_and_reminders()
    print("  [PASS] Timer duration and reminder regex")
    test_monotonic_timers_persistence()
    print("  [PASS] Monotonic timer and disk persistence")
    test_logger_trace()
    print("  [PASS] Trace logging to Hey Jev.log")
    test_volume_actions()
    print("  [PASS] Windows volume endpoint via pycaw")
    print("\nALL PHASE 1 TESTS PASSED!")
