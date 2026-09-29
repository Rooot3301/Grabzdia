from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QConicalGradient, QFont, QIcon, QPainter, QPen, QPixmap, QWheelEvent
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QComboBox, QFrame, QLabel, QSpinBox, QVBoxLayout, QWidget

from app.models.download_job import DownloadStatus
from app.utils.paths import icon_path

STATUS_LABELS = {
    DownloadStatus.QUEUED: "En attente",
    DownloadStatus.RUNNING: "Téléchargement",
    DownloadStatus.PAUSED: "En pause",
    DownloadStatus.COMPLETED: "Terminé",
    DownloadStatus.FAILED: "Échec",
    DownloadStatus.CANCELLED: "Annulé",
}

MODE_LABELS = {"video": "Vidéo", "audio": "Audio"}


def format_timestamp(value: str) -> str:
    """Horodatage ISO -> « 27/07/2026 09:15 », heure locale.

    L’historique contient des entrées écrites par des versions antérieures :
    une valeur inanalysable est rendue telle quelle plutôt que de lever.
    """
    try:
        return datetime.fromisoformat(value).astimezone().strftime("%d/%m/%Y %H:%M")
    except (TypeError, ValueError):
        return value


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


class NoWheelComboBox(QComboBox):
    """Combo box insensible à la molette.

    Dans une page défilante, faire tourner la molette au-dessus d’un combo
    changeait sa valeur au lieu de faire défiler la page. Ignorer l’événement
    le laisse remonter jusqu’au QScrollArea parent, qui défile normalement.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event: QWheelEvent) -> None:
        event.ignore()


class NoWheelSpinBox(QSpinBox):
    """Spin box insensible à la molette. Voir NoWheelComboBox."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event: QWheelEvent) -> None:
        event.ignore()


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


class CircleGauge(QWidget):
    """Donut chart minimal pour afficher un pourcentage.

    Pas d'échelle logarithmique, pas d'animation, pas de tooltip : c'est
    volontairement une jauge décorative qui accompagne un chiffre déjà
    présent à côté. Deux couleurs pour le gradient (start → end) et une
    couleur de piste, tout traversable via set_colors pour coller au thème.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._value = 0.0
        self._track = QColor("#2A3444")
        self._start = QColor("#7C5CFF")
        self._end = QColor("#39C5FF")
        self.setFixedSize(60, 60)

    def set_value(self, percent: float) -> None:
        clamped = max(0.0, min(100.0, float(percent)))
        if clamped != self._value:
            self._value = clamped
            self.update()

    def set_colors(self, track: str, start: str, end: str) -> None:
        self._track = QColor(track)
        self._start = QColor(start)
        self._end = QColor(end)
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        thickness = 6
        rect = QRectF(thickness / 2, thickness / 2, self.width() - thickness, self.height() - thickness)
        painter.setPen(QPen(self._track, thickness, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
        painter.drawArc(rect, 0, 360 * 16)
        gradient = QConicalGradient(rect.center(), 90.0)
        gradient.setColorAt(0.0, self._start)
        gradient.setColorAt(1.0, self._end)
        painter.setPen(QPen(gradient, thickness, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        # Qt : angles en 1/16 de degré, sens anti-horaire ; on part de midi.
        span = int(-3.6 * self._value * 16)
        painter.drawArc(rect, 90 * 16, span)
        painter.end()


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
