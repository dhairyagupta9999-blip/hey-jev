"""Record 10 acceptance test clips from the user's microphone for STT benchmarking."""
import os
import sys
import time
import json
import sounddevice as sd
import soundfile as sf
import numpy as np

import stt

SAMPLE_RATE = 16000
RECORD_DURATION = 4.0  # seconds per clip
CLIPS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_clips")

TEST_SENTENCES = [
    "open Spotify",
    "set volume to forty percent",
    "pause Spotify and open Slack",
    "who wrote Hamlet",
    "Hey Jev, dark mode on",
    "mute the volume",
    "set a timer for five minutes",
    "open youtube",
    "lock the screen",
    "next track"
]

def record_clip(duration: float = RECORD_DURATION, samplerate: int = SAMPLE_RATE) -> np.ndarray:
    """Record audio from the default input device at 16 kHz mono float32."""
    num_frames = int(duration * samplerate)
    audio = sd.rec(num_frames, samplerate=samplerate, channels=1, dtype="float32")
    sd.wait()
    return audio[:, 0] if audio.ndim > 1 else audio

def main():
    os.makedirs(CLIPS_DIR, exist_ok=True)
    metadata_path = os.path.join(CLIPS_DIR, "metadata.json")

    print("=" * 70)
    print(" HEY JEV — SPEECH-TO-TEXT BENCHMARK CLIP RECORDER")
    print("=" * 70)
    print(f"Destination: {CLIPS_DIR}")
    print(f"Format: 16 kHz mono float32 WAV (4.0s window per sentence)")
    print(f"Total phrases: {len(TEST_SENTENCES)}")
    print("\nFor each prompt:")
    print(" 1. Press ENTER to start the 3-second countdown.")
    print(" 2. Speak the exact sentence when you see '>>> SPEAK NOW!'.")
    print("=" * 70)

    clips_meta = []

    for idx, sentence in enumerate(TEST_SENTENCES, start=1):
        filename = f"clip_{idx:02d}.wav"
        filepath = os.path.join(CLIPS_DIR, filename)

        print(f"\n[{idx}/{len(TEST_SENTENCES)}] Target phrase:")
        print(f"   \"{sentence}\"")
        try:
            input("Press ENTER when ready to start 3-second countdown...")
        except EOFError:
            pass

        print("Get ready...")
        for count in range(3, 0, -1):
            print(f"  {count}...")
            time.sleep(1.0)

        print(f"\n>>> SPEAK NOW: \"{sentence}\"")
        audio = record_clip(RECORD_DURATION, SAMPLE_RATE)
        print("Done recording. Processing...")

        # Trim silence around utterance
        trimmed = stt.trim_silence(audio)
        if len(trimmed) == 0:
            trimmed = audio

        sf.write(filepath, trimmed, SAMPLE_RATE)
        dur = len(trimmed) / SAMPLE_RATE
        print(f"Saved {filename} ({dur:.2f}s audio)")

        clips_meta.append({
            "index": idx,
            "file": filename,
            "text": sentence,
            "duration_s": round(dur, 2)
        })

    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(clips_meta, f, indent=2)

    print("\n" + "=" * 70)
    print(f"All {len(TEST_SENTENCES)} clips successfully recorded and saved to {CLIPS_DIR}!")
    print(f"Metadata saved to: {metadata_path}")
    print("Now run 'python benchmark_stt.py' to benchmark faster-whisper vs Whistle.")
    print("=" * 70)

if __name__ == "__main__":
    main()
