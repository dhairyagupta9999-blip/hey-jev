"""Windows 10/11 system, media, app, and volume actions for Hey Jev."""
import os
import re
import time
import winreg
import ctypes
import subprocess
import psutil

# Level percentages
LEVELS = {"silent": 0, "quiet": 25, "medium": 50, "loud": 75, "max": 100}

# Virtual Keys
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_STOP       = 0xB2
VK_MEDIA_PLAY_PAUSE = 0xB3
VK_CONTROL          = 0x11
VK_T                = 0x54
KEYEVENTF_KEYUP     = 0x0002

user32 = ctypes.windll.user32

def send_vk(vk_code):
    """Synthesize a single key down and key up event."""
    user32.keybd_event(vk_code, 0, 0, 0)
    time.sleep(0.02)
    user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)

# --------------------------------------------------------------------------- Master Volume via pycaw
def _get_master_endpoint():
    try:
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        from comtypes import CLSCTX_ALL
        speakers = AudioUtilities.GetSpeakers()
        if not speakers:
            return None
        interface = speakers.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return interface.QueryInterface(IAudioEndpointVolume)
    except Exception as e:
        print(f"  [pycaw error]: {e}")
        return None

def get_volume() -> int:
    vol = _get_master_endpoint()
    if vol:
        return int(round(vol.GetMasterVolumeLevelScalar() * 100))
    return 50

def set_volume(level_percent: int):
    vol = _get_master_endpoint()
    if vol:
        scalar = max(0.0, min(1.0, level_percent / 100.0))
        vol.SetMasterVolumeLevelScalar(scalar, None)

def set_mute(muted: bool):
    vol = _get_master_endpoint()
    if vol:
        vol.SetMute(1 if muted else 0, None)

# --------------------------------------------------------------------------- Spotify Session Volume
def _get_spotify_session():
    try:
        from pycaw.pycaw import AudioUtilities
        for session in AudioUtilities.GetAllSessions():
            if session.Process and session.Process.name().lower() == "spotify.exe":
                return session
    except Exception:
        pass
    return None

def get_spotify_volume() -> int:
    s = _get_spotify_session()
    if s and s.SimpleAudioVolume:
        return int(round(s.SimpleAudioVolume.GetMasterVolume() * 100))
    return get_volume()

def set_spotify_volume(level_percent: int):
    s = _get_spotify_session()
    if s and s.SimpleAudioVolume:
        scalar = max(0.0, min(1.0, level_percent / 100.0))
        s.SimpleAudioVolume.SetMasterVolume(scalar, None)

def is_audio_playing() -> bool:
    """Check if audio is actively playing (via Spotify session peak or any system session)."""
    s = _get_spotify_session()
    if s:
        try:
            meter = s._ctl.QueryInterface(s._ctl._iid_) # AudioMeterInformation
            # Check peak value
            from pycaw.pycaw import IAudioMeterInformation
            meter = s.QueryInterface(IAudioMeterInformation)
            if meter and meter.GetPeakValue() > 0.001:
                return True
        except Exception:
            pass
    return False

# --------------------------------------------------------------------------- Media Transport (State-Aware)
def media_play():
    """State-aware play: only toggle if not already playing."""
    if not is_audio_playing():
        send_vk(VK_MEDIA_PLAY_PAUSE)

def media_pause():
    """State-aware pause: only toggle if audio is actively playing."""
    if is_audio_playing():
        send_vk(VK_MEDIA_PLAY_PAUSE)

def media_next():
    send_vk(VK_MEDIA_NEXT_TRACK)

def media_previous():
    send_vk(VK_MEDIA_PREV_TRACK)
    time.sleep(0.3)
    send_vk(VK_MEDIA_PREV_TRACK)

# --------------------------------------------------------------------------- Dark Mode
def set_dark_mode(dark: bool):
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            val = 0 if dark else 1
            winreg.SetValueEx(key, "AppsUseLightTheme", 0, winreg.REG_DWORD, val)
            winreg.SetValueEx(key, "SystemUsesLightTheme", 0, winreg.REG_DWORD, val)
        # Broadcast WM_SETTINGCHANGE
        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        SMTO_ABORTIFHUNG = 0x0002
        res = ctypes.c_ulong()
        user32.SendMessageTimeoutW(
            HWND_BROADCAST, WM_SETTINGCHANGE, 0, "ImmersiveColorSet",
            SMTO_ABORTIFHUNG, 1000, ctypes.byref(res)
        )
    except Exception as e:
        print(f"  [dark_mode error]: {e}")

def toggle_dark_mode():
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
            val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            is_light = bool(val)
        set_dark_mode(is_light)
    except Exception as e:
        print(f"  [toggle dark mode error]: {e}")

# --------------------------------------------------------------------------- System Actions
def lock_screen():
    user32.LockWorkStation()

def sleep_computer():
    ctypes.windll.PowrProf.SetSuspendState(False, False, False)

# --------------------------------------------------------------------------- App Control
def find_process_by_name(name: str):
    name_clean = name.lower().replace(".exe", "")
    for p in psutil.process_iter(["pid", "name"]):
        try:
            p_name = p.info["name"].lower()
            if name_clean in p_name:
                return p
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return None

def quit_app(proc_name: str):
    """Graceful WM_CLOSE, wait 1.5s, force-kill process tree if still alive."""
    p = find_process_by_name(proc_name)
    if not p:
        return
    try:
        # Try graceful close via windows
        for w in psutil.Process(p.pid).children(recursive=True) + [p]:
            try:
                w.terminate()
            except Exception:
                pass
        time.sleep(1.5)
        if p.is_running():
            # Force kill tree for tray-minimizing apps (Slack, Discord, Spotify)
            for child in p.children(recursive=True):
                try:
                    child.kill()
                except Exception:
                    pass
            p.kill()
    except Exception as e:
        print(f"  [quit_app error]: {e}")

def minimize_app(proc_name: str):
    """Minimize top-level window (never bare SW_HIDE)."""
    p = find_process_by_name(proc_name)
    if not p:
        return
    # Enumerate windows and minimize
    SW_MINIMIZE = 6
    def enum_cb(hwnd, lparam):
        if user32.IsWindowVisible(hwnd):
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == p.pid:
                user32.ShowWindow(hwnd, SW_MINIMIZE)
        return True
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    user32.EnumWindows(WNDENUMPROC(enum_cb), 0)

def focus_app(proc_name: str):
    """Restore and bring top-level window to front."""
    p = find_process_by_name(proc_name)
    if not p:
        return
    SW_RESTORE = 9
    def enum_cb(hwnd, lparam):
        if user32.IsWindowVisible(hwnd) or True:
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == p.pid:
                user32.ShowWindow(hwnd, SW_RESTORE)
                user32.SetForegroundWindow(hwnd)
                return False
        return True
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    user32.EnumWindows(WNDENUMPROC(enum_cb), 0)

def open_url(url: str, browser_name: str | None = None):
    """Open URL in default or specified browser."""
    if not url.startswith("http"):
        url = "https://" + url
    if browser_name:
        p = find_process_by_name(browser_name)
        if p:
            subprocess.Popen([p.name(), url])
            return
    os.startfile(url)

def browser_new_tab(browser_name: str | None = None):
    """Focus browser and synthesize Ctrl+T."""
    if browser_name:
        focus_app(browser_name)
    time.sleep(0.15)
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(VK_T, 0, 0, 0)
    time.sleep(0.05)
    user32.keybd_event(VK_T, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
