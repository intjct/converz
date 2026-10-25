"""The conversion engine. No GUI code here so it can be tested on its own.

Images and PDFs are handled with Pillow; video and audio with a bundled ffmpeg.
Original files are never modified or overwritten.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import threading
import zlib
from dataclasses import dataclass, field
from typing import Callable

from .formats import ACTIONS_BY_ID, AUDIO, IMAGE, VIDEO, ext_of

ProgressCB = Callable[[float, str], None]  # (0..1, file name)

QUALITY = ("small", "balanced", "best")


class ConvertError(Exception):
    """An error with a message that can be shown to the user (Thai)."""


@dataclass
class Result:
    outputs: list[str] = field(default_factory=list)
    errors: list[tuple[str, str]] = field(default_factory=list)  # (file, message)
    cancelled: bool = False


# --------------------------------------------------------------------------- helpers

def resource_dir() -> str:
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_ffmpeg() -> str | None:
    name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    base = resource_dir()
    for cand in (os.path.join(base, "ffmpeg", name), os.path.join(base, name),
                 os.path.join(os.path.dirname(sys.executable), name)):
        if os.path.isfile(cand):
            return cand
    return shutil.which("ffmpeg")


def _no_window() -> dict:
    """Keep Windows from flashing a black console window for every ffmpeg run."""
    if os.name == "nt":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return {"creationflags": 0x08000000, "startupinfo": si}  # CREATE_NO_WINDOW
    return {}


def unique_path(path: str) -> str:
    """'a.mp4' -> 'a (1).mp4' if it exists, and so on."""
    if not os.path.exists(path):
        return path
    root, ext = os.path.splitext(path)
    i = 1
    while os.path.exists(f"{root} ({i}){ext}"):
        i += 1
    return f"{root} ({i}){ext}"


def output_path(src: str, ext: str, suffix: str = "", out_dir: str | None = None) -> str:
    folder = out_dir or os.path.dirname(os.path.abspath(src))
    stem = os.path.splitext(os.path.basename(src))[0]
    return unique_path(os.path.join(folder, f"{stem}{suffix}.{ext}"))


def natural_key(path: str):
    name = os.path.basename(path).lower()
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", name)]


# --------------------------------------------------------------------------- images

_heif_ready = False


def _open_image(path: str):
    global _heif_ready
    from PIL import Image, ImageOps
    if not _heif_ready:
        try:
            import pillow_heif
            pillow_heif.register_heif_opener()
            try:
                pillow_heif.register_avif_opener()
            except Exception:
                pass
        except Exception:
            pass
        _heif_ready = True
    try:
        im = Image.open(path)
        im.seek(0)  # first frame of animated files
        icc = im.info.get("icc_profile")
        im = ImageOps.exif_transpose(im)  # phone photos: fix rotation
        im.load()
    except Exception as e:
        raise ConvertError("เปิดรูปนี้ไม่ได้ (ไฟล์อาจเสียหรือไม่ใช่รูปจริง)") from e
    if icc:
        im.info["icc_profile"] = icc
    return im


def _has_alpha(im) -> bool:
    return im.mode in ("RGBA", "LA", "PA") or (im.mode == "P" and "transparency" in im.info)


def _flatten(im, bg=(255, 255, 255)):
    """Remove transparency by placing the image on white."""
    from PIL import Image
    if _has_alpha(im):
        rgba = im.convert("RGBA")
        out = Image.new("RGB", rgba.size, bg)
        out.paste(rgba, mask=rgba.split()[-1])
        return out
    return im.convert("RGB")


def _keep_alpha(im):
    return im.convert("RGBA") if _has_alpha(im) else im.convert("RGB")


JPG_Q = {"small": 72, "balanced": 88, "best": 95}
WEBP_Q = {"small": 70, "balanced": 85, "best": 95}


def save_image(im, dest: str, fmt: str, quality: str) -> None:
    icc = im.info.get("icc_profile")
    extra = {"icc_profile": icc} if icc else {}
    if fmt == "jpg":
        _flatten(im).save(dest, "JPEG", quality=JPG_Q[quality], optimize=True, **extra)
    elif fmt == "png":
        _keep_alpha(im).save(dest, "PNG", optimize=True, **extra)
    elif fmt == "webp":
        _keep_alpha(im).save(dest, "WEBP", quality=WEBP_Q[quality], method=5, **extra)
    elif fmt == "bmp":
        _flatten(im).save(dest, "BMP")
    elif fmt == "tiff":
        _keep_alpha(im).save(dest, "TIFF", compression="tiff_lzw", **extra)
    elif fmt == "ico":
        from PIL import Image
        src = im.convert("RGBA")
        side = max(src.size)
        square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        square.paste(src, ((side - src.width) // 2, (side - src.height) // 2))
        sizes = [(s, s) for s in (16, 24, 32, 48, 64, 128, 256) if s <= max(side, 16)]
        square.save(dest, "ICO", sizes=sizes)
    elif fmt == "gif":
        im.convert("RGBA" if _has_alpha(im) else "RGB").save(dest, "GIF")
    else:
        raise ConvertError(f"ยังไม่รองรับการบันทึกเป็น {fmt.upper()}")


def convert_image(src: str, action_id: str, quality: str, out_dir: str | None) -> str:
    from PIL import Image
    im = _open_image(src)
    src_ext = ext_of(src)
    # Formats we can read but don't write keep their look as JPG.
    native = src_ext if src_ext in ("jpg", "png", "webp", "bmp", "tiff", "gif") else "jpg"

    if action_id == "img_half":
        w, h = max(1, im.width // 2), max(1, im.height // 2)
        icc = im.info.get("icc_profile")
        im = im.resize((w, h), Image.LANCZOS)
        if icc:
            im.info["icc_profile"] = icc
        dest = output_path(src, native, "_half", out_dir)
        save_image(im, dest, native, quality)
        return dest

    if action_id == "img_compress":
        max_side = {"small": 1600, "balanced": 2560, "best": 3200}[quality]
        icc = im.info.get("icc_profile")
        if max(im.size) > max_side:
            im.thumbnail((max_side, max_side), Image.LANCZOS)
        if icc:
            im.info["icc_profile"] = icc
        q = {"small": "small", "balanced": "small", "best": "balanced"}[quality]
        if _has_alpha(im):
            dest = output_path(src, "png", "_compressed", out_dir)
            im.convert("RGBA").quantize(256, method=Image.Quantize.FASTOCTREE).save(
                dest, "PNG", optimize=True)
        elif native == "webp":
            dest = output_path(src, "webp", "_compressed", out_dir)
            save_image(im, dest, "webp", q)
        else:
            dest = output_path(src, "jpg", "_compressed", out_dir)
            save_image(im, dest, "jpg", q)
        return dest

    fmt = ACTIONS_BY_ID[action_id].out_ext
    if fmt == "pdf":
        dest = output_path(src, "pdf", "", out_dir)
        images_to_pdf([src], dest, quality)
        return dest
    dest = output_path(src, fmt, "", out_dir)
    save_image(im, dest, fmt, quality)
    return dest


def images_to_pdf(paths: list[str], dest: str, quality: str = "balanced",
                  progress: Callable[[int], None] | None = None,
                  cancel: threading.Event | None = None) -> None:
    """Write one PDF with one image per page. Every page is A4 wide and as tall
    as the picture needs. Written page by page so 200 photos don't eat RAM."""
    from io import BytesIO
    from PIL import Image

    PAGE_W = 595.28  # A4 width in points
    max_px = {"small": 1240, "balanced": 2480, "best": 3508}[quality]
    jpg_q = {"small": 70, "balanced": 85, "best": 92}[quality]

    offsets: list[int] = []
    tmp = dest + ".part"
    n = len(paths)
    # object numbers: 1 catalog, 2 pages, then per page: page, image, contents
    try:
        with open(tmp, "wb") as f:
            def obj(num: int, body: bytes):
                while len(offsets) < num:
                    offsets.append(0)
                offsets[num - 1] = f.tell()
                f.write(f"{num} 0 obj\n".encode() + body + b"\nendobj\n")

            f.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
            kids = " ".join(f"{3 + i * 3} 0 R" for i in range(n))
            obj(1, b"<< /Type /Catalog /Pages 2 0 R >>")
            obj(2, f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode())
            for i, p in enumerate(paths):
                if cancel and cancel.is_set():
                    raise _Cancelled()
                try:
                    im = _flatten(_open_image(p))
                except ConvertError as e:
                    raise ConvertError(f"{os.path.basename(p)}: {e}") from e
                if im.width > max_px:
                    im = im.resize((max_px, max(1, round(im.height * max_px / im.width))),
                                   Image.LANCZOS)
                buf = BytesIO()
                im.save(buf, "JPEG", quality=jpg_q, optimize=True)
                data = buf.getvalue()
                page_h = PAGE_W * im.height / im.width
                pnum, inum, cnum = 3 + i * 3, 4 + i * 3, 5 + i * 3
                obj(pnum, (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_W:.2f} {page_h:.2f}] "
                           f"/Resources << /XObject << /Im0 {inum} 0 R >> >> /Contents {cnum} 0 R >>").encode())
                obj(inum, (f"<< /Type /XObject /Subtype /Image /Width {im.width} /Height {im.height} "
                           f"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode "
                           f"/Length {len(data)} >>\nstream\n").encode() + data + b"\nendstream")
                content = zlib.compress(f"q {PAGE_W:.2f} 0 0 {page_h:.2f} 0 0 cm /Im0 Do Q".encode())
                obj(cnum, f"<< /Length {len(content)} /Filter /FlateDecode >>\nstream\n".encode()
                    + content + b"\nendstream")
                if progress:
                    progress(i + 1)
            xref = f.tell()
            f.write(f"xref\n0 {len(offsets) + 1}\n0000000000 65535 f \n".encode())
            for off in offsets:
                f.write(f"{off:010d} 00000 n \n".encode())
            f.write(f"trailer\n<< /Size {len(offsets) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
        os.replace(tmp, dest)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


# --------------------------------------------------------------------------- video / audio

class _Cancelled(Exception):
    pass


@dataclass
class Probe:
    duration: float = 0.0
    vcodec: str | None = None
    acodec: str | None = None
    width: int = 0
    height: int = 0


def probe(ffmpeg: str, path: str) -> Probe:
    r = subprocess.run([ffmpeg, "-hide_banner", "-i", path], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", **_no_window())
    info = Probe()
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", r.stderr)
    if m:
        info.duration = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])
    for line in r.stderr.splitlines():
        if "Stream #" not in line:
            continue
        if " Video: " in line and info.vcodec is None and "attached pic" not in line:
            info.vcodec = line.split(" Video: ")[1].split()[0].strip(",")
            d = re.search(r",\s*(\d{2,5})x(\d{2,5})", line)
            if d:
                info.width, info.height = int(d[1]), int(d[2])
        elif " Audio: " in line and info.acodec is None:
            info.acodec = line.split(" Audio: ")[1].split()[0].strip(",")
    # Phone videos are often stored sideways with a rotation flag.
    if re.search(r"rotation of -?90|rotate\s*:\s*-?(90|270)", r.stderr):
        info.width, info.height = info.height, info.width
    if info.vcodec is None and info.acodec is None:
        raise ConvertError("เปิดไฟล์นี้ไม่ได้ (ไฟล์อาจเสีย หรือไม่ใช่วิดีโอ/เสียงจริง)")
    return info


