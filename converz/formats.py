"""What kinds of files Converz understands and what it can turn them into."""
from __future__ import annotations

import os
from collections import Counter
from dataclasses import dataclass

IMAGE = "image"
VIDEO = "video"
AUDIO = "audio"

KIND_NAMES_TH = {IMAGE: "รูป", VIDEO: "วิดีโอ", AUDIO: "ไฟล์เสียง"}

EXTENSIONS = {
    IMAGE: {"jpg", "jpeg", "jfif", "png", "webp", "bmp", "tif", "tiff", "gif",
            "ico", "heic", "heif", "avif"},
    VIDEO: {"mp4", "mov", "mkv", "avi", "webm", "wmv", "flv", "m4v", "3gp",
            "mts", "m2ts", "ts", "mpg", "mpeg", "vob"},
    AUDIO: {"mp3", "wav", "m4a", "aac", "flac", "ogg", "oga", "opus", "wma",
            "aiff", "aif", "amr"},
}

# Extensions that mean the same thing (so "JPG" is hidden for a .jpeg file).
SAME_AS = {"jpeg": "jpg", "jfif": "jpg", "tif": "tiff", "heif": "heic",
           "aif": "aiff", "oga": "ogg", "m4v": "mp4"}


@dataclass(frozen=True)
class Action:
    id: str          # unique key, also used for usage stats
    kind: str        # IMAGE / VIDEO / AUDIO
    label: str       # big text in the donut
    sub: str         # small text under it
    out_ext: str | None  # target extension (None = keep the input's extension)


ACTIONS: list[Action] = [
    # ---- images ----
    Action("img_jpg", IMAGE, "JPG", "รูปทั่วไป", "jpg"),
    Action("img_png", IMAGE, "PNG", "พื้นใสได้", "png"),
    Action("img_pdf", IMAGE, "PDF", "เอกสาร", "pdf"),
    Action("img_webp", IMAGE, "WEBP", "ไฟล์เล็ก", "webp"),
    Action("img_compress", IMAGE, "บีบไฟล์", "เล็กลง", None),
    Action("img_half", IMAGE, "ย่อครึ่ง", "50%", None),
    Action("img_ico", IMAGE, "ICO", "ไอคอน", "ico"),
    Action("img_bmp", IMAGE, "BMP", "", "bmp"),
    Action("img_tiff", IMAGE, "TIFF", "งานพิมพ์", "tiff"),
    # ---- video ----
    Action("vid_mp4", VIDEO, "MP4", "เปิดได้ทุกที่", "mp4"),
    Action("vid_mp3", VIDEO, "MP3", "ดึงเสียงออก", "mp3"),
    Action("vid_compress", VIDEO, "บีบไฟล์", "เล็กลง", "mp4"),
    Action("vid_gif", VIDEO, "GIF", "ภาพเคลื่อนไหว", "gif"),
    Action("vid_mute", VIDEO, "ปิดเสียง", "ตัดเสียงทิ้ง", None),
    Action("vid_mov", VIDEO, "MOV", "", "mov"),
    Action("vid_mkv", VIDEO, "MKV", "", "mkv"),
    Action("vid_webm", VIDEO, "WEBM", "เว็บ", "webm"),
    Action("vid_avi", VIDEO, "AVI", "เครื่องเก่า", "avi"),
    # ---- audio ----
    Action("aud_mp3", AUDIO, "MP3", "ทั่วไป", "mp3"),
    Action("aud_wav", AUDIO, "WAV", "ไม่ลดคุณภาพ", "wav"),
    Action("aud_m4a", AUDIO, "M4A", "iPhone", "m4a"),
    Action("aud_compress", AUDIO, "บีบไฟล์", "เล็กลง", "mp3"),
    Action("aud_flac", AUDIO, "FLAC", "เสียงดีสุด", "flac"),
    Action("aud_ogg", AUDIO, "OGG", "", "ogg"),
    Action("aud_aac", AUDIO, "AAC", "", "aac"),
]

ACTIONS_BY_ID = {a.id: a for a in ACTIONS}


def ext_of(path: str) -> str:
    e = os.path.splitext(path)[1].lower().lstrip(".")
    return SAME_AS.get(e, e)


def kind_of(path: str) -> str | None:
    e = os.path.splitext(path)[1].lower().lstrip(".")
    for kind, exts in EXTENSIONS.items():
        if e in exts:
            return kind
    return None


@dataclass
class Selection:
    """The files being dragged, sorted into the kind we will work on."""
    kind: str | None
    files: list[str]         # files of that kind (what will be converted)
    skipped: list[str]       # files we can't use for this kind

    @property
    def count(self) -> int:
        return len(self.files)


def _expand(paths: list[str]) -> list[str]:
    """Files stay as they are; a dragged folder means the files directly inside it."""
    out: list[str] = []
    for p in paths:
        if os.path.isdir(p):
            try:
                names = sorted(os.listdir(p))
            except OSError:
                continue
            out += [os.path.join(p, n) for n in names
                    if kind_of(n) and os.path.isfile(os.path.join(p, n))]
        elif os.path.isfile(p):
            out.append(p)
    return out


def make_selection(paths: list[str]) -> Selection:
    paths = _expand(paths)
    kinds = Counter(k for k in (kind_of(p) for p in paths) if k)
    if not kinds:
        return Selection(None, [], paths)
    kind = kinds.most_common(1)[0][0]
    files = [p for p in paths if kind_of(p) == kind]
    skipped = [p for p in paths if kind_of(p) != kind]
    return Selection(kind, files, skipped)


def actions_for(sel: Selection, usage: dict[str, int] | None = None) -> list[Action]:
    """Actions to show in the donut, most used first."""
    if not sel.kind:
        return []
    exts = {ext_of(p) for p in sel.files}
    out = []
    for a in ACTIONS:
        if a.kind != sel.kind:
            continue
        # Converting every file to the format it already is makes no sense.
        if a.out_ext and exts == {a.out_ext} and a.id not in ("vid_compress", "aud_compress"):
            continue
        out.append(a)
    if usage:
        base = {a.id: i for i, a in enumerate(out)}
        # Stable: used actions float to the top, the rest keep their default order.
        out.sort(key=lambda a: (-usage.get(a.id, 0), base[a.id]))
    return out


def display_label(action: Action, sel: Selection) -> tuple[str, str]:
    """Label + sub-label, adjusted for the current selection."""
    if action.id == "img_pdf" and sel.count > 1:
        return "PDF", f"รวม {sel.count} รูป"
    return action.label, action.sub
