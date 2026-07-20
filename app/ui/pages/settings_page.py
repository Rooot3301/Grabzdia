from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.models.application_settings import ApplicationSettings
from app.ui.widgets import eyebrow_label, page_header
from app.utils.filename import validate_output_template
from app.version import __version__


class SettingsPage(QWidget):
    saved = Signal()
    update_ytdlp_requested = Signal()
    check_updates_requested = Signal()
    report_requested = Signal()

    def __init__(self, settings: ApplicationSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = settings

        header = page_header(
            "Paramètres",
            "Personnalisez le comportement de MediaGrab. Tout est enregistré localement.",
            eyebrow="Préférences",
        )

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)
        content_layout.addWidget(self._general_card())
        content_layout.addWidget(self._downloads_card())
        content_layout.addWidget(self._components_card())
        content_layout.addWidget(self._notifications_card())
        content_layout.addWidget(self._application_card())
        content_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(content)

        self.feedback = QLabel("")
        self.feedback.setObjectName("successText")
        save = QPushButton("Enregistrer les paramètres")
        save.setObjectName("primaryButton")
        save.clicked.connect(self.apply)
        actions = QHBoxLayout()
        actions.addWidget(self.feedback)
        actions.addStretch()
        actions.addWidget(save)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 30, 36, 24)
        layout.setSpacing(16)
        layout.addWidget(header)
        layout.addWidget(scroll, 1)
        layout.addLayout(actions)

    # ---- cards -------------------------------------------------------------
    def _general_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.addWidget(self._section("Général", "Destination et organisation des fichiers"))
        form = QFormLayout()
        form.setSpacing(12)
        self.folder = QLineEdit(self.settings.default_download_directory)
        browse = QPushButton("Parcourir…")
        browse.clicked.connect(self._browse)
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.folder, 1)
        folder_row.addWidget(browse)
        form.addRow("Dossier par défaut", folder_row)
        self.organize = QComboBox()
        self.organize.addItem("Tout dans le dossier choisi", "all")
        self.organize.addItem("Séparer Audio et Vidéos", "separate")
        self.organize.addItem("Créer un dossier par playlist", "playlist")
        self.organize.setCurrentIndex(max(0, self.organize.findData(self.settings.organize_mode)))
        form.addRow("Organisation", self.organize)
        self.theme = QComboBox()
        self.theme.addItem("Sombre", "dark")
        self.theme.addItem("Clair", "light")
        self.theme.addItem("Système", "system")
        self.theme.setCurrentIndex(max(0, self.theme.findData(self.settings.theme)))
        form.addRow("Thème", self.theme)
        layout.addLayout(form)
        return card

    def _downloads_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.addWidget(self._section("Téléchargements", "File d’attente, noms de fichiers et historique"))
        form = QFormLayout()
        form.setSpacing(12)
        self.parallel = QSpinBox()
        self.parallel.setRange(1, 4)
        self.parallel.setValue(self.settings.parallel_downloads)
        form.addRow("Téléchargements simultanés", self.parallel)
        self.template = QLineEdit(self.settings.filename_template)
        self.template.setPlaceholderText("%(title)s [%(id)s].%(ext)s")
        form.addRow("Modèle de nom", self.template)
        self.history_limit = QSpinBox()
        self.history_limit.setRange(10, 5000)
        self.history_limit.setSingleStep(50)
        self.history_limit.setValue(self.settings.history_limit)
        form.addRow("Éléments dans l’historique", self.history_limit)
        self.archive = QCheckBox("Éviter de télécharger deux fois le même média")
        self.archive.setChecked(self.settings.use_download_archive)
        form.addRow("Archive anti-doublons", self.archive)
        layout.addLayout(form)
        return card

    def _components_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.addWidget(self._section("Composants", "yt-dlp et FFmpeg, téléchargés localement"))
        self.component_status = QLabel("Vérification…")
        self.component_status.setObjectName("mutedText")
        self.component_status.setWordWrap(True)
        row = QHBoxLayout()
        row.addWidget(self.component_status, 1)
        self.update_button = QPushButton("Mettre à jour yt-dlp")
        self.update_button.setObjectName("ghostButton")
        self.update_button.clicked.connect(self.update_ytdlp_requested)
        row.addWidget(self.update_button)
        layout.addLayout(row)
        self.auto_update = QCheckBox("Mettre à jour yt-dlp automatiquement au démarrage")
        self.auto_update.setChecked(self.settings.auto_update_ytdlp)
        layout.addWidget(self.auto_update)
        return card

    def _notifications_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.addWidget(self._section("Notifications", "Alertes de fin de téléchargement"))
        self.notifications = QCheckBox("M’avertir quand un téléchargement se termine")
        self.notifications.setChecked(self.settings.notifications)
        layout.addWidget(self.notifications)
        return card

    def _application_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.addWidget(self._section("Application", f"MediaGrab {__version__}"))
        row = QHBoxLayout()
        self.update_status = QLabel("")
        self.update_status.setObjectName("mutedText")
        self.update_status.setWordWrap(True)
        row.addWidget(self.update_status, 1)
        self.check_updates_button = QPushButton("Rechercher des mises à jour")
        self.check_updates_button.setObjectName("ghostButton")
        self.check_updates_button.clicked.connect(self.check_updates_requested)
        row.addWidget(self.check_updates_button)
        layout.addLayout(row)
        self.auto_check = QCheckBox("Vérifier les mises à jour au démarrage")
        self.auto_check.setChecked(self.settings.auto_check_updates)
        layout.addWidget(self.auto_check)

        report_row = QHBoxLayout()
        report_hint = QLabel("Un souci ? Générez un rapport (logs anonymisés) et ouvrez un ticket.")
        report_hint.setObjectName("mutedText")
        report_hint.setWordWrap(True)
        report_button = QPushButton("Signaler un problème")
        report_button.setObjectName("ghostButton")
        report_button.clicked.connect(self.report_requested)
        report_row.addWidget(report_hint, 1)
        report_row.addWidget(report_button)
        layout.addLayout(report_row)
        return card

    @staticmethod
    def _section(title: str, subtitle: str) -> QWidget:
        widget = QWidget()
        widget.setObjectName("plainContainer")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(2)
        layout.addWidget(eyebrow_label(title))
        heading = QLabel(subtitle)
        heading.setObjectName("mutedText")
        layout.addWidget(heading)
        return widget

    # ---- behaviour ---------------------------------------------------------
    def set_component_status(self, text: str) -> None:
        self.component_status.setText(text)

    def set_update_enabled(self, enabled: bool) -> None:
        self.update_button.setEnabled(enabled)
        self.update_button.setText("Mise à jour…" if not enabled else "Mettre à jour yt-dlp")

    def set_update_status(self, text: str) -> None:
        self.update_status.setText(text)

    def set_check_enabled(self, enabled: bool) -> None:
        self.check_updates_button.setEnabled(enabled)
        self.check_updates_button.setText("Recherche…" if not enabled else "Rechercher des mises à jour")

    def _browse(self) -> None:
        value = QFileDialog.getExistingDirectory(self, "Dossier par défaut", self.folder.text())
        if value:
            self.folder.setText(value)

    def apply(self) -> None:
        try:
            template = validate_output_template(self.template.text().strip())
        except ValueError as error:
            self.feedback.setStyleSheet("color: #FF9BA6;")
            self.feedback.setText(str(error))
            return
        self.settings.default_download_directory = self.folder.text().strip()
        self.settings.parallel_downloads = self.parallel.value()
        self.settings.organize_mode = self.organize.currentData()
        self.settings.theme = self.theme.currentData()
        self.settings.filename_template = template
        self.settings.history_limit = self.history_limit.value()
        self.settings.use_download_archive = self.archive.isChecked()
        self.settings.notifications = self.notifications.isChecked()
        self.settings.auto_update_ytdlp = self.auto_update.isChecked()
        self.settings.auto_check_updates = self.auto_check.isChecked()
        self.feedback.setStyleSheet("")
        self.feedback.setText("Paramètres enregistrés")
        self.saved.emit()
