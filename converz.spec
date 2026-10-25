# PyInstaller recipe for Converz.exe (used by the GitHub build).
# Expects ffmpeg at build_ffmpeg/ffmpeg.exe (the workflow downloads it).
import os

ffmpeg = [("build_ffmpeg/ffmpeg.exe", "ffmpeg")] if os.path.exists("build_ffmpeg/ffmpeg.exe") else []
ffmpeg_license = ([("build_ffmpeg/FFMPEG-LICENSE.txt", "ffmpeg")]
                  if os.path.exists("build_ffmpeg/FFMPEG-LICENSE.txt") else [])

a = Analysis(
    ["run.py"],
    pathex=["."],
    binaries=ffmpeg,
    datas=[("assets/converz.ico", "assets"), ("assets/converz.png", "assets"),
           ("LICENSE", ".")] + ffmpeg_license,
    hiddenimports=["pillow_heif"],
    excludes=["tkinter", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuickWidgets",
              "PySide6.QtPdf", "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtDesigner",
              "PySide6.QtUiTools", "PySide6.QtHelp", "pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Converz",
    icon="assets/converz.ico",
    console=False,
    upx=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="Converz", upx=False)
