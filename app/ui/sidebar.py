from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.widgets import load_icon, render_svg
from app.utils.paths import logo_path
from app.version import __version__


class Sidebar(QWidget):
    """Vertical navigation rail with a brand mark, page buttons and a footer."""

    navigated = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(224)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 22, 16, 18)
        layout.setSpacing(6)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(10)
        mark = QLabel()
        mark.setPixmap(render_svg(str(logo_path()), 30))
        mark.setFixedSize(30, 30)
        brand_text = QWidget()
        brand_text_layout = QVBoxLayout(brand_text)
        brand_text_layout.setContentsMargins(0, 0, 0, 0)
        brand_text_layout.setSpacing(0)
        name = QLabel("MediaGrab")
        name.setObjectName("sidebarBrand")
        tagline = QLabel("Téléchargeur local")
        tagline.setObjectName("sidebarTagline")
        brand_text_layout.addWidget(name)
        brand_text_layout.addWidget(tagline)
        brand_row.addWidget(mark)
        brand_row.addWidget(brand_text, 1)
        layout.addLayout(brand_row)
        layout.addSpacing(18)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: list[QPushButton] = []
        entries = [
            ("Télécharger", "download.svg"),
            ("Historique", "history.svg"),
            ("Paramètres", "settings.svg"),
        ]
        for index, (label, icon_name) in enumerate(entries):
            button = QPushButton(f"  {label}")
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setIcon(load_icon(icon_name))
            button.setIconSize(QSize(19, 19))
            button.clicked.connect(lambda _checked=False, i=index: self.navigated.emit(i))
            self._group.addButton(button, index)
            self._buttons.append(button)
            layout.addWidget(button)

        layout.addStretch(1)

        self.status = QLabel("Composants : vérification…")
        self.status.setObjectName("sidebarStatus")
        self.status.setWordWrap(True)
        version = QLabel(f"Version {__version__}")
        version.setObjectName("sidebarVersion")
        layout.addWidget(self.status)
        layout.addSpacing(2)
        layout.addWidget(version)

        self._buttons[0].setChecked(True)

    def set_current(self, index: int) -> None:
        if 0 <= index < len(self._buttons):
            self._buttons[index].setChecked(True)

    def set_status(self, text: str, state: str) -> None:
        """state is one of 'ok', 'missing', ''."""
        self.status.setText(text)
        self.status.setProperty("state", state)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
