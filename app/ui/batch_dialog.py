from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.ui.widgets import eyebrow_label


class BatchDialog(QDialog):
    """Collects several URLs (one per line) to enqueue as a batch."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ajouter plusieurs liens")
        self.setModal(True)
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(10)
        layout.addWidget(eyebrow_label("Lot"))
        title = QLabel("Un lien par ligne")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)
        hint = QLabel(
            "Chaque lien valide sera ajouté à la file avec les options de sortie "
            "actuelles. Les lignes invalides sont ignorées."
        )
        hint.setObjectName("mutedText")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.edit = QPlainTextEdit()
        self.edit.setPlaceholderText("https://…\nhttps://…")
        self.edit.setMinimumHeight(180)
        layout.addWidget(self.edit)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Ajouter à la file")
        buttons.button(QDialogButtonBox.StandardButton.Ok).setObjectName("primaryButton")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Annuler")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def urls(self) -> list[str]:
        return self.edit.toPlainText().splitlines()
