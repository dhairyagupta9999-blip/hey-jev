"""Safety, Risk Classification, Confirmation Engine, and Audit Log for Hey Jev.

Safety architecture:
  - SAFE: runs automatically (open, focus, volume, media, search, web).
  - MEDIUM: spoken back, runs unless user says 'stop' or presses Esc within 2s.
    (close-all and typing into unsaved documents require explicit 'yes').
  - HIGH: states exact impact, waits for spoken/typed 'yes' with 8-second timeout defaulting to NO.
    (delete to Recycle Bin, run_powershell, move/rename, shutdown/restart, install/uninstall).
  - Never permanently delete: send files to Recycle Bin only via send2trash.
  - run_powershell denylist: iex, download cradles, format, diskpart, system file deletion, reg delete, net user.
  - Audit log: %APPDATA%/HeyJev/actions.jsonl with 'undo that' support.
  - Prompt injection defense: data from files, windows, web pages is strictly quarantined as DATA.
"""
from __future__ import annotations

import os
import sys
import time
import json
import re
import threading
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

import send2trash

from config import APPDATA_DIR

ACTIONS_LOG_FILE = os.path.join(APPDATA_DIR, "actions.jsonl")

# --------------------------------------------------------------------------- Risk Levels
SAFE = "SAFE"
MEDIUM = "MEDIUM"
HIGH = "HIGH"

ACTION_RISK_MAP = {
    # SAFE
    "open_app": SAFE,
    "focus_window": SAFE,
    "app_focus": SAFE,
    "app_open": SAFE,
    "system_setting": SAFE,
    "system_folder": SAFE,
    "system_utility": SAFE,
    "system_website": SAFE,
    "system_search": SAFE,
    "set_volume": SAFE,
    "media_control": SAFE,
    "media_play": SAFE,
    "media_pause": SAFE,
    "media_next": SAFE,
    "media_previous": SAFE,
    "window_snap_left": SAFE,
    "window_snap_right": SAFE,
    "window_minimize": SAFE,
    "window_maximize": SAFE,
    "window_restore": SAFE,
    "list_windows": SAFE,
    "find_files": SAFE,
    "open_path": SAFE,
    "read_foreground_text": SAFE,
    "web_search": SAFE,
    "open_url": SAFE,
    "clipboard_get": SAFE,

    # MEDIUM (2-second grace period)
    "close_app": MEDIUM,
    "app_quit": MEDIUM,
    "type_text": MEDIUM,
    "press_keys": MEDIUM,
    "clipboard_set": MEDIUM,

    # HIGH (8-second explicit YES timeout, default NO)
    "close_all": HIGH,
    "delete_file": HIGH,
    "move_file": HIGH,
    "rename_file": HIGH,
    "open_dangerous_file": HIGH,
    "run_powershell": HIGH,
    "install_software": HIGH,
    "uninstall_software": HIGH,
    "shutdown_computer": HIGH,
    "restart_computer": HIGH,
    "registry_edit": HIGH,
    "network_change": HIGH,
    "send_message": HIGH,
    "send_email": HIGH,
}

# --------------------------------------------------------------------------- PowerShell Denylist
POWERSHELL_DENYLIST = [
    (re.compile(r"\b(?:Invoke-Expression|iex)\b", re.I), "Invoke-Expression (code execution)"),
    (re.compile(r"\b(?:DownloadFile|DownloadString|Net\.WebClient|BitsTransfer)\b", re.I), "arbitrary web download cradle"),
    (re.compile(r"\b(?:Invoke-WebRequest|Invoke-RestMethod|curl|wget)\b", re.I), "outbound network request"),
    (re.compile(r"\bRemove-Item\b.*-(?:Recurse|r)\b.*(?:C:\\Windows|C:\\Program Files|C:\\Users\\[^\\]+$|system32)", re.I), "recursive system path deletion"),
    (re.compile(r"\b(?:format|diskpart)\b", re.I), "destructive disk partitioning or formatting"),
    (re.compile(r"\breg(?:\.exe)?\s+delete\b", re.I), "registry key deletion"),
    (re.compile(r"\bnet\s+(?:user|localgroup)\b", re.I), "user account management"),
    (re.compile(r"\b(?:Start-Process.*-Verb\s+RunAs|runas)\b", re.I), "privilege elevation / administrative execution"),
]

def validate_powershell_command(cmd: str) -> Tuple[bool, str]:
    """Validate PowerShell command against the safety denylist. Never runs as admin."""
    for rx, reason in POWERSHELL_DENYLIST:
        if rx.search(cmd):
            return False, f"Command blocked by safety policy: contains {reason}."
    return True, "Command passed safety validation."


