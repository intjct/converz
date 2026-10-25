"""Small Windows-only helpers. Every function is safe to call on other systems
(it just does nothing), which keeps the app testable on Linux/macOS."""
from __future__ import annotations

import os
import subprocess
import sys

from . import APP_NAME

IS_WIN = os.name == "nt"

VK = {"ctrl": 0x11, "shift": 0x10, "alt": 0x12}
VK_LBUTTON, VK_RBUTTON, VK_ESCAPE = 0x01, 0x02, 0x1B

if IS_WIN:
    import ctypes
    from ctypes import wintypes

    _user32 = ctypes.windll.user32
    _user32.GetAsyncKeyState.restype = ctypes.c_short

    class _POINT(ctypes.Structure):
        _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


def key_down(vk: int) -> bool:
    if not IS_WIN:
        return False
    return bool(_user32.GetAsyncKeyState(vk) & 0x8000)


def left_button_down() -> bool:
    """Physical primary button, respecting left-handed mouse settings."""
    if not IS_WIN:
        return False
    swapped = _user32.GetSystemMetrics(23)  # SM_SWAPBUTTON
    return key_down(VK_RBUTTON if swapped else VK_LBUTTON)


def cursor_pos() -> tuple[int, int] | None:
    """Cursor in physical pixels (we convert with Qt where needed)."""
    if not IS_WIN:
        return None
    pt = _POINT()
    _user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def exe_command() -> list[str]:
    """How to start this program again (frozen .exe or python -m converz)."""
    if getattr(sys, "frozen", False):
        return [sys.executable]
    exe = sys.executable
    pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    return [pyw if os.path.exists(pyw) else exe, "-m", "converz"]


# ---- start with Windows (HKCU\...\Run, no admin needed) ----

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def set_start_with_windows(on: bool) -> None:
    if not IS_WIN:
        return
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            cmd = " ".join(f'"{p}"' for p in exe_command()) + " --background"
            winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(k, APP_NAME)
            except FileNotFoundError:
                pass


# ---- right-click > Send to > Converz ----

def _sendto_link() -> str | None:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return None
    return os.path.join(appdata, "Microsoft", "Windows", "SendTo", f"{APP_NAME} (แปลงไฟล์).lnk")


def set_send_to(on: bool) -> None:
    if not IS_WIN:
        return
    link = _sendto_link()
    if not link:
        return
    if not on:
        if os.path.exists(link):
            os.remove(link)
        return
    cmd = exe_command()
    target, args = cmd[0], " ".join(f'"{a}"' for a in cmd[1:])
    icon = sys.executable if getattr(sys, "frozen", False) else target
    ps = (
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:CZ_LINK);"
        "$s.TargetPath=$env:CZ_TARGET;$s.Arguments=$env:CZ_ARGS;"
        "$s.IconLocation=$env:CZ_ICON;$s.Description='Converz';$s.Save()"
    )
    env = dict(os.environ, CZ_LINK=link, CZ_TARGET=target, CZ_ARGS=args, CZ_ICON=icon)
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                   env=env, creationflags=0x08000000, timeout=20)


def show_in_folder(path: str) -> None:
    path = os.path.abspath(path)
    if IS_WIN:
        subprocess.Popen(["explorer", "/select,", path])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-R", path])
    else:
        subprocess.Popen(["xdg-open", os.path.dirname(path)])
