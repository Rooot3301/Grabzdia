from __future__ import annotations

import os
import tempfile
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.services.bootstrap_service import download_file
from app.services.bootstrap_worker import start_worker
from app.ui.widgets import eyebrow_label


class InstallerDownloadWorker(QObject):
    progress = Signal(int)
    finished = Signal(str, str)  # downloaded path, error

    def __init__(self, url: str, target: Path) -> None:
        super().__init__()
        self.url = url
        self.target = target

    def run(self) -> None:
        try:
            download_file(self.url, self.target, self.progress.emit)
            self.finished.emit(str(self.target), "")
        except Exception as error:  # noqa: BLE001
            self.finished.emit("", str(error))


class UpdateDialog(QDialog):
    """Offers to download and run the installer for a newer release."""

    def __init__(self, info: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.info = info
        self._thread = None
        self._worker = None

        self.setWindowTitle("Mise à jour disponible")
        self.setModal(True)
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 22)
        layout.setSpacing(12)
        layout.addWidget(eyebrow_label("Mise à jour"))
        title = QLabel(f"MediaGrab {info.get('version', '')} est disponible")
        title.setObjectName("pageTitle")
        title.setWordWrap(True)
        layout.addWidget(title)

        intro = QLabel(
            "Une nouvelle version est publiée sur GitHub. Découvrez les nouveautés "
            "ci-dessous, puis téléchargez et installez si vous le souhaitez (MediaGrab "
            "se fermera pour laisser l’installateur terminer)."
        )
        intro.setObjectName("mutedText")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        notes = str(info.get("notes", "")).strip()
        if notes:
            layout.addWidget(eyebrow_label("Nouveautés"))
            self.notes = QTextBrowser()
            self.notes.setOpenExternalLinks(True)
            self.notes.setMarkdown(notes)
            self.notes.setMinimumHeight(180)
            layout.addWidget(self.notes, 1)

        self.status = QLabel("")
        self.status.setObjectName("mutedText")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        self.bar.setVisible(False)
        layout.addWidget(self.bar)

        buttons = QHBoxLayout()
        page = QPushButton("Voir sur GitHub")
        page.setObjectName("ghostButton")
        page.clicked.connect(self._open_page)
        buttons.addWidget(page)
        buttons.addStretch()
        self.later_button = QPushButton("Plus tard")
        self.later_button.setObjectName("ghostButton")
        self.later_button.clicked.connect(self.reject)
        buttons.addWidget(self.later_button)
        self.install_button = QPushButton("Télécharger et installer")
        self.install_button.setObjectName("primaryButton")
        self.install_button.clicked.connect(self._install)
        self.install_button.setEnabled(bool(info.get("asset")))
        if not info.get("asset"):
            self.install_button.setToolTip("Aucun installateur attaché à cette version.")
        buttons.addWidget(self.install_button)
        layout.addLayout(buttons)

    def _open_page(self) -> None:
        page = self.info.get("page")
        if page:
            QDesktopServices.openUrl(QUrl(page))

    def _install(self) -> None:
        asset = self.info.get("asset")
        if not asset:
            self._open_page()
            return
        self.install_button.setEnabled(False)
        self.later_button.setEnabled(False)
        self.bar.setVisible(True)
        self.status.setText("Téléchargement de l’installateur…")
        target = Path(tempfile.gettempdir()) / f"MediaGrab-Setup-{self.info.get('version', 'latest')}.exe"
        self._worker = InstallerDownloadWorker(asset, target)
        self._worker.progress.connect(self.bar.setValue)
        self._worker.finished.connect(self._downloaded)
        self._thread = start_worker(self, self._worker)

    def _downloaded(self, path: str, error: str) -> None:
        if error or not path:
            self.status.setText("Échec du téléchargement. Réessayez ou ouvrez la page GitHub.")
            self.install_button.setEnabled(True)
            self.later_button.setEnabled(True)
            return
        self.status.setText("Lancement de l’installateur…")
        if hasattr(os, "startfile"):
            os.startfile(path)  # noqa: S606 (launch the trusted downloaded installer)
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
        self.accept()
        QApplication.quit()

    def closeEvent(self, event) -> None:
        if self._thread is not None and self._thread.isRunning():
            event.ignore()
            return
        event.accept()
