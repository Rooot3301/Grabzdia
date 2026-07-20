"""Generate assets/MediaGrab.ico from assets/logo.svg.

Rasterizes the SVG logo to several sizes with PySide6 (no extra dependency)
and packs them into a multi-resolution Windows .ico file (PNG-compressed
entries, supported by Vista and later). Run from the project root:

    python assets/make_icon.py
"""
from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QBuffer, QByteArray, Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication, QImage, QPainter  # noqa: E402
from PySide6.QtSvg import QSvgRenderer  # noqa: E402

SIZES = [16, 24, 32, 48, 64, 128, 256]


def render_png(renderer: QSvgRenderer, size: int) -> bytes:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter)
    painter.end()
    storage = QByteArray()
    buffer = QBuffer(storage)
    buffer.open(QBuffer.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    buffer.close()
    return bytes(storage)


def build_ico(pngs: list[tuple[int, bytes]]) -> bytes:
    header = struct.pack("<HHH", 0, 1, len(pngs))
    entries = bytearray()
    offset = 6 + 16 * len(pngs)
    payload = bytearray()
    for size, data in pngs:
        dimension = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", dimension, dimension, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
        payload += data
    return bytes(header) + bytes(entries) + bytes(payload)


def main() -> int:
    root = Path(__file__).resolve().parent
    svg = root / "logo.svg"
    target = root / "MediaGrab.ico"
    app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    _ = app  # keep the application alive while rendering
    renderer = QSvgRenderer(str(svg))
    if not renderer.isValid():
        print(f"SVG invalide : {svg}", file=sys.stderr)
        return 1
    pngs = [(size, render_png(renderer, size)) for size in SIZES]
    target.write_bytes(build_ico(pngs))
    print(f"Écrit {target} ({target.stat().st_size} octets, {len(SIZES)} tailles)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
