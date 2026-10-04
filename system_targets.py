"""System Targets, Settings URIs, Folders, and Web Navigation (Tier 2).

Resolves and executes:
  - ms-settings: URIs (wifi, bluetooth, display, sound, apps, windowsupdate)
  - Windows Administrative Tools (Task Manager, Control Panel, Device Manager)
  - Standard user folders (Downloads, Documents, Desktop, Pictures, Music, Videos)
  - Websites: direct URLs, known sites map, or fallback web search
"""
from __future__ import annotations

import os
import subprocess
import webbrowser
import re
from typing import Any, Dict, Optional

SETTINGS_PAGES = {
    "wifi": ("ms-settings:network-wifi", "Wi-Fi Settings"),
    "wi-fi": ("ms-settings:network-wifi", "Wi-Fi Settings"),
    "network": ("ms-settings:network", "Network Settings"),
    "internet": ("ms-settings:network", "Network Settings"),
    "bluetooth": ("ms-settings:bluetooth", "Bluetooth Settings"),
    "bluetooth settings": ("ms-settings:bluetooth", "Bluetooth Settings"),
    "display": ("ms-settings:display", "Display Settings"),
    "screen": ("ms-settings:display", "Display Settings"),
    "sound": ("ms-settings:sound", "Sound Settings"),
    "audio": ("ms-settings:sound", "Sound Settings"),
    "apps": ("ms-settings:appsfeatures", "Apps & Features"),
    "installed apps": ("ms-settings:appsfeatures", "Apps & Features"),
    "updates": ("ms-settings:windowsupdate", "Windows Update"),
    "windows update": ("ms-settings:windowsupdate", "Windows Update"),
    "update": ("ms-settings:windowsupdate", "Windows Update"),
    "battery": ("ms-settings:powersleep", "Battery & Power Settings"),
    "power": ("ms-settings:powersleep", "Battery & Power Settings"),
    "storage": ("ms-settings:storagesense", "Storage Settings"),
    "notifications": ("ms-settings:notifications", "Notification Settings"),
    "date and time": ("ms-settings:dateandtime", "Date & Time Settings"),
    "time": ("ms-settings:dateandtime", "Date & Time Settings"),
    "settings": ("ms-settings:", "Windows Settings"),
}

STANDARD_FOLDERS = {
    "downloads": (os.path.expanduser("~/Downloads"), "Downloads folder"),
    "downloads folder": (os.path.expanduser("~/Downloads"), "Downloads folder"),
    "documents": (os.path.expanduser("~/Documents"), "Documents folder"),
    "documents folder": (os.path.expanduser("~/Documents"), "Documents folder"),
    "desktop": (os.path.expanduser("~/Desktop"), "Desktop folder"),
    "desktop folder": (os.path.expanduser("~/Desktop"), "Desktop folder"),
    "pictures": (os.path.expanduser("~/Pictures"), "Pictures folder"),
    "pictures folder": (os.path.expanduser("~/Pictures"), "Pictures folder"),
    "music": (os.path.expanduser("~/Music"), "Music folder"),
    "music folder": (os.path.expanduser("~/Music"), "Music folder"),
    "videos": (os.path.expanduser("~/Videos"), "Videos folder"),
    "videos folder": (os.path.expanduser("~/Videos"), "Videos folder"),
}

SYSTEM_UTILITIES = {
    "task manager": ("taskmgr.exe", "Task Manager"),
    "taskmgr": ("taskmgr.exe", "Task Manager"),
    "control panel": ("control.exe", "Control Panel"),
    "device manager": ("devmgmt.msc", "Device Manager"),
    "device manager console": ("devmgmt.msc", "Device Manager"),
    "disk management": ("diskmgmt.msc", "Disk Management"),
    "resource monitor": ("resmon.exe", "Resource Monitor"),
    "services": ("services.msc", "Services"),
}

KNOWN_SITES = {
    "youtube": "https://www.youtube.com",
    "github": "https://github.com",
    "gmail": "https://mail.google.com",
    "reddit": "https://www.reddit.com",
    "twitter": "https://twitter.com",
    "x": "https://x.com",
    "google": "https://www.google.com",
    "wikipedia": "https://www.wikipedia.org",
    "netflix": "https://www.netflix.com",
    "spotify": "https://open.spotify.com",
    "amazon": "https://www.amazon.com",
    "twitch": "https://www.twitch.tv",
    "discord": "https://discord.com",
    "linkedin": "https://www.linkedin.com",
    "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "chatgpt": "https://chatgpt.com",
    "claude": "https://claude.ai",
}

URL_REGEX = re.compile(
    r"^(?:https?://)?(?:www\.)?([a-zA-Z0-9-]+\.(?:com|org|net|io|edu|gov|co|ai|dev|app|info|xyz|me|tv|cc))(?:/[^\s]*)?$",
    re.IGNORECASE
)

def is_url(text: str) -> Optional[str]:
    """Check if text is a valid web URL, returning a normalized https:// URL."""
    t = text.strip()
    if t.startswith("http://") or t.startswith("https://"):
        return t
    m = URL_REGEX.match(t)
    if m:
        return f"https://{t}"
    return None

def resolve_system_target(text: str) -> Optional[Dict[str, Any]]:
    """Resolve spoken target against Settings pages, system utilities, folders, or websites."""
    t_clean = text.lower().strip()
    # Strip common leading verbs
    t_target = re.sub(r"^(?:open|launch|start|show|go\s+to|bring\s+up)\s+(?:the\s+|my\s+)?", "", t_clean).strip()
    t_target = re.sub(r"\s+please$", "", t_target).strip()

    # 1. Settings Pages
    for key, (uri, label) in SETTINGS_PAGES.items():
        if t_target == key or t_target == f"{key} settings" or t_target == f"settings for {key}":
            os.startfile(uri)
            return {
                "type": "setting",
                "uri": uri,
                "label": label,
                "line": f"Opening {label}."
            }

    # 2. System Utilities
    for key, (cmd, label) in SYSTEM_UTILITIES.items():
        if t_target == key:
            subprocess.Popen(["cmd", "/c", "start", "", cmd], shell=False)
            return {
                "type": "utility",
                "cmd": cmd,
                "label": label,
                "line": f"Opening {label}."
            }

    # 3. Standard Folders
    for key, (path, label) in STANDARD_FOLDERS.items():
        if t_target == key or t_target == f"{key} folder":
            if os.path.exists(path):
                os.startfile(path)
            else:
                subprocess.Popen(["explorer.exe", path], shell=False)
            return {
                "type": "folder",
                "path": path,
                "label": label,
                "line": f"Opening {label}."
            }

    # 4. Websites
    # Direct URL
    normalized_url = is_url(t_target)
    if normalized_url:
        webbrowser.open(normalized_url)
        return {
            "type": "website",
            "url": normalized_url,
            "label": normalized_url,
            "line": f"Opening {normalized_url}."
        }

    # Known site by bare name
    if t_target in KNOWN_SITES:
        url = KNOWN_SITES[t_target]
        webbrowser.open(url)
        return {
            "type": "website",
            "url": url,
            "label": t_target.capitalize(),
            "line": f"Opening {t_target.capitalize()}."
        }

    # If explicitly phrased as "search for X" or "google X"
    search_m = re.match(r"^(?:search\s+for|google|web\s+search\s+for|search\s+the\s+web\s+for)\s+(.+)$", t_clean)
    if search_m:
        query = search_m.group(1).strip()
        search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        webbrowser.open(search_url)
        return {
            "type": "search",
            "url": search_url,
            "query": query,
            "line": f"Searching for {query}."
        }

    return None
