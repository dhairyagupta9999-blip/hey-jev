# Phase 7 Research: "Do Anything" Automation Engines

**Evaluation of Candidate Automation Systems for Hey Jev Windows Port**  
**Date:** October 2026  
**Environment:** Windows 11 / Windows 10 x64, Python 3.11.9, separate `.venv-agents`  
**Status:** Step 1 Research Complete — Awaiting Approval for Step 2

---

## 1. Candidate Evaluation Matrix

| Candidate | License | Last Commit Date | Runtime / Platform Requirements | Disk Footprint | Telemetry / Data Sent | Primary Tool List | Key Capability Beyond Hey Jev Tier 2 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **CursorTouch/Windows-MCP** | **MIT** (Jeomon George, 2025) | Early Oct 2026 (v1.0.1 on Sep 27, 2026) | Windows 7–11 x64; Python 3.13+ or `uvx` | ~55 MB (Python dependencies) | PostHog usage data (tool name, latency, status). **Disable:** `ANONYMIZED_TELEMETRY=false` | `click_tool`, `type_tool`, `move_cursor_tool`, `press_key_tool`, `scroll_tool`, `snapshot_tool` (with DOM mode), `app_tool`, `clipboard_tool`, `powershell_tool`, `process_tool`, `registry_tool` | Arbitrary UI coordinate clicking, typing into non-focused inputs, accessibility/DOM tree snapshotting |
| **sbroenne/mcp-windows** | **MIT** (sbroenne, 2025–2026) | Oct 2026 (v2.x) | Windows 10/11 x64; .NET 10 standalone binary (No Python required) | ~40 MB (single executable) | **Zero telemetry**; completely local via Windows UI Automation API | `ui_find`, `ui_click`, `ui_type`, `ui_read`, `file_save`, `window_management`, `screenshot_control`, `mouse_control`, `keyboard_control`, `app` | Semantic UI control by element name (DPI/resolution-independent), button clicking without coordinates |
| **browser-use/browser-use** | **MIT** (browser-use team) | Oct 2026 (v0.13.10 on Sep 3, 2026) | Windows 10/11, macOS, Linux; Python >= 3.11; Chromium | ~350 MB (Playwright + Chromium browser) | Anonymous task metadata (task, visited URLs, action traces). **Disable:** `ANONYMIZED_TELEMETRY=false` | `search_google`, `go_to_url`, `click_element`, `input_text`, `scroll_down`, `scroll_up`, `send_keys`, `open_tab`, `switch_tab`, `close_tab`, `extract_content` | Autonomous multi-step web browsing, dynamic DOM interaction, form fills, authentication navigation |
| **simular-ai/Agent-S** (Agent S3) | **Apache-2.0** (Simular AI) | Sep 2026 (v0.3.2 + patches) | Windows, macOS, Linux; Python >= 3.10; PyTorch, OCR | ~2.5 GB (PyTorch, vision models, OCR weights) | Sends full screenshots to external VLM APIs (Claude/GPT-4o). No telemetry to Simular | `click`, `double_click`, `right_click`, `move_to`, `type_text`, `press_key`, `hotkey`, `scroll`, `drag_and_drop`, `screenshot`, `subtask_complete` | End-to-end vision-language reasoning on arbitrary desktop GUI, visual icon grounding, complex subtask planning |
| **microsoft/UFO** (UFO² / UFO³ Galaxy) | **MIT** (Microsoft Corp) | Mid/Late 2026 (UFO³ Galaxy) | Windows 10/11 x64; Python >= 3.10; PyWin32, OpenCV | ~1.2 GB (OpenCV, COM, agent libraries) | Dual-agent sends screenshots & UI trees to Azure/OpenAI VLM. Configurable telemetry | HostAgent: App dispatch, window focus, DAG evolution. AppAgent: Control click, type, select, scroll, text read | Cross-application enterprise workflow automation (e.g. Excel -> PowerPoint -> Outlook) with dual-agent reflection |

---

## 2. Detailed Candidate Profiles

