from __future__ import annotations

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class ErrorDialog(QDialog):
    """Détail d’un échec de téléchargement.

    Prend quatre chaînes et rien d’autre : la file manipule un DownloadJob,
    l’historique un dictionnaire, et chacune fait son adaptation. C’est ce qui
    permet à la même fenêtre de servir les deux sans qu’elles se connaissent.
    """

    def __init__(
        self,
        title: str,
        reason: str,
        hint: str,
        output: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Détail de l’échec")
        self.setMinimumWidth(560)
        self._title = title
        self._reason = reason
        self._hint = hint
        self._output = output

        self.title = QLabel(title)
        self.title.setObjectName("itemTitle")
        self.title.setWordWrap(True)
        self.reason = QLabel(reason)
        self.reason.setObjectName("sectionTitle")
        self.reason.setWordWrap(True)
        self.hint = QLabel(hint)
        self.hint.setObjectName("mutedText")
        self.hint.setWordWrap(True)
        self.hint.setVisible(bool(hint))

        self.output = QPlainTextEdit(output)
        self.output.setReadOnly(True)
        self.output.setMinimumHeight(180)

        copy_button = QPushButton("Copier")
        copy_button.setObjectName("ghostButton")
        copy_button.clicked.connect(self._copy)
        close_button = QPushButton("Fermer")
        close_button.setObjectName("primaryButton")
        close_button.clicked.connect(self.accept)
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(copy_button)
        buttons.addWidget(close_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)
        layout.addWidget(self.title)
        layout.addWidget(self.reason)
        layout.addWidget(self.hint)
        layout.addWidget(QLabel("Sortie de yt-dlp"))
        layout.addWidget(self.output, 1)
        layout.addLayout(buttons)

    def copy_text(self) -> str:
        """Le texte porté au presse-papier. Exposé pour être testable."""
        parts = [self._title, self._reason]
        if self._hint:
            parts.append(self._hint)
        if self._output:
            parts.append(self._output)
        return "\n\n".join(parts)

    def _copy(self) -> None:
        QApplication.clipboard().setText(self.copy_text())
