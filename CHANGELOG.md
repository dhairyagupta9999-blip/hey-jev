# Changelog

All notable changes to the Windows 10/11 port of `hey-jev` will be documented in this file.

## [Phase 2: Action Parity] - 2026-10-03
- Implemented and verified all 33 actions from the Action Parity Table for Windows 10/11 x64.
- Added comprehensive app launcher supporting Win32, UWP, and packaged apps via URI schemes and shell:AppsFolder.
- Implemented safe process-tree termination with 1.5s timeout for tray-minimizing apps (Slack, Discord, Spotify).
- Added state-aware media transport via SendInput (VK_MEDIA_*), pycaw master/session volume, dark mode registry toggling with WM_SETTINGCHANGE, and non-blocking background action pool.

## [Phase 1.5: Decision Backend Abstraction & Benchmark] - 2026-10-03
- Introduced backend-agnostic `DecisionBackend` interface supporting both TypeSafe hosted Jev and local open-weight Laya models.
- Added `LayaBackend` running in-process on CPU with background pre-warming, uniform-prior confidence calibration, and automatic fallback to Jev.
- Built 105-phrase benchmark test suite across §07 acceptance categories and evaluated latency, memory commitment, and host reliability in `BENCHMARK_REPORT.md`.

## [Phase 1: Core Loop] - 2026-10-03
- Ported core loop to Windows 10/11 with single asyncio event loop, WASAPI audio capture (`sounddevice`), and local `faster-whisper` (`small.en`, CPU int8).
- Implemented global non-admin Right-Alt push-to-talk hook and Whisper-prefix wake mode.
- Ported secrets store from macOS Keychain to Windows Credential Manager via `keyring` with `.env` priority.
- Built monotonic timers and reminders surviving restarts (`%APPDATA%/HeyJev/timers.json`) with dual voice alerts and native Windows Toast notifications.
- Added pure in-process MP3/WAV playback via `sounddevice` + `soundfile`/PyAV (no winsound).
- Implemented trace logging to `%APPDATA%/HeyJev/Hey Jev.log` adhering to the exact macOS trace format with `[backend: jev]`.
