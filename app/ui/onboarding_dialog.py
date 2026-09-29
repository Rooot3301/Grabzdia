"""Petit dialogue de première rencontre — ne demande qu'un prénom.

Non-bloquant si l'utilisateur clique « Plus tard » : on mémorise juste
qu'il a vu l'écran (onboarding_completed=True) pour ne plus l'afficher.
Rien de fumeux : aucun envoi, tout reste local dans settings.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from app.ui.widgets import eyebrow_label


class OnboardingDialog(QDialog):
    def __init__(self, current: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Grabzdia — apprenons à nous connaître")
        self.setModal(True)
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(12)

        layout.addWidget(eyebrow_label("Bienvenue"))
        title = QLabel("Comment tu veux qu'on t'appelle ?")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        subtitle = QLabel(
            "Ton prénom sert uniquement à personnaliser la salutation de la "
            "page Accueil. Rien n'est envoyé, tout reste local. Tu peux "
            "modifier ou effacer ce champ à tout moment dans les Paramètres."
        )
        subtitle.setObjectName("mutedText")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        layout.addSpacing(6)
        self.name = QLineEdit(current)
        self.name.setPlaceholderText("Ex. Romain, Alex, Sam…")
        self.name.setMaxLength(40)
        self.name.returnPressed.connect(self.accept)
        layout.addWidget(self.name)

        buttons = QDialogButtonBox(self)
        skip = buttons.addButton("Plus tard", QDialogButtonBox.ButtonRole.RejectRole)
        confirm = buttons.addButton("C'est parti", QDialogButtonBox.ButtonRole.AcceptRole)
        confirm.setObjectName("primaryButton")
        confirm.setDefault(True)
        confirm.setCursor(Qt.CursorShape.PointingHandCursor)
        skip.setCursor(Qt.CursorShape.PointingHandCursor)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def chosen_name(self) -> str:
        return self.name.text().strip()
