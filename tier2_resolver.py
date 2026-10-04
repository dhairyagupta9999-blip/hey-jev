"""Tier 2 Open-Vocabulary Local Resolver for Hey Jev.

Resolves requests locally without an LLM when Tier 1 is unclear or the target
is outside the hardcoded Tier 1 battery:
  - Open any application via AppIndex
  - Close any running application via process/window matching
  - Handle 'close everything' with confirmation
  - On-demand app index refresh ('refresh apps')
  - Ambiguity detection and two-choice clarification
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional

import app_index
from app_index import get_app_index, refresh_apps
import target_extractor
import actions_win
from tts import say_line
import logger


def resolve_tier2(text: str) -> Optional[Dict[str, Any]]:
    """Attempt to resolve a spoken command via Tier 2 local resolvers.

    Returns a dict with execution details, or None if Tier 2 cannot handle it.
    """
    t0 = time.perf_counter()
    action, target = target_extractor.extract_target(text)
    if not action:
        return None

    idx = get_app_index()

    # 1. Refresh apps command
    if action == "refresh_apps":
        count = refresh_apps()
        latency_ms = int((time.perf_counter() - t0) * 1000)
        line = f"Refreshed app index, found {count} applications."
        logger.trace_line(f"  [tier 2: app_index] {latency_ms}ms  $0.000000  action: refresh_apps")
        return {"tier": 2, "status": "done", "action": "refresh_apps", "line": line, "latency_ms": latency_ms}

    # 2. Close everything / close all windows (Always requires confirmation)
    if action == "close_all":
        res = idx.close_all_apps(confirmed=False)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        logger.trace_line(f"  [tier 2: app_control] {latency_ms}ms  $0.000000  action: close_all (needs_confirmation)")
        return {
            "tier": 2,
            "status": "needs_confirmation",
            "action": "close_all",
            "risk_level": "MEDIUM",
            "message": res["message"],
            "line": res["message"],
            "latency_ms": latency_ms
        }

    # 3. Open / launch application
    if action == "open" and target:
        app_entry, score, amb = idx.find_app(target)
        latency_ms = int((time.perf_counter() - t0) * 1000)

        # Ambiguity check
        if amb and len(amb) >= 2:
            choice_a, choice_b = amb[0]["name"], amb[1]["name"]
            msg = f"Did you mean {choice_a} or {choice_b}?"
            logger.trace_line(f"  [tier 2: app_index] {latency_ms}ms  $0.000000  ambiguity: {choice_a} vs {choice_b}")
            return {
                "tier": 2,
                "status": "ambiguous",
                "action": "clarify_app",
                "choices": [choice_a, choice_b],
                "message": msg,
                "line": msg,
                "latency_ms": latency_ms
            }

        if app_entry:
            success = idx.launch_app(app_entry)
            display_name = app_entry["name"]
            line = say_line("app_open", app=display_name)
            logger.trace_line(f"  [tier 2: app_index] {latency_ms}ms  $0.000000  launch: {display_name} (score {score:.1f})")
            return {
                "tier": 2,
                "status": "done" if success else "failed",
                "action": "app_open",
                "app": display_name,
                "entry": app_entry,
                "line": line,
                "latency_ms": latency_ms
            }

    # 4. Close / quit application
    if action == "close" and target:
        res = idx.close_app(target)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        if res.get("success"):
            line = say_line("app_quit", app=target)
            logger.trace_line(f"  [tier 2: app_control] {latency_ms}ms  $0.000000  closed: {target} (procs: {res.get('matched_processes')})")
            return {
                "tier": 2,
                "status": "done",
                "action": "app_quit",
                "app": target,
                "line": line,
                "latency_ms": latency_ms
            }

    # 5. Focus / switch to application
    if action == "focus" and target:
        app_entry, score, _ = idx.find_app(target)
        latency_ms = int((time.perf_counter() - t0) * 1000)
        if app_entry:
            proc_target = app_entry.get("process") or app_entry["name"]
            actions_win.focus_app(proc_target)
            line = say_line("app_focus", app=app_entry["name"])
            logger.trace_line(f"  [tier 2: app_control] {latency_ms}ms  $0.000000  focus: {app_entry['name']}")
            return {
                "tier": 2,
                "status": "done",
                "action": "app_focus",
                "app": app_entry["name"],
                "line": line,
                "latency_ms": latency_ms
            }

    return None
