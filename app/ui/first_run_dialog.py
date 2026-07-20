from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.services.bootstrap_service import Component
from app.services.bootstrap_worker import BootstrapWorker, start_worker
from app.ui.widgets import eyebrow_label


class FirstRunDialog(QDialog):
    """Guides the one-time download of yt-dlp and FFmpeg on first launch."""

    def __init__(self, components: list[Component], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.components = components
        self._thread = None
        self._worker = None

        self.setWindowTitle("Installation des composants")
        self.setModal(True)
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 22)
        layout.setSpacing(12)

        layout.addWidget(eyebrow_label("Première utilisation"))
        title = QLabel("Installer les composants de MediaGrab")
        title.setObjectName("pageTitle")
        title.setWordWrap(True)
        layout.addWidget(title)

        names = ", ".join(component.label for component in components)
        intro = QLabel(
            f"MediaGrab a besoin de {names} pour analyser et télécharger des médias. "
            "Ils seront récupérés depuis leurs sources officielles (~40 à 90 Mo) et "
            "installés dans votre dossier utilisateur. Une connexion Internet est requise."
        )
        intro.setObjectName("mutedText")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.status = QLabel("Prêt à installer.")
        self.status.setObjectName("mutedText")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        layout.addWidget(self.bar)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.later_button = QPushButton("Plus tard")
        self.later_button.setObjectName("ghostButton")
        self.later_button.clicked.connect(self.reject)
        self.install_button = QPushButton("Installer maintenant")
        self.install_button.setObjectName("primaryButton")
        self.install_button.clicked.connect(self._start)
        buttons.addWidget(self.later_button)
        buttons.addWidget(self.install_button)
        layout.addLayout(buttons)

    def _start(self) -> None:
        self.install_button.setEnabled(False)
        self.later_button.setEnabled(False)
        self.status.setText("Préparation…")
        self._worker = BootstrapWorker(self.components)
        self._worker.component_started.connect(self._on_component)
        self._worker.progress.connect(self.bar.setValue)
        self._worker.finished.connect(self._on_finished)
        self._thread = start_worker(self, self._worker)

    def _on_component(self, label: str) -> None:
        self.status.setText(f"Téléchargement de {label}…")

    def _on_finished(self, success: bool, message: str) -> None:
        self.status.setText(message)
        if success:
            self.bar.setValue(100)
            self.install_button.setText("Terminer")
            self.install_button.setEnabled(True)
            self.install_button.clicked.disconnect()
            self.install_button.clicked.connect(self.accept)
        else:
            self.install_button.setText("Réessayer")
            self.install_button.setEnabled(True)
            self.later_button.setEnabled(True)

    def closeEvent(self, event) -> None:
        if self._thread is not None and self._thread.isRunning():
            event.ignore()
            return
        event.accept()