CRF = {"small": 28, "balanced": 22, "best": 18}
ABR = {"small": "128k", "balanced": "192k", "best": "320k"}


def _x264(quality: str, crf_add: int = 0) -> list[str]:
    preset = "medium" if quality == "best" else "veryfast"
    return ["-c:v", "libx264", "-preset", preset, "-crf", str(CRF[quality] + crf_add),
            "-pix_fmt", "yuv420p"]


def _scale_cap(p: Probe, cap: int) -> list[str]:
    if max(p.width, p.height) <= cap or not p.width:
        return []
    return ["-vf", f"scale={cap}:{cap}:force_original_aspect_ratio=decrease:force_divisible_by=2"]


def ffmpeg_args(action_id: str, p: Probe, quality: str, src_ext: str) -> list[list[str]]:
    """Return one or more argument lists to try in order (fast copy first)."""
    a_map = ["-map", "0:a:0?"]
    v_map = ["-map", "0:v:0"]
    aac = ["-c:a", "aac", "-b:a", ABR[quality]]
    mp3 = ["-c:a", "libmp3lame", "-b:a", ABR[quality]]
    faststart = ["-movflags", "+faststart"]

    def need_audio():
        if not p.acodec:
            raise ConvertError("ไฟล์นี้ไม่มีเสียง")

    if action_id in ("vid_mp4", "vid_mov"):
        tries = []
        if p.vcodec == "h264" and p.acodec in (None, "aac", "mp3"):
            tries.append(v_map + a_map + ["-c", "copy"] + faststart)
        tries.append(v_map + a_map + _x264(quality) + aac + faststart)
        return tries
    if action_id == "vid_mkv":
        return [["-map", "0:v:0", "-map", "0:a?", "-c", "copy"],
                v_map + ["-map", "0:a?"] + _x264(quality) + aac]
    if action_id == "vid_webm":
        crf = {"small": 40, "balanced": 33, "best": 28}[quality]
        return [v_map + a_map + ["-c:v", "libvpx-vp9", "-b:v", "0", "-crf", str(crf),
                                 "-deadline", "realtime", "-cpu-used", "8", "-row-mt", "1",
                                 "-c:a", "libopus", "-b:a", "128k"]]
    if action_id == "vid_avi":
        q = {"small": 6, "balanced": 4, "best": 2}[quality]
        return [v_map + a_map + ["-c:v", "mpeg4", "-q:v", str(q), "-vtag", "XVID",
                                 "-c:a", "libmp3lame", "-q:a", "4"]]
    if action_id == "vid_gif":
        fps, w = {"small": (10, 360), "balanced": (12, 480), "best": (15, 640)}[quality]
        vf = (f"fps={fps},scale='min({w},iw)':-2:flags=lanczos,split[a][b];"
              f"[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4")
        return [v_map + ["-vf", vf, "-loop", "0"]]
    if action_id == "vid_compress":
        cap = {"small": 1280, "balanced": 1920, "best": 1920}[quality]
        return [v_map + a_map + _x264(quality, crf_add=6) + _scale_cap(p, cap)
                + ["-c:a", "aac", "-b:a", "128k"] + faststart]
    if action_id == "vid_mute":
        tries = [v_map + ["-c:v", "copy", "-an"]]
        tries.append(v_map + _x264(quality) + ["-an"])
        return tries
    if action_id in ("vid_mp3", "aud_mp3"):
        need_audio()
        return [["-vn", "-map", "0:a:0"] + mp3]
    if action_id == "aud_wav":
        return [["-vn", "-map", "0:a:0", "-c:a", "pcm_s16le"]]
    if action_id == "aud_m4a":
        tries = []
        if p.acodec == "aac":
            tries.append(["-vn", "-map", "0:a:0", "-c:a", "copy"] + faststart)
        tries.append(["-vn", "-map", "0:a:0"] + aac + faststart)
        return tries
    if action_id == "aud_aac":
        return [["-vn", "-map", "0:a:0"] + aac + ["-f", "adts"]]
    if action_id == "aud_flac":
        return [["-vn", "-map", "0:a:0", "-c:a", "flac"]]
    if action_id == "aud_ogg":
        q = {"small": 3, "balanced": 5, "best": 8}[quality]
        return [["-vn", "-map", "0:a:0", "-c:a", "libvorbis", "-q:a", str(q)]]
    if action_id == "aud_compress":
        return [["-vn", "-map", "0:a:0", "-c:a", "libmp3lame", "-b:a", "96k"]]
    raise ConvertError("ไม่รู้จักคำสั่งนี้")


