"""Colors and fonts shared by every window."""
from __future__ import annotations

import os

from PySide6.QtGui import QColor, QFont, QIcon

ACCENT = QColor("#6C5CE7")
ACCENT_DARK = QColor("#5646D6")
ACCENT_SOFT = QColor("#EFEDFD")
GREEN = QColor("#22B07D")
RED = QColor("#E5484D")
TEXT = QColor("#1C1E26")
TEXT_SOFT = QColor("#7C8090")
LINE = QColor("#ECEBF2")
BG = QColor("#F6F6F9")
CARD = QColor("#FFFFFF")

# Segoe UI for Latin, Leelawadee UI is the modern Thai font that ships with Windows.
FAMILIES = ["Segoe UI Variable Text", "Segoe UI", "Leelawadee UI",
            "Noto Sans Thai", "Noto Sans", "Loma", "sans-serif"]


def font(px: float, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    f = QFont()
    f.setFamilies(FAMILIES)
    f.setPixelSize(max(1, round(px)))
    f.setWeight(weight)
    f.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    return f


def asset(name: str) -> str:
    from ..converter import resource_dir
    return os.path.join(resource_dir(), "assets", name)


def app_icon() -> QIcon:
    for name in ("converz.ico", "converz.png"):
        p = asset(name)
        if os.path.exists(p):
            return QIcon(p)
    return QIcon()


STYLE = f"""
* {{ color: {TEXT.name()}; }}
QWidget#Main {{ background: {BG.name()}; }}
QFrame#Card {{ background: {CARD.name()}; border-radius: 14px; border: 1px solid {LINE.name()}; }}
QLabel#Title {{ font-weight: 700; }}
QLabel#Soft {{ color: {TEXT_SOFT.name()}; }}
QLabel#Hint {{ color: {TEXT_SOFT.name()}; background: {BG.name()}; border-radius: 10px; padding: 10px 12px; }}
QLabel#Warn {{ color: #8A5A00; background: #FFF6E0; border-radius: 10px; padding: 10px 12px; }}
QPushButton#Seg {{
    background: {BG.name()}; border: none; border-radius: 9px; padding: 8px 0px;
    color: {TEXT_SOFT.name()}; font-weight: 600;
}}
QPushButton#Seg:hover {{ color: {TEXT.name()}; }}
QPushButton#Seg:checked {{ background: {ACCENT.name()}; color: white; }}
QPushButton#Primary {{
    background: {ACCENT.name()}; color: white; border: none; border-radius: 10px;
    padding: 9px 18px; font-weight: 600;
}}
QPushButton#Primary:hover {{ background: {ACCENT_DARK.name()}; }}
QPushButton#Ghost {{
    background: transparent; color: {TEXT_SOFT.name()}; border: 1px solid {LINE.name()};
    border-radius: 10px; padding: 8px 14px;
}}
QPushButton#Ghost:hover {{ color: {TEXT.name()}; border-color: #D6D4E2; }}
QPushButton#Link {{ background: transparent; border: none; color: {TEXT_SOFT.name()}; padding: 2px; }}
QPushButton#Link:hover {{ color: {RED.name()}; }}
QScrollArea {{ border: none; background: transparent; }}
"""