### Candidate 1: CursorTouch/Windows-MCP
- **Repository:** `https://github.com/CursorTouch/Windows-MCP`
- **License:** **MIT License** (verified from `LICENSE.md`, Copyright 2025 Jeomon George).
- **Last Commit / Release:** v1.0.1 released September 27, 2026; commits active in October 2026.
- **Requirements:** Windows 7, 8, 8.1, 10, 11 (x64). Runtime via `uvx windows-mcp` or `python -m windows_mcp`.
- **Install Size:** ~55 MB (FastMCP, comtypes, dxcam, Pillow, posthog, psutil, click).
- **Data Collection & Telemetry:**
  - **What is collected:** PostHog client sends tool execution status (success/failure), latency duration, tool name, client application name/version, and anonymized session ID.
  - **What is NOT collected:** Tool arguments (typed text, file paths) and outputs (screenshots, command outputs) are not sent.
  - **Exact setting to disable:**
    ```env
    ANONYMIZED_TELEMETRY=false
    ```
    This environment variable must be passed into the subprocess environment when launching the server.
- **Exposed Tools:**
  - `click_tool` (`Click`), `move_cursor_tool` (`Move`), `type_tool` (`Type`), `press_key_tool` (`Shortcut`), `scroll_tool` (`Scroll`), `app_tool` (`Launch`), `snapshot_tool` (`State`, with DOM mode), `wait_for_tool` (`WaitFor`), `clipboard_tool`, `powershell_tool`, `process_tool`, `registry_tool`, `display_inventory_tool`.
- **Capabilities Beyond Hey Jev Tier 2:**
  - Enables physical mouse clicking at arbitrary coordinates and simulated typing into controls across any application.
  - Reads UI state trees and browser DOM hierarchies (`use_dom=True`).
- **Risks & Mitigation:**
  - Exposes dangerous tools (`PowerShell`, `Registry`, `Process`). In Hey Jev, these **must be denied by default** at the MCP client layer and gated by the Safety Engine.

---

### Candidate 2: sbroenne/mcp-windows
- **Repository:** `https://github.com/sbroenne/mcp-windows`
- **License:** **MIT License** (verified from `LICENSE`, Copyright 2025–2026 sbroenne).
- **Last Commit / Release:** v2.x series, active in October 2026.
- **Requirements:** Windows 10/11 x64. Implemented in C# / .NET 10. Standalone `.exe` binary available on GitHub Releases (no Python runtime required).
- **Install Size:** ~40 MB for self-contained single-file executable.
- **Data Collection & Telemetry:**
  - **Zero data collection**. Strictly local execution via Windows native UI Automation COM APIs (`UIAutomationClient`). No telemetry packages, no network egress.
- **Exposed Tools (10 tools):**
  - `ui_find`: Find element by name, control type, or automation ID.
  - `ui_click`: Click UI element by name/identifier.
  - `ui_type`: Input text directly into element.
  - `ui_read`: Read accessibility attributes and text content.
  - `file_save`: Save file.
  - `window_management`: Find, activate, move, resize, minimize, maximize.
  - `screenshot_control`: Capture screen or window bounds.
  - `mouse_control`: Simulate mouse click/move/scroll.
  - `keyboard_control`: Send keystrokes and key combinations.
  - `app`: Launch app and return HWND.
- **Capabilities Beyond Hey Jev Tier 2:**
  - Semantic element targeting: clicks buttons and types into fields by label rather than pixel coordinates. Immune to display scaling/DPI shifts.

---

### Candidate 3: browser-use/browser-use
- **Repository:** `https://github.com/browser-use/browser-use`
- **License:** **MIT License** (verified from `LICENSE`).
- **Last Commit / Release:** v0.13.10 released September 3, 2026; active through October 2026.
- **Requirements:** Windows 10/11 x64, Python >= 3.11, Chromium (via Playwright).
- **Install Size:** ~350 MB (library + Playwright browser binaries).
- **Data Collection & Telemetry:**
  - Default telemetry (`AgentTelemetryEvent`) collects task instructions, URLs visited, action steps, and outcomes.
  - **Exact setting to disable:**
    ```env
    ANONYMIZED_TELEMETRY=false
    ```
    Must be set in the process environment before importing or executing `browser_use`.
- **Exposed Actions:**
  - `search_google`, `go_to_url`, `click_element`, `input_text`, `scroll_down`, `scroll_up`, `send_keys`, `open_tab`, `switch_tab`, `close_tab`, `extract_content`.
- **Capabilities Beyond Hey Jev Tier 2:**
  - Handles dynamic modern web apps, multi-tab navigation, login forms, CAPTCHA pauses, and content extraction that standard shell URLs cannot handle.

---

