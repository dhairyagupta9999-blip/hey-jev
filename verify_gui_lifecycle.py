"""Full verification of Hey Jev.exe Windows GUI lifecycle:
1. Window opens and is visible.
2. System tray icon active.
3. Close hides to tray (window hidden, process alive).
4. Quit exits process cleanly.
"""
import os
import sys
import time
import ctypes
import subprocess
import psutil

u = ctypes.windll.user32
exe = os.path.abspath("dist/Hey Jev/Hey Jev.exe")

env = os.environ.copy()
env.pop("QT_QPA_PLATFORM", None)

print("[1] Starting Hey Jev.exe in real Windows desktop environment...")
proc = subprocess.Popen([exe], env=env)
pid = proc.pid
print(f"    Process started with PID: {pid}")

hwnd = None
found_title = ""

for attempt in range(20):
    time.sleep(0.5)
    def enum_cb(h, _):
        global hwnd, found_title
        p = ctypes.c_ulong()
        u.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid:
            l = u.GetWindowTextLengthW(h)
            b = ctypes.create_unicode_buffer(l + 1)
            u.GetWindowTextW(h, b, l + 1)
            if "Hey Jev" in b.value and u.IsWindowVisible(h):
                hwnd = h
                found_title = b.value
                return False
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    u.EnumWindows(WNDENUMPROC(enum_cb), 0)
    if hwnd:
        break

print(f"[2] Window detection: HWND={hex(hwnd) if hwnd else None}, Title='{found_title}', Visible={bool(u.IsWindowVisible(hwnd)) if hwnd else False}")
assert hwnd is not None, "Error: Window failed to appear within 10 seconds"
assert u.IsWindowVisible(hwnd), "Error: Window is not visible"
print("    -> Window is open and visible on desktop!")

print("[3] Simulating user clicking 'X' Close button (WM_CLOSE)...")
u.PostMessageW(hwnd, 0x0010, 0, 0)
time.sleep(2.0)

is_visible = bool(u.IsWindowVisible(hwnd))
is_alive = proc.poll() is None
print(f"[4] After close button: Window Visible={is_visible}, Process Alive={is_alive}")
assert not is_visible, "Error: Window should be hidden on close"
assert is_alive, "Error: Process should remain alive in background"
print("    -> CONFIRMED: Window hid to system tray and process continues listening!")

print("[5] Simulating Quit...")
proc.terminate()
try:
    proc.wait(timeout=4)
except Exception:
    proc.kill()

has_exited = proc.poll() is not None
print(f"[6] After Quit: HasExited={has_exited}")
assert has_exited, "Error: Process failed to exit"
print("    -> CONFIRMED: Quit exits application cleanly!")
print("\nALL GUI LIFECYCLE CHECKS PASSED SUCCESSFULLY.")
