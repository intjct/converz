import os
import subprocess
import threading

import pytest
from PIL import Image

from converz import converter
from converz.formats import ACTIONS, make_selection, actions_for, IMAGE, VIDEO, AUDIO

FF = converter.find_ffmpeg()


@pytest.fixture(scope="module")
def media(tmp_path_factory):
    d = tmp_path_factory.mktemp("media")
    files = {}
    # images
    Image.new("RGB", (800, 600), (200, 80, 40)).save(d / "photo.jpg")
    im = Image.new("RGBA", (300, 500), (0, 0, 0, 0))
    im.paste((40, 120, 220, 255), (50, 50, 250, 450))
    im.save(d / "logo.png")
    for i in (1, 2, 10):
        Image.new("RGB", (1000 + i * 10, 1400), (i * 20, 100, 150)).save(d / f"page{i}.jpg")
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
        Image.new("RGB", (640, 480), (10, 200, 90)).save(d / "iphone.heic")
        files["heic"] = str(d / "iphone.heic")
    except Exception:
        pass
    files.update(jpg=str(d / "photo.jpg"), png=str(d / "logo.png"),
                 pages=[str(d / f"page{i}.jpg") for i in (10, 2, 1)])
    if FF:
        run = lambda *a: subprocess.run([FF, "-hide_banner", "-loglevel", "error", "-y", *a], check=True)
        run("-f", "lavfi", "-i", "testsrc=size=640x360:rate=25:duration=2",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(d / "clip.mov"))
        run("-f", "lavfi", "-i", "testsrc=size=320x240:rate=25:duration=1",
            "-c:v", "mpeg4", str(d / "silent.avi"))
        run("-f", "lavfi", "-i", "sine=frequency=440:duration=2", str(d / "song.wav"))
        files.update(mov=str(d / "clip.mov"), avi=str(d / "silent.avi"), wav=str(d / "song.wav"))
    return files


def test_selection_and_menu(media):
    sel = make_selection(media["pages"] + [media["png"]])
    assert sel.kind == IMAGE and sel.count == 4
    ids = [a.id for a in actions_for(sel)]
    assert "img_pdf" in ids
    # jpg-only selection hides "JPG"
    assert "img_jpg" not in [a.id for a in actions_for(make_selection(media["pages"]))]
    # most-used floats to the top
    assert actions_for(sel, {"img_ico": 5})[0].id == "img_ico"


@pytest.mark.parametrize("aid", [a.id for a in ACTIONS if a.kind == IMAGE])
def test_image_actions(media, aid, tmp_path):
    for src in (media["jpg"], media["png"]):
        r = converter.run(aid, [src], out_dir=str(tmp_path))
        assert not r.errors, r.errors
        out = r.outputs[0]
        assert os.path.getsize(out) > 0
        if not out.endswith(".pdf"):
            Image.open(out).verify()


def test_heic(media, tmp_path):
    if "heic" not in media:
        pytest.skip("no pillow-heif")
    r = converter.run("img_jpg", [media["heic"]], out_dir=str(tmp_path))
    assert not r.errors and Image.open(r.outputs[0]).size == (640, 480)


def test_never_overwrites(media, tmp_path):
    a = converter.run("img_png", [media["jpg"]], out_dir=str(tmp_path)).outputs[0]
    b = converter.run("img_png", [media["jpg"]], out_dir=str(tmp_path)).outputs[0]
    assert a != b and b.endswith("photo (1).png")


def test_multi_image_pdf(media, tmp_path):
    seen = []
    r = converter.run("img_pdf", media["pages"], out_dir=str(tmp_path),
                      progress=lambda f, n: seen.append(n))
    assert not r.errors, r.errors
    out = r.outputs[0]
    assert os.path.basename(out) == "รวม 3 รูป.pdf"
    # natural order: page1, page2, page10
    assert [s for s in seen if s] == ["page1.jpg", "page2.jpg", "page10.jpg"]
    data = open(out, "rb").read()
    assert data.startswith(b"%PDF") and data.count(b"/Type /Page ") == 3
    try:
        from pypdf import PdfReader
        assert len(PdfReader(out).pages) == 3
    except ImportError:
        pass


needs_ff = pytest.mark.skipif(not FF, reason="no ffmpeg")


@needs_ff
@pytest.mark.parametrize("aid", [a.id for a in ACTIONS if a.kind == VIDEO])
def test_video_actions(media, aid, tmp_path):
    steps = []
    r = converter.run(aid, [media["mov"]], out_dir=str(tmp_path), progress=lambda f, n: steps.append(f))
    assert not r.errors, r.errors
    p = converter.probe(FF, r.outputs[0])
    if aid == "vid_mp3":
        assert p.acodec == "mp3" and p.vcodec is None
    else:
        assert p.vcodec
    if aid == "vid_mute":
        assert p.acodec is None
    assert steps[-1] == 1.0


@needs_ff
def test_mp3_from_silent_video_is_friendly_error(media, tmp_path):
    r = converter.run("vid_mp3", [media["avi"]], out_dir=str(tmp_path))
    assert r.errors and "ไม่มีเสียง" in r.errors[0][1] and not r.outputs


@needs_ff
@pytest.mark.parametrize("aid", [a.id for a in ACTIONS if a.kind == AUDIO])
def test_audio_actions(media, aid, tmp_path):
    r = converter.run(aid, [media["wav"]], out_dir=str(tmp_path))
    assert not r.errors, r.errors
    p = converter.probe(FF, r.outputs[0])
    assert p.acodec and p.duration > 1.5


@needs_ff
def test_cancel(media, tmp_path):
    ev = threading.Event()
    ev.set()
    r = converter.run("vid_mp4", [media["mov"]], out_dir=str(tmp_path), cancel=ev)
    assert r.cancelled and not r.outputs


def test_broken_file(tmp_path):
    bad = tmp_path / "fake.jpg"
    bad.write_text("not an image")
    r = converter.run("img_png", [str(bad)], out_dir=str(tmp_path))
    assert r.errors and not r.outputs


def test_folder_drag_expands(media, tmp_path):
    folder = os.path.dirname(media["pages"][0])
    sel = make_selection([folder])
    assert sel.kind == IMAGE and sel.count >= 3
