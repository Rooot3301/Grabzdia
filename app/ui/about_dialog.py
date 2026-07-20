from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.constants import GITHUB_REPO
from app.ui.widgets import eyebrow_label, render_svg
from app.utils.paths import logo_path
from app.version import __version__

_THIRD_PARTY = """
MediaGrab s'appuie sur des composants tiers, téléchargés depuis leurs sources
officielles et soumis à leurs propres licences :

- **yt-dlp** — licence *Unlicense* (domaine public) — https://github.com/yt-dlp/yt-dlp
- **FFmpeg** — licences *LGPL v2.1+ / GPL* selon la build — https://ffmpeg.org/legal.html
- **Qt for Python (PySide6)** — licence *LGPL v3* — https://www.qt.io/licensing

MediaGrab lui-même est distribué sous licence **MIT** (Dev by Root3301).

Utilisez MediaGrab uniquement pour des contenus que vous êtes autorisé à
télécharger. Le logiciel ne contourne ni DRM ni protection d'accès.
"""


class AboutDialog(QDialog):
    """About box with version, license and third-party notices."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("À propos de MediaGrab")
        self.setModal(True)
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(14)
        mark = QLabel()
        mark.setPixmap(render_svg(str(logo_path()), 48))
        mark.setFixedSize(48, 48)
        header.addWidget(mark)
        heading = QVBoxLayout()
        heading.setSpacing(2)
        name = QLabel("MediaGrab")
        name.setObjectName("pageTitle")
        version = QLabel(f"Version {__version__}")
        version.setObjectName("mutedText")
        heading.addWidget(name)
        heading.addWidget(version)
        header.addLayout(heading)
        header.addStretch()
        layout.addLayout(header)

        subtitle = QLabel("Téléchargeur de médias local pour Windows — aucun compte, aucun serveur, aucune télémétrie.")
        subtitle.setObjectName("mutedText")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        layout.addWidget(eyebrow_label("Licences & composants"))
        notices = QTextBrowser()
        notices.setOpenExternalLinks(True)
        notices.setMarkdown(_THIRD_PARTY.strip())
        notices.setMinimumHeight(200)
        layout.addWidget(notices, 1)

        buttons = QHBoxLayout()
        repo_button = QPushButton("Voir sur GitHub")
        repo_button.setObjectName("ghostButton")
        repo_button.clicked.connect(self._open_repo)
        buttons.addWidget(repo_button)
        buttons.addStretch()
        close_button = QPushButton("Fermer")
        close_button.setObjectName("primaryButton")
        close_button.clicked.connect(self.accept)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

    def _open_repo(self) -> None:
        QDesktopServices.openUrl(QUrl(f"https://github.com/{GITHUB_REPO}"))