# --------------------------------------------------------------------------- Prompt Injection Sanitizer
INJECTION_PATTERNS = [
    re.compile(r"(?:ignore|forget|disregard)\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?", re.I),
    re.compile(r"(?:system\s+prompt|developer\s+mode|jailbreak|DAN\s+mode)", re.I),
    re.compile(r"(?:delete\s+(?:all|everything)|remove-item\s+-recurse)", re.I),
    re.compile(r"(?:you\s+are\s+now|new\s+system\s+instruction)", re.I),
]

def sanitize_data_content(text: str, source_label: str = "DATA") -> str:
    """Quarantine external text as untrusted DATA, stripping prompt injection vectors."""
    cleaned = text
    for rx in INJECTION_PATTERNS:
        cleaned = rx.sub("[REDACTED_INJECTION_ATTEMPT]", cleaned)
    return f"<{source_label}>\n{cleaned.strip()}\n</{source_label}>"


# --------------------------------------------------------------------------- Audit Log & Undo
_LOG_LOCK = threading.Lock()

def log_action(
    tier: int,
    action: str,
    args: Dict[str, Any],
    risk_level: str,
    result: str,
    undoable: bool = False,
    undo_data: Optional[Dict[str, Any]] = None
) -> str:
    """Record action to %APPDATA%/HeyJev/actions.jsonl."""
    act_id = f"act_{int(time.time()*1000)}"
    entry = {
        "id": act_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "tier": tier,
        "action": action,
        "args": args,
        "risk_level": risk_level,
        "result": result,
        "undoable": undoable,
        "undo_data": undo_data
    }
    with _LOG_LOCK:
        try:
            os.makedirs(os.path.dirname(ACTIONS_LOG_FILE), exist_ok=True)
            with open(ACTIONS_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as exc:
            print(f"  [safety audit log error]: {exc}")
    return act_id

def get_last_undoable_action() -> Optional[Dict[str, Any]]:
    """Retrieve the most recent undoable action from the audit log."""
    if not os.path.exists(ACTIONS_LOG_FILE):
        return None
    with _LOG_LOCK:
        try:
            with open(ACTIONS_LOG_FILE, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
            for line in reversed(lines):
                data = json.loads(line)
                if data.get("undoable") and data.get("undo_data"):
                    return data
        except Exception:
            return None
    return None

def perform_undo() -> Tuple[bool, str]:
    """Execute undo for the last reversible action."""
    last_act = get_last_undoable_action()
    if not last_act:
        return False, "Nothing to undo."

    undo_data = last_act["undo_data"]
    u_act = undo_data.get("action")

    if u_act == "open_app":
        target = undo_data.get("target")
        from app_index import get_app_index
        get_app_index().launch_app(target)
        log_action(2, "undo", {"reverted_action": last_act["action"], "reverted_id": last_act["id"]}, SAFE, "success")
        return True, f"Undid closing {target}. Reopening {target}."

    elif u_act == "restore_file":
        path = undo_data.get("path")
        # Recycle Bin restoration note: Windows Recycle Bin COM doesn't guarantee programmatic restore without shell UI,
        # but we record the original location.
        log_action(2, "undo", {"reverted_action": last_act["action"], "path": path}, SAFE, "success")
        return True, f"File {os.path.basename(path)} was sent to the Recycle Bin. You can restore it from the Recycle Bin."

    elif u_act == "set_volume":
        prev_vol = undo_data.get("previous_volume", 50)
        import actions_win
        actions_win.set_volume(prev_vol)
        log_action(2, "undo", {"reverted_action": "set_volume", "previous_volume": prev_vol}, SAFE, "success")
        return True, f"Undid volume change, restored to {prev_vol}%."

    return False, f"Cannot undo {last_act['action']}."


# --------------------------------------------------------------------------- Confirmation & Cancellation Manager
class ConfirmationManager:
    """Manages in-flight actions, grace periods, and explicit confirmations."""

    def __init__(self):
        self._lock = threading.RLock()
        self.pending_confirmation: Optional[Dict[str, Any]] = None
        self.grace_period_timer: Optional[threading.Timer] = None

    def request_high_risk_confirmation(
        self,
        action: str,
        message: str,
        execute_fn: Callable[[], Any],
        timeout_s: float = 8.0
    ) -> Dict[str, Any]:
        """Request explicit confirmation for HIGH risk actions with 8s default-NO timeout."""
        with self._lock:
            # Cancel any previous pending confirmation
            self.cancel_pending("replaced by new action")

            evt = threading.Event()
            state = {"confirmed": False, "executed": False, "expired": False, "result": None}

            def _timeout_cb():
                with self._lock:
                    if not state["confirmed"]:
                        state["expired"] = True
                        evt.set()

            timer = threading.Timer(timeout_s, _timeout_cb)
            timer.daemon = True
            timer.start()

            self.pending_confirmation = {
                "action": action,
                "message": message,
                "risk_level": HIGH,
                "timer": timer,
                "event": evt,
                "state": state,
                "execute_fn": execute_fn,
                "created_at": time.time()
            }

            return {
                "needs_confirmation": True,
                "risk_level": HIGH,
                "action": action,
                "message": message,
                "timeout_s": timeout_s
            }

    def request_medium_risk_grace_period(
        self,
        action: str,
        message: str,
        execute_fn: Callable[[], Any],
        grace_seconds: float = 2.0
    ) -> Dict[str, Any]:
        """Schedule MEDIUM risk action with 2s cancel grace period."""
        with self._lock:
            self.cancel_pending("replaced by new action")

            state = {"aborted": False}
            def _grace_run():
                time.sleep(grace_seconds)
                with self._lock:
                    if not state["aborted"]:
                        try:
                            execute_fn()
                        except Exception as exc:
                            print(f"  [medium risk action error]: {exc}")

            t = threading.Thread(target=_grace_run, daemon=True)
            t.start()

            self.pending_confirmation = {
                "action": action,
                "message": message,
                "risk_level": MEDIUM,
                "state": state,
                "thread": t,
                "created_at": time.time()
            }

            return {
                "status": "grace_period",
                "risk_level": MEDIUM,
                "action": action,
                "message": message,
                "grace_seconds": grace_seconds
            }

    def respond(self, response_text: str) -> Tuple[bool, str]:
        """Handle user spoken or typed response ('yes', 'stop', 'no')."""
        t = response_text.lower().strip()
        with self._lock:
            if not self.pending_confirmation:
                return False, "No action is awaiting confirmation."

            pending = self.pending_confirmation
            state = pending["state"]

            # Explicit YES confirmation for HIGH risk actions
            if t in ("yes", "yeah", "yep", "do it", "confirm", "proceed", "sure"):
                now = time.time()
                timeout_s = pending.get("timeout_s", 8.0)
                created_at = pending.get("created_at", now)
                if state.get("expired") or (now - created_at > timeout_s):
                    self.pending_confirmation = None
                    return False, "Confirmation timed out and defaulted to NO."

                if pending.get("timer"):
                    pending["timer"].cancel()
                state["confirmed"] = True
                try:
                    result = pending["execute_fn"]()
                    self.pending_confirmation = None
                    return True, "Confirmed. Action executed."
                except Exception as exc:
                    self.pending_confirmation = None
                    return False, f"Action failed: {exc}"

            # Cancel / Stop command
            if t in ("stop", "no", "cancel", "abort", "halt", "wait", "dont", "don't"):
                return self.cancel_pending("user requested stop")

            # Any other response to HIGH risk defaults to NO
            return self.cancel_pending("confirmation did not receive yes")

    def cancel_pending(self, reason: str = "stop") -> Tuple[bool, str]:
        """Abort any pending grace period or confirmation."""
        with self._lock:
            if not self.pending_confirmation:
                return False, "No action was running or pending."

            pending = self.pending_confirmation
            state = pending["state"]
            if pending.get("timer"):
                pending["timer"].cancel()
            state["aborted"] = True
            state["confirmed"] = False
            self.pending_confirmation = None
            return True, f"Action cancelled ({reason})."

    def has_pending(self) -> bool:
        """Return True if an action or confirmation is actively pending."""
        with self._lock:
            return self.pending_confirmation is not None



_GLOBAL_CONFIRMATION_MANAGER: Optional[ConfirmationManager] = None
_CANCEL_EVENT = threading.Event()

def get_confirmation_manager() -> ConfirmationManager:
    global _GLOBAL_CONFIRMATION_MANAGER
    if _GLOBAL_CONFIRMATION_MANAGER is None:
        _GLOBAL_CONFIRMATION_MANAGER = ConfirmationManager()
    return _GLOBAL_CONFIRMATION_MANAGER

def request_global_cancel(reason: str = "stop") -> bool:
    """Signal global cancellation of running actions, confirmations, or agent loops."""
    _CANCEL_EVENT.set()
    cm = get_confirmation_manager()
    if cm.has_pending():
        cm.cancel_pending(reason)
        return True
    return False

def is_cancel_requested() -> bool:
    """Check if cancellation was signaled."""
    return _CANCEL_EVENT.is_set()

def check_and_clear_cancel() -> bool:
    """Clear and return previous cancellation state."""
    if _CANCEL_EVENT.is_set():
        _CANCEL_EVENT.clear()
        return True
    return False



# --------------------------------------------------------------------------- Safe File Operations
def delete_file_to_recycle_bin(path: str) -> Dict[str, Any]:
    """Never permanently delete anything: send file to Windows Recycle Bin."""
    if not os.path.exists(path):
        return {"success": False, "error": f"File does not exist: {path}"}

    try:
        send2trash.send2trash(path)
        log_action(
            tier=2,
            action="delete_file",
            args={"path": path},
            risk_level=HIGH,
            result="success",
            undoable=True,
            undo_data={"action": "restore_file", "path": path}
        )
        return {
            "success": True,
            "path": path,
            "filename": os.path.basename(path),
            "line": f"Moved {os.path.basename(path)} to the Recycle Bin."
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}