def _suffix(action_id: str) -> str:
    return {"vid_compress": "_compressed", "aud_compress": "_compressed",
            "vid_mute": "_mute"}.get(action_id, "")


def _run_ffmpeg(ffmpeg: str, src: str, dest: str, args: list[str], duration: float,
                on_frac: Callable[[float], None], cancel: threading.Event | None) -> tuple[bool, str]:
    cmd = [ffmpeg, "-hide_banner", "-nostdin", "-y", "-i", src, *args,
           "-progress", "pipe:1", "-nostats", dest]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="replace", **_no_window())
    err_tail: list[str] = []

    def read_err():
        for line in proc.stderr:
            err_tail.append(line)
            del err_tail[:-30]
    t = threading.Thread(target=read_err, daemon=True)
    t.start()
    for line in proc.stdout:
        if cancel and cancel.is_set():
            proc.kill()
            proc.wait()
            raise _Cancelled()
        if line.startswith("out_time_us=") or line.startswith("out_time_ms="):
            try:
                us = int(line.split("=", 1)[1])
            except ValueError:
                continue
            if duration > 0:
                on_frac(min(1.0, us / 1_000_000 / duration))
    proc.wait()
    t.join(timeout=2)
    return proc.returncode == 0, "".join(err_tail)


def convert_media(ffmpeg: str, src: str, action_id: str, quality: str, out_dir: str | None,
                  on_frac: Callable[[float], None], cancel: threading.Event | None) -> str:
    p = probe(ffmpeg, src)
    action = ACTIONS_BY_ID[action_id]
    src_ext = ext_of(src)
    ext = action.out_ext or src_ext
    if action_id.startswith("vid_") and action_id not in ("vid_mp3",) and not p.vcodec:
        raise ConvertError("ไฟล์นี้ไม่มีภาพวิดีโอ")
    if action_id.startswith("aud_") and not p.acodec:
        raise ConvertError("ไฟล์นี้ไม่มีเสียง")
    dest = output_path(src, ext, _suffix(action_id), out_dir)
    last_err = ""
    for args in ffmpeg_args(action_id, p, quality, src_ext):
        ok, last_err = _run_ffmpeg(ffmpeg, src, dest, args, p.duration, on_frac, cancel)
        if ok and os.path.exists(dest) and os.path.getsize(dest) > 0:
            return dest
        if os.path.exists(dest):
            os.remove(dest)
    tail = last_err.strip().splitlines()[-1:] or [""]
    raise ConvertError("แปลงไฟล์ไม่สำเร็จ" + (f" ({tail[0][:120]})" if tail[0] else ""))


