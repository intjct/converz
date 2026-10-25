"""`Converz.exe --selftest` — converts a few generated files and reports.

Used by the GitHub build to prove the finished .exe really works on Windows
(ffmpeg found, HEIC support bundled, PDF writer works, Qt starts).
Writes a report to %TEMP%\\converz-selftest.txt and exits 0 on success."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import traceback


def selftest() -> int:
    lines: list[str] = []
    ok = True
    out_file = os.path.join(tempfile.gettempdir(), "converz-selftest.txt")

    def check(name, fn):
        nonlocal ok
        try:
            detail = fn()
            lines.append(f"PASS  {name}  {detail or ''}")
        except Exception as e:
            ok = False
            lines.append(f"FAIL  {name}  {e}\n{traceback.format_exc()}")

    from PIL import Image
    from . import converter, VERSION

    d = tempfile.mkdtemp(prefix="converz-selftest-")
    lines.append(f"Converz {VERSION} selftest in {d}")
    ff = converter.find_ffmpeg()
    lines.append(f"ffmpeg: {ff}")

    Image.new("RGB", (640, 480), (220, 90, 40)).save(os.path.join(d, "a.jpg"))
    Image.new("RGBA", (200, 300), (40, 90, 220, 128)).save(os.path.join(d, "b.png"))
    jpg, png = os.path.join(d, "a.jpg"), os.path.join(d, "b.png")

    def run(aid, files):
        r = converter.run(aid, files)
        if r.errors or not r.outputs:
            raise RuntimeError(r.errors)
        return ", ".join(os.path.basename(o) for o in r.outputs)

    def heic():
        import pillow_heif
        pillow_heif.register_heif_opener()
        h = os.path.join(d, "c.heic")
        Image.new("RGB", (320, 240), (10, 200, 90)).save(h)
        return run("img_jpg", [h])

    check("jpg->png", lambda: run("img_png", [jpg]))
    check("png->ico", lambda: run("img_ico", [png]))
    check("png->webp", lambda: run("img_webp", [png]))
    check("heic->jpg", heic)
    check("2 images->pdf", lambda: run("img_pdf", [jpg, png]))

    def make_media():
        if not ff:
            raise RuntimeError("ffmpeg not found")
        kw = converter._no_window()
        subprocess.run([ff, "-hide_banner", "-loglevel", "error", "-y",
                        "-f", "lavfi", "-i", "testsrc=size=320x240:rate=25:duration=2",
                        "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
                        os.path.join(d, "v.mov")], check=True, **kw)
        return "ok"
    check("make test video", make_media)
    mov = os.path.join(d, "v.mov")
    for aid in ("vid_mp4", "vid_mp3", "vid_gif", "vid_webm", "vid_compress"):
        check(aid, lambda aid=aid: run(aid, [mov]))
    check("aud_wav", lambda: run("aud_wav", [os.path.join(d, "v.mp3")]))

    def qt():
        if not sys.platform.startswith("win") and not os.environ.get("DISPLAY"):
            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        from .settings import Settings
        from .ui.donut import Donut
        from .ui.mainwindow import MainWindow
        app = QApplication.instance() or QApplication([])
        from .ui import theme
        from PySide6.QtGui import QFontInfo
        theme.load_fonts()
        if QFontInfo(theme.font(13)).family() != "Prompt":
            raise RuntimeError("bundled Prompt font not loaded: " + QFontInfo(theme.font(13)).family())
        d1 = Donut()
        d1.show_menu([jpg, png])
        w = MainWindow(Settings())
        n = len(d1.actions)
        d1.hide()
        w.deleteLater()
        return f"donut slices={n}"
    check("Qt windows", qt)

    lines.append("RESULT: " + ("OK" if ok else "FAILED"))
    with open(out_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    if sys.stdout:
        try:
            print("\n".join(lines))
        except Exception:
            pass
    return 0 if ok else 1
