# Phase 7 Acceptance Runbook: Windows MCP Automation Integration

This runbook documents the acceptance testing procedures for **Phase 7 Step 2 (Windows MCP Client Integration)**.

---

## 1. Automated Test Suite (Mocks Only)

> [!IMPORTANT]
> All automated tests in `test_phase7_mcp.py` strictly mock the MCP server over stdio and external LLM APIs. **No automated test sends real keystrokes, typing, or clicks into the user's active desktop window.**

Run the complete suite:
```powershell
.venv\Scripts\pytest.exe -v test_phase7_mcp.py
```
Expected result: **13 passed**.

---

## 2. Real PC Acceptance Commands (3 Harmless Commands)

Run these three safe, read-only `--text` commands on your real PC to verify end-to-end routing without typing into active windows:

### Command 1: Open Window Listing (Read-only UI Inspection)
```powershell
.venv\Scripts\python.exe siri.py --text "list the open windows"
```
- **What it does:** Discovers and enumerates top-level visible desktop windows.
- **Safety level:** `SAFE` (read-only inspection).
- **Audit proof:** Check `%APPDATA%\HeyJev\actions.jsonl` for `"action": "list_windows"` or `"window_management"`, `"risk_level": "SAFE"`.

### Command 2: File Discovery (Read-only Search)
```powershell
.venv\Scripts\python.exe siri.py --text "find files named resume"
```
- **What it does:** Searches local indexed user directories for matching filenames.
- **Safety level:** `SAFE` (read-only query). Output quarantined within `<DATA>` / `<MCP_DATA>` tags.
- **Audit proof:** Check `%APPDATA%\HeyJev\actions.jsonl` for `"action": "find_files"`, `"risk_level": "SAFE"`.

### Command 3: Active Window Status (Read-only State Inspection)
```powershell
.venv\Scripts\python.exe siri.py --text "what window is currently active"
```
- **What it does:** Inspects the current foreground window title without sending mouse clicks or keystrokes.
- **Safety level:** `SAFE` (read-only).
- **Audit proof:** Check `%APPDATA%\HeyJev\actions.jsonl` for `"risk_level": "SAFE"`.

---

## 3. Spoken Acceptance Test Matrix (12 Cases)

| # | Spoken Phrase | Expected System Behavior | Result | Category |
| :-: | :--- | :--- | :-: | :--- |
| **1** | *"What windows are currently open?"* | Discovers open top-level windows via UI inspection; speaks back summary | `[ ] Pass  [ ] Fail` | Read / Inspection |
| **2** | *"Find my budget spreadsheet"* | Searches user filesystem; quarantines results in `<DATA>` tags | `[ ] Pass  [ ] Fail` | Read / Inspection |
| **3** | *"Take a screenshot of the active window"* | Captures window bounds using `screenshot_control`; returns state | `[ ] Pass  [ ] Fail` | Read / Inspection |
| **4** | *"Open Notepad"* | Tier 2 / App index launches Notepad; logs as `SAFE` | `[ ] Pass  [ ] Fail` | App Launch |
| **5** | *"Type Hello World into Notepad"* | Gated as `MEDIUM` risk; speaks back action and executes typing | `[ ] Pass  [ ] Fail` | UI Action (Typing) |
| **6** | *"Press Ctrl plus S"* | Gated as `MEDIUM` risk; dispatches keystrokes via `keyboard_control` | `[ ] Pass  [ ] Fail` | UI Action (Keys) |
| **7** | *"Click the Save button"* | Gated as `MEDIUM` risk; semantically identifies button by UIA name | `[ ] Pass  [ ] Fail` | UI Action (Click) |
| **8** | *"Kill process chrome.exe"* | Blocked immediately by default; `process` tool denied; logged as `BLOCKED` | `[ ] Pass  [ ] Fail` | Denylist (Process) |
| **9** | *"Run PowerShell command Get-Process"* | Blocked by default from MCP stdio; requires Tier 3 confirmed PowerShell path | `[ ] Pass  [ ] Fail` | Denylist (Shell) |
| **10** | Spoken *"stop"* during multi-step turn | Instantly signals global cancel; halts remaining steps; speaks *"Action cancelled."* | `[ ] Pass  [ ] Fail` | Cancellation Hook |
| **11** | Press `Esc` key during in-flight operation | Signals global cancellation; stops MCP tool execution; speaks *"Action cancelled."* | `[ ] Pass  [ ] Fail` | Keyboard Cancel |
| **12** | MCP Server missing or unavailable | Speaks single clean message: *"Windows automation service is unavailable..."*; stays off | `[ ] Pass  [ ] Fail` | Error & Resilience |

---

## 4. Verification Record: Real PC vs. Mocks

| Item | Verification Mode | Evidence |
| :--- | :--- | :--- |
| **Standalone Binary Install** | **Real PC** | Downloaded `windows-mcp-server-1.3.27-win-x64.zip` without GitHub token; extracted `Sbroenne.WindowsMcp.exe` to `.venv-agents\bin\mcp-windows\`; verified on disk. |
| **Real Size on Disk** | **Real PC (Measured)** | `59,899,787 bytes` (`57.12 MB`). |
| **Network Egress / Telemetry** | **Real PC (Measured)** | Process monitored via `psutil`: `len(p.net_connections()) == 0` and 0 child processes. Zero outbound connections. |
| **MCP Handshake & Discovery** | **Real PC & Mock** | Real PC: stdio handshake with `Sbroenne.WindowsMcp.exe` queried and discovered all 18 tools. Unit tests: mocked stdio pipes verify handshake and allowlist filtering. |
| **Tool Allowlist & Denylist** | **Mocks** | Tested in `test_phase7_mcp.py`: permitted tools pass; `process`, `file_save`, `powershell`, and unknown tools rejected immediately. |
| **Safety Engine Risk Gating** | **Mocks & Local** | `evaluate_risk()` verified: typing/keys/clicks = `MEDIUM`, read/inspect = `SAFE`, unknown/denied = `BLOCKED`. |
| **Prompt Injection Quarantine** | **Mocks** | Tested with injection payloads: stripped and enclosed within `<MCP_DATA>` tags. |
| **8-Step Ceiling & 30s Timeout** | **Mocks** | Tested in `test_phase7_mcp.py`: loop terminates at step 8 ceiling; 30s timeout aborts cleanly without freezing. |
| **Global Cancellation (Esc / Stop)**| **Mocks & UI** | Tested in `test_phase7_mcp.py` and UI shortcut in `assistant_ui.py`: `request_global_cancel()` halts in-flight operations. |