# --------------------------------------------------------------------------- main entry

def run(action_id: str, files: list[str], quality: str = "balanced",
        out_dir: str | None = None, progress: ProgressCB | None = None,
        cancel: threading.Event | None = None) -> Result:
    action = ACTIONS_BY_ID[action_id]
    res = Result()
    progress = progress or (lambda f, n: None)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    try:
        if action_id == "img_pdf" and len(files) > 1:
            files = sorted(files, key=natural_key)
            folder = out_dir or os.path.dirname(os.path.abspath(files[0]))
            dest = unique_path(os.path.join(folder, f"รวม {len(files)} รูป.pdf"))
            try:
                images_to_pdf(files, dest, quality,
                              progress=lambda i: progress(i / len(files), os.path.basename(files[i - 1])),
                              cancel=cancel)
                res.outputs.append(dest)
            except ConvertError as e:
                res.errors.append((dest, str(e)))
            return res

        ffmpeg = None
        if action.kind in (VIDEO, AUDIO):
            ffmpeg = find_ffmpeg()
            if not ffmpeg:
                res.errors.append(("", "ไม่พบ ffmpeg (ตัวแปลงวิดีโอ) — ลองติดตั้งโปรแกรมใหม่"))
                return res
        n = len(files)
        for i, src in enumerate(files):
            if cancel and cancel.is_set():
                raise _Cancelled()
            name = os.path.basename(src)
            progress(i / n, name)
            try:
                if action.kind == IMAGE:
                    res.outputs.append(convert_image(src, action_id, quality, out_dir))
                else:
                    res.outputs.append(convert_media(
                        ffmpeg, src, action_id, quality, out_dir,
                        lambda fr: progress((i + fr) / n, name), cancel))
            except ConvertError as e:
                res.errors.append((src, str(e)))
            except _Cancelled:
                raise
            except Exception as e:  # never crash the app because of one file
                res.errors.append((src, f"เกิดข้อผิดพลาด: {e}"))
        progress(1.0, "")
    except _Cancelled:
        res.cancelled = True
    return res
