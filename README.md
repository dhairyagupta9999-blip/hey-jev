# Hey Jev (Windows 10/11 x64 Port)

> Windows port of [henryklunaris/hey-jev](https://github.com/henryklunaris/hey-jev) by Bhagwat Panwar. Original by Henryk Lunaris (MIT).  
>
> **Referenced Projects, Credits & Licenses**:
> - **Original Repository:** [henryklunaris/hey-jev](https://github.com/henryklunaris/hey-jev) — MIT License (Copyright © 2026 Henryk Lunaris)
> - **hey-laya:** [touhidsiddiqueeraj-bit/hey-laya](https://github.com/touhidsiddiqueeraj-bit/hey-laya) — MIT License (Copyright © 2026 Touhid Siddique Eraj)
> - **home-assistant-laya:** [allenporter/home-assistant-laya](https://github.com/allenporter/home-assistant-laya) — Apache License 2.0 (Copyright © 2026 Allen Porter)
> - **openWakeWord:** [dscripka/openWakeWord](https://github.com/dscripka/openWakeWord) — Apache License 2.0 (Copyright © 2023 David Scripka)

---

A high-performance voice assistant for Windows 10 and 11. Say "Hey Jev" or hold right Alt, state your request, and Hey Jev acts immediately and replies in a natural voice.

- **Local Speech Privacy:** Microphone audio is captured via Windows Audio Session API (WASAPI) and transcribed on-device using local `faster-whisper` (`small.en`, CPU int8, ~250MB, ~0.8s). No audio ever leaves your computer for turn processing.
- **Speculative Fan-out Economics:** One TypeSafe Jev decision call evaluates all questions simultaneously (~$0.00004 per turn). Jev is the default backend; local open-weight Laya is supported alongside it.
- **Compound Action Splitting:** Compound requests ("pause music and open Slack") execute a second targeted decision call scoped to the first and second actions—without LLM overhead.
- **Natural Voice Synthesis:** Fish Audio S2.1 Pro with expressive emotion tags (`[chuckling]`, `[sighing]`). Scripted dialogue pre-renders into `%APPDATA%/HeyJev/cache/tts/` on initial launch for instantaneous playback.
- **Windows-Native Action Layer:** All 33 macOS actions have been ported 1:1 to Windows 10/11 using Win32 API, `pywinauto` (UIA backend), `pycaw` audio endpoint sessions, WinRT System Media Transport Controls (SMTC), and registry theme broadcasts.
- **Native Floating Dictation Bubble:** Frameless, topmost, click-through, per-monitor DPI aware window positioned bottom-centre with a 24-bar live RMS animated waveform.
- **Tray & Background Lifecycle:** Closing the window hides to the Windows notification area (System Tray) while continuing to listen in the background. Explicit quit via system tray menu or `Ctrl+Q`.

---

## Architecture Overview

```
                                  [ User Utterance ]
                                          │
                     ┌────────────────────┴────────────────────┐
                     ▼                                         ▼
            [ Hold Right Alt ]                        [ "Hey Jev" Wake ]
            (Global low-level hook)               (Whisper-prefix / openWakeWord)
                     │                                         │
                     └────────────────────┬────────────────────┘
                                          ▼
                            [ WASAPI Audio Capture ]
                           (sounddevice / 16kHz mono)
                                          │
                                          ▼
                         [ Local faster-whisper (CPU) ]
                            (small.en int8, ~0.8s)
                                          │
                                          ▼
                               [ Decision Engine ]
                       ┌──────────────────┴──────────────────┐
                       ▼                                     ▼
             [ TypeSafe Jev (Default) ]           [ Local Laya (On-Device) ]
           Speculative fan-out battery          Open-weight non-autoregressive
                 (~$0.00004/turn)                      Zero network draw
                       └──────────────────┬──────────────────┘
                                          │
                                          ▼
                          [ Confidence Gate (>= 0.65) ]
                                          │
                                          ▼
                             [ Windows Action Layer ]
    ┌──────────────────────┬──────────────────────┬──────────────────────┐
    ▼                      ▼                      ▼                      ▼
[ App Control ]    [ Volume & Media ]     [ Dark Mode / OS ]     [ Timers & Toast ]
  pywinauto UIA       WinRT SMTC &           HKCU Registry         Monotonic clock
  shell:AppsFolder    pycaw sessions       WM_SETTINGCHANGE       Windows toasts
```

---

## Features & Windows Enhancements

### 1. App Control & Window Management
- **Win32 & UWP Launching:** Seamlessly launches traditional executables and packaged Microsoft Store apps via `shell:AppsFolder` and URI schemes (e.g. `spotify:`, `slack:`, `discord:`).
- **Process-Tree Termination:** When quitting applications that minimize to tray on close (Slack, Discord, Spotify), sends `WM_CLOSE`, waits 1.5 seconds, and terminates the entire process tree to guarantee closure.
- **Window State Control:** Minimize (`ShowWindow(SW_MINIMIZE)`) and focus/restore (`ShowWindow(SW_RESTORE)`) using `pywinauto` UIA backend with Win32 fallback.

### 2. Audio & Media Transport
- **WinRT SMTC Integration:** Interfaces directly with Windows `GlobalSystemMediaTransportControlsSessionManager` (SMTC). Commands (`try_play_async`, `try_pause_async`, `try_skip_next_async`) control Spotify, Chrome/Edge YouTube, Apple Music, and Media Player without keyboard simulation quirks.
- **State-Aware Playback:** Checks active audio peak meters and SMTC playback status before issuing play/pause commands to prevent accidental toggling.
- **Per-Application Volume:** Uses `pycaw` `ISimpleAudioVolume` to adjust Spotify's session volume independently, or `IAudioEndpointVolume` for master volume.
- **Optional Spotify Web API:** Dedicated `spotify_api.py` module supporting direct Web API playback control.

### 3. Native Dictation Bubble
- Voice-activated dictation: say *"Hey Jev, transcribe"* or *"Hey Jev, start dictating"*.
- Frameless, layered, topmost, click-through window positioned above the taskbar at bottom-centre.
- Displays a 24-bar live RMS audio waveform during recording.
- Transcribes using OpenAI / OpenRouter `gpt-4o-mini-transcribe`.
- Automatically pastes transcribed text at the current cursor location via Win32 clipboard synthesis (`Ctrl+V`) and appends history to `%APPDATA%/HeyJev/Hey Jev dictation.jsonl`.

### 4. Non-Admin Autostart
- Implements `autostart.py` targeting Windows Task Scheduler (`schtasks.exe /Create /TN "HeyJev" /SC ONLOGON /F`) for logon execution without administrative privileges.
- Resilient automated fallback to `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`.

---

## Installation & Setup

### Prerequisites
- Windows 10 or 11 (64-bit x64)
- Python 3.10 or 3.11
- Working microphone (configured as Default Audio Device)
- API Keys:
  - **TypeSafe (Jev):** [https://typesafe.ai](https://typesafe.ai) (Decision backend)
  - **Fish Audio:** [https://fish.audio](https://fish.audio) (Text-to-Speech replies)
  - **OpenRouter (Optional):** [https://openrouter.ai](https://openrouter.ai) (General knowledge queries)
  - **OpenAI (Optional):** [https://openai.com](https://openai.com) (Dictation transcription)

### Step-by-Step Installation

```powershell
# 1. Clone repository
git clone https://github.com/panwarbhagwat/hey-jev.git
cd hey-jev

# 2. Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Launch the application
python app.py
```

On first launch:
1. The **Keys** tab will prompt for your API keys, saving them securely to **Windows Credential Manager**.
2. `faster-whisper` will automatically download the `small.en` model (~250MB, cached locally).
3. Scripted TTS replies are pre-rendered into `%APPDATA%/HeyJev/cache/tts/`.
4. The status dot turns green when ready.

---

## Usage

### Interaction Modes
- **Hold Right Alt (Push-to-Talk):** Hold the Right Alt key, speak your request, and release when finished.
- **"Hey Jev" (Always Listening):** Say *"Hey Jev"* followed by your command (e.g. *"Hey Jev, open Spotify and set volume to 50"*).

### System Tray & Window Controls
- **Close Window (`X`):** Hides the window to the System Tray and continues listening.
- **Restore Window:** Double-click the Hey Jev tray icon, or right-click and choose **Show Hey Jev**.
- **Keep on Top:** Check **Keep window always on top** in Settings or right-click the tray icon.
- **Quit:** Right-click the tray icon and select **Quit Hey Jev**, or press `Ctrl+Q`.

### Command Line Interface

```powershell
# Launch graphical interface (same as app.py)
python siri.py --ui

# Push-to-talk mode in console (outputs live decision trace)
python siri.py

# Always-listening wake mode
python siri.py --wake

# Low-CPU openWakeWord engine
python siri.py --wake --wake-backend openwakeword

# Text-only test turn (no microphone required)
python siri.py --text "pause music and open slack"
```

---

## Packaging into Standalone Windows Executable

Hey Jev includes a pre-configured PyInstaller specification (`hey_jev.spec`) that produces a windowed, one-dir executable with zero console window flashing:

```powershell
# Build standalone distribution
pyinstaller hey_jev.spec --noconfirm --clean

# The resulting distribution is located in:
dist\Hey Jev\Hey Jev.exe
```

---

## Decision Backend Benchmark (Jev vs Laya)

As evaluated in `BENCHMARK_REPORT.md`:

| Metric | TypeSafe Jev (Hosted System 1) | Local Laya (On-Device Model) |
|---|---|---|
| **Turn Accuracy** | 98.1% | 84.8% |
| **p50 Latency** | 224 ms | 712 ms (CPU) |
| **p95 Latency** | 382 ms | 1,480 ms (CPU) |
| **RAM Footprint** | ~140 MB | ~1.85 GB |
| **Cost Per Turn** | ~$0.00004 | $0.00 |
| **Host Stability** | 100% Green | OS Commitment limit on constrained pagefiles |
| **Default Selection** | **YES (Recommended Default)** | Additive (Toggle in Settings) |

To run the automated benchmark on your hardware:
```powershell
python benchmark_backends.py --samples 50 --runs 2
```

---

## File Structure

- `app.py`: Standard executable entrypoint.
- `siri.py`: Main event loop, Whisper speech recognition, decision routing, audio dispatch.
- `assistant_ui.py`: PySide6 native 7-tab interface and Windows notification area system tray integration.
- `bubble.py`: Frameless floating waveform dictation window.
- `actions_win.py`: Complete Windows 10/11 action parity implementation (Win32, UIA, pycaw, SMTC).
- `backend.py`: `DecisionBackend` abstraction with `JevBackend` and `LayaBackend`.
- `wake_word.py`: Wake word detector abstraction (`WhisperPrefixDetector` and `OpenWakeWordDetector`).
- `spotify_api.py`: Optional Spotify Web API OAuth client.
- `autostart.py`: Windows Task Scheduler and HKCU Run autostart manager.
- `secrets_store.py`: Windows Credential Manager integration via `keyring`.
- `hey_jev.spec`: PyInstaller one-dir windowed build specification.

---

## License & Credits

- Windows port of [henryklunaris/hey-jev](https://github.com/henryklunaris/hey-jev) by Bhagwat Panwar. Original by Henryk Lunaris (MIT).
- Original macOS implementation: Copyright © 2026 Henryk Lunaris ([MIT License](https://github.com/henryklunaris/hey-jev/blob/main/LICENSE)).
- Laya reference implementations: `hey-laya` (MIT License © 2026 Touhid Siddique Eraj) and `home-assistant-laya` (Apache 2.0 © 2026 Allen Porter).
- openWakeWord: Apache 2.0 © 2023 David Scripka.
