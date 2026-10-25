"""Colors and fonts shared by every window.

Colors can be changed by the user (accent color + background). Widgets read
the module-level values (theme.ACCENT, theme.CARD, ...) every time they paint,
so calling apply() and repainting is enough to recolor everything."""
from __future__ import annotations

import os

from PySide6.QtGui import QColor, QFont, QIcon

# ---- choices offered in the settings window ----

ACCENTS: list[tuple[str, str]] = [
    ("#6C5CE7", "ม่วง"), ("#4F46E5", "คราม"), ("#0EA5E9", "ฟ้า"), ("#14B8A6", "เขียวมิ้นต์"),
    ("#22A55B", "เขียว"), ("#84A611", "เขียวมะนาว"), ("#E0A100", "เหลือง"), ("#F97316", "ส้ม"),
    ("#E5484D", "แดง"), ("#EC4899", "ชมพู"), ("#B4539A", "บานเย็น"), ("#334155", "เทาเข้ม"),
]
DEFAULT_ACCENT = "#6C5CE7"

# card = windows / donut / toast, bg = window background behind cards
BASES: dict[str, dict] = {
    "white": dict(label="ขาว",     card="#FFFFFF", bg="#F6F6F9", line="#ECEBF2", text="#1C1E26", soft="#7C8090", dark=False),
    "gray":  dict(label="เทาอ่อน", card="#FAFAFB", bg="#ECEDF1", line="#E0E1E7", text="#1C1E26", soft="#6F7383", dark=False),
    "cream": dict(label="ครีม",    card="#FFFDF8", bg="#F4F0E6", line="#EAE4D6", text="#26221B", soft="#857D6E", dark=False),
    "sky":   dict(label="ฟ้าอ่อน", card="#FBFDFF", bg="#E9F1FA", line="#DCE6F2", text="#18202B", soft="#6A7789", dark=False),
    "pink":  dict(label="ชมพูอ่อน", card="#FFFBFC", bg="#F8EBEF", line="#EFDDE3", text="#2A1C21", soft="#87707A", dark=False),
    "dark":  dict(label="มืด",     card="#1F2027", bg="#15161B", line="#30313C", text="#ECECF1", soft="#9A9DAB", dark=True),
}
DEFAULT_BASE = "white"

GREEN = QColor("#22B07D")
RED = QColor("#E5484D")


def mix(a: QColor, b: QColor, t: float) -> QColor:
    """t=0 → a, t=1 → b"""
    return QColor(round(a.red() + (b.red() - a.red()) * t),
                  round(a.green() + (b.green() - a.green()) * t),
                  round(a.blue() + (b.blue() - a.blue()) * t))


def _luminance(c: QColor) -> float:
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c.red()) + 0.7152 * ch(c.green()) + 0.0722 * ch(c.blue())


# current colors (filled in by apply)
ACCENT = ACCENT_DARK = ACCENT_SOFT = ON_ACCENT = QColor()
CARD = BG = LINE = TEXT = TEXT_SOFT = HOVER_BG = DASH = SWITCH_OFF = QColor()
WARN_FG = WARN_BG = QColor()
IS_DARK = False
STYLE = ""


def apply(accent_hex: str = DEFAULT_ACCENT, base_key: str = DEFAULT_BASE) -> None:
    global ACCENT, ACCENT_DARK, ACCENT_SOFT, ON_ACCENT, CARD, BG, LINE, TEXT, TEXT_SOFT
    global HOVER_BG, DASH, SWITCH_OFF, WARN_FG, WARN_BG, IS_DARK, STYLE
    base = BASES.get(base_key, BASES[DEFAULT_BASE])
    acc = QColor(accent_hex)
    if not acc.isValid():
        acc = QColor(DEFAULT_ACCENT)
    IS_DARK = base["dark"]
    CARD, BG, LINE = QColor(base["card"]), QColor(base["bg"]), QColor(base["line"])
    TEXT, TEXT_SOFT = QColor(base["text"]), QColor(base["soft"])
    ACCENT = acc
    ACCENT_DARK = mix(acc, QColor("black"), 0.15) if not IS_DARK else mix(acc, QColor("white"), 0.15)
    ACCENT_SOFT = mix(CARD, acc, 0.24 if IS_DARK else 0.12)
    # white text on dark accents, dark text on light ones (yellow, lime…)
    ON_ACCENT = QColor("#1C1E26") if _luminance(acc) > 0.38 else QColor("white")
    HOVER_BG = mix(CARD, TEXT, 0.06)
    DASH = mix(LINE, TEXT_SOFT, 0.35)
    SWITCH_OFF = mix(LINE, TEXT_SOFT, 0.3)
    WARN_FG = QColor("#F2C063") if IS_DARK else QColor("#8A5A00")
    WARN_BG = QColor("#362A12") if IS_DARK else QColor("#FFF6E0")
    STYLE = _build_style()


# Prompt (Thai + Latin, SIL Open Font License) ships inside the app in assets/fonts.
# The rest are fallbacks in case the font files are missing.
FAMILIES = ["Prompt", "Leelawadee UI", "Segoe UI", "Noto Sans Thai", "Loma", "sans-serif"]
_fonts_loaded = False


def load_fonts() -> None:
    """Register the bundled fonts. Call once after QApplication is created."""
    global _fonts_loaded
    if _fonts_loaded:
        return
    from PySide6.QtGui import QFontDatabase
    folder = asset("fonts")
    if os.path.isdir(folder):
        for name in sorted(os.listdir(folder)):
            if name.lower().endswith((".ttf", ".otf")):
                QFontDatabase.addApplicationFont(os.path.join(folder, name))
    _fonts_loaded = True


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


def _build_style() -> str:
    return f"""
* {{ color: {TEXT.name()}; }}
QWidget#Main {{ background: {BG.name()}; }}
QFrame#Card {{ background: {CARD.name()}; border-radius: 14px; border: 1px solid {LINE.name()}; }}
QFrame#Sep {{ background: {LINE.name()}; }}
QLabel#Title {{ font-weight: 700; }}
QLabel#Soft {{ color: {TEXT_SOFT.name()}; }}
QLabel#Hint {{ color: {TEXT_SOFT.name()}; background: {BG.name()}; border-radius: 10px; padding: 10px 12px; }}
QLabel#Warn {{ color: {WARN_FG.name()}; background: {WARN_BG.name()}; border-radius: 10px; padding: 10px 12px; }}
QPushButton#Seg {{
    background: {BG.name()}; border: none; border-radius: 9px; padding: 8px 0px;
    color: {TEXT_SOFT.name()}; font-weight: 600;
}}
QPushButton#Seg:hover {{ color: {TEXT.name()}; }}
QPushButton#Seg:checked {{ background: {ACCENT.name()}; color: {ON_ACCENT.name()}; }}
QPushButton#Primary {{
    background: {ACCENT.name()}; color: {ON_ACCENT.name()}; border: none; border-radius: 10px;
    padding: 9px 18px; font-weight: 600;
}}
QPushButton#Primary:hover {{ background: {ACCENT_DARK.name()}; }}
QPushButton#Ghost {{
    background: transparent; color: {TEXT_SOFT.name()}; border: 1px solid {LINE.name()};
    border-radius: 10px; padding: 8px 14px;
}}
QPushButton#Ghost:hover {{ color: {TEXT.name()}; border-color: {DASH.name()}; }}
QPushButton#Link {{ background: transparent; border: none; color: {TEXT_SOFT.name()}; padding: 2px; }}
QPushButton#Link:hover {{ color: {RED.name()}; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {DASH.name()}; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
"""


apply()