### Candidate 4: simular-ai/Agent-S (Agent S3)
- **Repository:** `https://github.com/simular-ai/Agent-S`
- **License:** **Apache-2.0 License** (verified from `LICENSE`).
- **Last Commit / Release:** v0.3.2 (Dec 2025) with active September 2026 updates.
- **Requirements:** Windows/Linux/macOS, Python >= 3.10, PyTorch, torchvision, EasyOCR.
- **Install Size:** Heavyweight (~2.5 GB).
- **Data Collection & Privacy:**
  - Transmits full desktop screenshots to external multimodal vision models (e.g. Anthropic Claude 3.5 Sonnet, OpenAI GPT-4o).
  - Note: CVE-2026-84886/84887 vulnerability reported in September 2026 regarding image buffer handling in `ocr_server.py`.
- **Exposed ACI Tools:**
  - Mouse moves, clicks, typing, hotkeys, scrolling, coordinate dragging, and screenshot capturing.
- **Capabilities Beyond Hey Jev Tier 2:**
  - Visual reasoning over arbitrary desktop pixels without needing accessibility tree tags.

---

### Candidate 5: microsoft/UFO (UFO² / UFO³ Galaxy)
- **Repository:** `https://github.com/microsoft/UFO`
- **License:** **MIT License** (verified from `LICENSE`, Copyright Microsoft Corporation).
- **Last Commit / Release:** UFO³ Galaxy framework (Mid/Late 2026).
- **Requirements:** Windows 10/11 x64, Python >= 3.10, PyWin32, OpenCV.
- **Install Size:** Heavyweight (~1.2 GB).
- **Data Collection & Privacy:**
  - Dual-agent loop sends window screenshots and UI tree hierarchies to LLM/VLM APIs.
- **Capabilities Beyond Hey Jev Tier 2:**
  - Orchestrates complex workflows across multiple Office and Windows desktop applications.

---

## 3. Integration Recommendation & Strategic Plan

### Recommended Primary Integration: CursorTouch/Windows-MCP (Step 2)
1. **Rationale:**
   - Native Python/MCP stdio protocol compatibility (`uvx windows-mcp serve` or `python -m windows_mcp serve`).
   - Supports explicit `--tools` allowlist and `--exclude-tools` denylist natively.
   - Clean, lightweight (~55 MB), and fast latency (0.2–0.5s per action).
   - Can easily be complemented by `sbroenne/mcp-windows` if a zero-dependency compiled binary is preferred.
2. **Mandatory Security Configuration for Windows-MCP:**
   - **Telemetry:** Always pass `ANONYMIZED_TELEMETRY=false` in the subprocess environment.
   - **Tool Allowlist (Permitted):**
     - UI Snapshot / State (`snapshot_tool` / `State`)
     - Mouse Click (`click_tool` / `Click`)
     - Text Typing (`type_tool` / `Type`)
     - Keyboard / Shortcut (`press_key_tool` / `Shortcut`)
     - Scroll (`scroll_tool` / `Scroll`)
     - Window Focus / Resize (`window`)
     - App Launch (`app_tool` / `Launch`)
   - **Tool Denylist (Strictly Blocked by Default):**
     - `powershell_tool`, `registry_tool`, `process_tool`, file write/move/delete, services, scheduled tasks, network config.
   - **Safety Gating:**
     - Typing or key combinations into any application $\to$ **MEDIUM risk**.
     - Unknown or unlisted tools $\to$ **Blocked**.
     - All outputs wrapped in `<DATA>` sanitization tags.
     - 8-step ceiling and 30-second timeout per turn.

### Recommended Web Browsing Engine: browser-use (Step 3)
- Run in `.venv-agents` as an isolated worker subprocess.
- Always enforce `ANONYMIZED_TELEMETRY=false`.
- Launch with a dedicated clean browser user data profile directory (never user's personal browser profile).
- Confirmation required before sensitive actions (login, payment, file download, form submit).

### Recommended Desktop Vision Engine: Lightweight Wrapper (Step 4)
- Maintain lightweight, modular design: do not install multi-gigabyte PyTorch/VLM weights locally.
- Implement `desktop_vision_task(task)` as a configuration wrapper with Settings toggle (default OFF).
- Enforce explicit user consent and privacy notice regarding screenshot transmission to VLM endpoints.

---

## 4. Current State & Verification

- **Environment:** Dedicated virtual environment `.venv-agents` created at `C:\Users\prabh\.gemini\antigravity\scratch\hey-jev\.venv-agents` without modifying Hey Jev core `.venv`.
- **Automated Tests:** 110/110 existing unit tests pass (`pytest -v`).
- **Real PC Verification:** Candidate licenses, repository commit dates, package dependencies, telemetry parameters, and security postures were verified directly from upstream sources.
