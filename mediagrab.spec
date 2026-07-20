# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

root = Path(SPECPATH)

# yt-dlp, ffmpeg and ffprobe are downloaded on first run into a writable
# per-user directory, so they are intentionally NOT bundled here. Only the
# application and its assets ship in the distribution.
datas = [(str(root / "assets"), "assets")]
icon = root / "assets" / "MediaGrab.ico"

a = Analysis(
    ["app/main.py"],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    # The embedded player is imported lazily; declare the multimedia modules so
    # PyInstaller collects them (the PySide6 hook pulls the backend plugins).
    hiddenimports=["PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets"],
    hookspath=[],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MediaGrab",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(icon) if icon.exists() else None,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=True, name="MediaGrab")
