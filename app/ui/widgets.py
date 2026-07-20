from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from app.utils.paths import icon_path


def load_icon(name: str) -> QIcon:
    """Load an SVG icon from assets/icons by file name."""
    return QIcon(str(icon_path(name)))


def render_svg(path: str, size: int) -> QPixmap:
    """Rasterize an SVG file to a transparent square pixmap of the given size."""
    renderer = QSvgRenderer(path)
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter)
    painter.end()
    return pixmap


def eyebrow_label(text: str) -> QLabel:
    """Small uppercase, letter-spaced label used to head sections."""
    label = QLabel(text.upper())
    label.setObjectName("eyebrow")
    font = label.font()
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.4)
    label.setFont(font)
    return label


def card(*, object_name: str = "card") -> QFrame:
    """A rounded surface container."""
    frame = QFrame()
    frame.setObjectName(object_name)
    return frame


def page_header(title: str, subtitle: str, eyebrow: str = "") -> QWidget:
    """Standard page heading: optional eyebrow, title, subtitle."""
    container = QWidget()
    container.setObjectName("plainContainer")
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    if eyebrow:
        layout.addWidget(eyebrow_label(eyebrow))
    title_label = QLabel(title)
    title_label.setObjectName("pageTitle")
    layout.addWidget(title_label)
    subtitle_label = QLabel(subtitle)
    subtitle_label.setObjectName("pageSubtitle")
    subtitle_label.setWordWrap(True)
    layout.addWidget(subtitle_label)
    return container
