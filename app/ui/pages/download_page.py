from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
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
    QVBoxLayout,
    QWidget,
)

from app.models.application_settings import ApplicationSettings
from app.models.download_job import DownloadJob
from app.models.media_info import MediaInfo
from app.services.disk_service import DiskService
from app.ui.batch_dialog import BatchDialog
from app.ui.download_item_widget import DownloadItemWidget
from app.ui.log_panel import LogPanel
from app.ui.widgets import eyebrow_label, page_header
from app.utils.filename import sanitize_filename, validate_output_template
from app.utils.url_validator import validate_media_url

CODEC_MAP = {"Automatique": "auto", "H.264": "h264", "VP9": "vp9", "AV1": "av1"}


class DownloadPage(QWidget):
    analyze_requested = Signal(str, bool)
    job_ready = Signal(object, bool)
    start_queue_requested = Signal()
    error = Signal(str)
    destination_changed = Signal(str)
    cancel_requested = Signal(str)
    retry_requested = Signal(str)
    open_requested = Signal(str)
    options_remembered = Signal()

    def __init__(self, settings: ApplicationSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.media: MediaInfo | None = None
        self.items: dict[str, DownloadItemWidget] = {}
        self._build()
        self._connect()
        self._apply_remembered_options()
        self._update_actions()

    # ---- construction ------------------------------------------------------
    def _build(self) -> None:
        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(36, 30, 36, 30)
        root.setSpacing(16)
        root.addWidget(page_header(
            "Télécharger",
            "Collez un lien, vérifiez les informations, puis choisissez votre format.",
            eyebrow="Nouveau",
        ))

        root.addWidget(self._hero_card())
        root.addWidget(self._media_card())
        root.addWidget(self._options_card())
        root.addWidget(self._destination_card())
        root.addLayout(self._action_row())
        root.addWidget(self._queue_section(), 1)

        self.logs = LogPanel()
        self.logs.setVisible(False)
        self.logs.setFixedHeight(150)
        root.addWidget(self.logs)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _hero_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("heroCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)
        layout.addWidget(eyebrow_label("Lien"))
        row = QHBoxLayout()
        row.setSpacing(10)
        self.url = QLineEdit()
        self.url.setObjectName("heroInput")
        self.url.setPlaceholderText("Collez une URL HTTP ou HTTPS…")
        self.url.setClearButtonEnabled(True)
        self.paste = QPushButton("Coller")
        self.paste.setObjectName("ghostButton")
        self.batch = QPushButton("Lot…")
        self.batch.setObjectName("ghostButton")
        self.batch.setToolTip("Ajouter plusieurs liens à la file")
        self.analyze = QPushButton("Analyser")
        self.analyze.setObjectName("primaryButton")
        row.addWidget(self.url, 1)
        row.addWidget(self.paste)
        row.addWidget(self.batch)
        row.addWidget(self.analyze)
        layout.addLayout(row)
        self.spinner = QLabel("Astuce : glissez-déposez un lien ici.")
        self.spinner.setObjectName("mutedText")
        layout.addWidget(self.spinner)
        return card

    def _media_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        row = QHBoxLayout(card)
        row.setContentsMargins(18, 18, 18, 18)
        row.setSpacing(16)
        self.thumbnail = QLabel("Aperçu")
        self.thumbnail.setObjectName("thumb")
        self.thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail.setFixedSize(200, 112)
        self.thumbnail.setScaledContents(True)
        details = QVBoxLayout()
        details.setSpacing(6)
        self.platform_pill = QLabel("")
        self.platform_pill.setObjectName("platformPill")
        self.platform_pill.setVisible(False)
        pill_row = QHBoxLayout()
        pill_row.addWidget(self.platform_pill)
        pill_row.addStretch()
        self.media_title = QLabel("Aucun média analysé")
        self.media_title.setObjectName("mediaTitle")
        self.media_title.setWordWrap(True)
        self.media_meta = QLabel("Les informations du média apparaîtront ici.")
        self.media_meta.setObjectName("mutedText")
        self.media_meta.setWordWrap(True)
        details.addLayout(pill_row)
        details.addWidget(self.media_title)
        details.addWidget(self.media_meta)
        details.addStretch()
        row.addWidget(self.thumbnail)
        row.addLayout(details, 1)
        return card

    def _options_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        layout.addWidget(eyebrow_label("Sortie"))

        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.mode_video = QPushButton("Vidéo")
        self.mode_audio = QPushButton("Audio uniquement")
        seg = QHBoxLayout()
        seg.setSpacing(8)
        for index, button in enumerate((self.mode_video, self.mode_audio)):
            button.setObjectName("segButton")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.mode_group.addButton(button, index)
            seg.addWidget(button)
        seg.addStretch()
        self.mode_video.setChecked(True)
        layout.addLayout(seg)

        form = QFormLayout()
        form.setSpacing(12)
        self.quality = QComboBox()
        self.quality.addItems(["Automatique", "360p", "480p", "720p", "1080p", "1440p", "2160p", "Meilleure qualité"])
        self.quality.setCurrentText("1080p")
        self.format = QComboBox()
        self.format.addItems(["MP4", "MKV", "WebM"])
        self.codec = QComboBox()
        self.codec.addItems(["Automatique", "H.264", "VP9", "AV1"])
        self.bitrate = QComboBox()
        self.bitrate.addItems(["128 kb/s", "192 kb/s", "256 kb/s", "320 kb/s"])
        self.bitrate.setCurrentText("320 kb/s")
        form.addRow("Qualité", self.quality)
        form.addRow("Format", self.format)
        form.addRow("Codec préféré", self.codec)
        form.addRow("Qualité audio", self.bitrate)
        self._quality_label = form.labelForField(self.quality)
        self._codec_label = form.labelForField(self.codec)
        self._bitrate_label = form.labelForField(self.bitrate)
        layout.addLayout(form)

        checks = QHBoxLayout()
        checks.setSpacing(18)
        self.subtitles = QCheckBox("Sous-titres")
        self.metadata_box = QCheckBox("Métadonnées")
        self.metadata_box.setChecked(True)
        self.thumbnail_box = QCheckBox("Intégrer la miniature")
        self.thumbnail_box.setChecked(True)
        self.playlist = QCheckBox("Playlist entière")
        for widget in (self.subtitles, self.metadata_box, self.thumbnail_box, self.playlist):
            checks.addWidget(widget)
        checks.addStretch()
        layout.addLayout(checks)
        return card

    def _destination_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)
        layout.addWidget(eyebrow_label("Destination"))
        row = QHBoxLayout()
        row.setSpacing(8)
        self.destination = QLineEdit(self.settings.last_download_directory)
        self.browse_button = QPushButton("Parcourir…")
        self.open_button = QPushButton("Ouvrir")
        self.reset_button = QPushButton("Par défaut")
        row.addWidget(self.destination, 1)
        row.addWidget(self.browse_button)
        row.addWidget(self.open_button)
        row.addWidget(self.reset_button)
        layout.addLayout(row)
        return card

    def _action_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch()
        self.queue_button = QPushButton("Ajouter à la file")
        self.download_button = QPushButton("Télécharger maintenant")
        self.download_button.setObjectName("primaryButton")
        row.addWidget(self.queue_button)
        row.addWidget(self.download_button)
        return row

    def _queue_section(self) -> QWidget:
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        head = QHBoxLayout()
        title = QLabel("File de téléchargements")
        title.setObjectName("sectionTitle")
        self.queue_count = QLabel()
        self.queue_count.setObjectName("mutedText")
        self.start_queue_button = QPushButton("Démarrer la file")
        self.start_queue_button.setObjectName("ghostButton")
        head.addWidget(title)
        head.addSpacing(10)
        head.addWidget(self.queue_count)
        head.addStretch()
        head.addWidget(self.start_queue_button)
        layout.addLayout(head)

        self.queue_empty = QLabel("Aucun téléchargement pour le moment. Analysez un lien pour commencer.")
        self.queue_empty.setObjectName("mutedText")
        layout.addWidget(self.queue_empty)

        self.queue_container = QWidget()
        self.queue_layout = QVBoxLayout(self.queue_container)
        self.queue_layout.setContentsMargins(0, 0, 0, 0)
        self.queue_layout.setSpacing(10)
        self.queue_layout.addStretch()
        layout.addWidget(self.queue_container)
        return section

    # ---- wiring ------------------------------------------------------------
    def _connect(self) -> None:
        self.paste.clicked.connect(lambda: self.url.setText(QApplication.clipboard().text().strip()))
        self.batch.clicked.connect(self._open_batch)
        self.analyze.clicked.connect(self._emit_analyze)
        self.url.returnPressed.connect(self._emit_analyze)
        self.url.textChanged.connect(self._update_actions)
        self.mode_group.idToggled.connect(lambda *_: self._mode_changed())
        self.browse_button.clicked.connect(self._browse)
        self.open_button.clicked.connect(lambda: self.open_requested.emit(""))
        self.reset_button.clicked.connect(lambda: self.destination.setText(self.settings.default_download_directory))
        self.queue_button.clicked.connect(lambda: self._enqueue(False))
        self.download_button.clicked.connect(lambda: self._enqueue(True))
        self.start_queue_button.clicked.connect(self.start_queue_requested)

    def _is_audio(self) -> bool:
        return self.mode_audio.isChecked()

    def _emit_analyze(self) -> None:
        self.analyze_requested.emit(self.url.text().strip(), self.playlist.isChecked())

    def _mode_changed(self) -> None:
        audio = self._is_audio()
        for widget, label in (
            (self.quality, self._quality_label),
            (self.codec, self._codec_label),
        ):
            widget.setVisible(not audio)
            if label:
                label.setVisible(not audio)
        self.bitrate.setVisible(audio)
        if self._bitrate_label:
            self._bitrate_label.setVisible(audio)
        self.format.clear()
        self.format.addItems(["MP3", "M4A", "FLAC", "WAV", "Opus"] if audio else ["MP4", "MKV", "WebM"])

    def _browse(self) -> None:
        value = QFileDialog.getExistingDirectory(self, "Choisir le dossier de destination", self.destination.text())
        if value:
            self.destination.setText(value)
            self.destination_changed.emit(value)

    def _build_job(self, url: str, title: str, destination: str) -> DownloadJob:
        audio = self._is_audio()
        quality = self.quality.currentText().replace("Automatique", "auto").replace("Meilleure qualité", "best")
        return DownloadJob(
            url=url,
            title=title,
            mode="audio" if audio else "video",
            quality=quality,
            output_format=self.format.currentText().lower(),
            destination=destination,
            filename_template=self.settings.filename_template,
            video_codec=CODEC_MAP[self.codec.currentText()],
            audio_bitrate=self.bitrate.currentText().split()[0],
            subtitles=self.subtitles.isChecked(),
            embed_metadata=self.metadata_box.isChecked(),
            embed_thumbnail=self.thumbnail_box.isChecked(),
            playlist=self.playlist.isChecked(),
            use_archive=self.settings.use_download_archive,
        )

    def _enqueue(self, start: bool) -> None:
        if not self.media:
            self.error.emit("Analysez d’abord une URL.")
            return
        try:
            validate_output_template(self.settings.filename_template)
            base = DiskService.validate_destination(self.destination.text(), self.media.estimated_size)
            playlist_name = sanitize_filename(self.media.title) if self.media.is_playlist else ""
            media_type = "audio" if self._is_audio() else "video"
            destination = str(DiskService.organized_destination(base, self.settings.organize_mode, media_type, playlist_name))
        except Exception as error:
            self.error.emit(str(error))
            return
        self._remember_options()
        job = self._build_job(self.media.original_url, self.media.title, destination)
        self.job_ready.emit(job, start)

    def _open_batch(self) -> None:
        dialog = BatchDialog(self)
        if dialog.exec():
            self.enqueue_batch(dialog.urls())

    def enqueue_batch(self, urls: list[str]) -> None:
        valid: list[str] = []
        for raw in urls:
            candidate = raw.strip()
            if not candidate:
                continue
            try:
                validate_media_url(candidate)
            except Exception:
                continue
            valid.append(candidate)
        if not valid:
            self.error.emit("Aucune URL valide dans la liste.")
            return
        try:
            validate_output_template(self.settings.filename_template)
            base = DiskService.validate_destination(self.destination.text())
            media_type = "audio" if self._is_audio() else "video"
            destination = str(DiskService.organized_destination(base, self.settings.organize_mode, media_type, ""))
        except Exception as error:
            self.error.emit(str(error))
            return
        self._remember_options()
        for url in valid:
            self.job_ready.emit(self._build_job(url, url, destination), False)
        self.start_queue_requested.emit()

    def load_url(self, url: str) -> None:
        """Fill the URL field and start analysis (used by drag & drop)."""
        self.url.setText(url)
        self._emit_analyze()

    def _apply_remembered_options(self) -> None:
        settings = self.settings
        (self.mode_audio if settings.last_mode == "audio" else self.mode_video).setChecked(True)
        self._mode_changed()
        self.quality.setCurrentText(settings.last_quality)
        self.codec.setCurrentText(settings.last_codec)
        self.bitrate.setCurrentText(settings.last_audio_bitrate)
        self.format.setCurrentText(settings.last_audio_format if settings.last_mode == "audio" else settings.last_video_format)
        self.subtitles.setChecked(settings.last_subtitles)
        self.metadata_box.setChecked(settings.last_embed_metadata)
        self.thumbnail_box.setChecked(settings.last_embed_thumbnail)

    def _remember_options(self) -> None:
        settings = self.settings
        audio = self._is_audio()
        settings.last_mode = "audio" if audio else "video"
        settings.last_quality = self.quality.currentText()
        settings.last_codec = self.codec.currentText()
        settings.last_audio_bitrate = self.bitrate.currentText()
        if audio:
            settings.last_audio_format = self.format.currentText()
        else:
            settings.last_video_format = self.format.currentText()
        settings.last_subtitles = self.subtitles.isChecked()
        settings.last_embed_metadata = self.metadata_box.isChecked()
        settings.last_embed_thumbnail = self.thumbnail_box.isChecked()
        self.options_remembered.emit()

    # ---- public API used by the window ------------------------------------
    def set_busy(self, busy: bool) -> None:
        self.analyze.setEnabled(not busy)
        self.spinner.setText("Analyse en cours…" if busy else "Astuce : glissez-déposez un lien ici.")

    def set_media(self, media: MediaInfo) -> None:
        self.media = media
        duration = f"{int(media.duration or 0) // 60}:{int(media.duration or 0) % 60:02d}"
        best = f"{media.best_height}p" if media.best_height else "inconnue"
        playlist = f" · Playlist ({media.playlist_count} éléments)" if media.is_playlist else ""
        self.media_title.setText(media.title)
        self.media_meta.setText(
            f"{media.author or 'Auteur inconnu'} · {duration} · max. {best}{playlist}"
        )
        if media.platform:
            self.platform_pill.setText(media.platform)
            self.platform_pill.setVisible(True)
        self._update_actions()

    def set_thumbnail(self, pixmap: QPixmap) -> None:
        self.thumbnail.setPixmap(pixmap)

    def update_job(self, job: DownloadJob) -> None:
        item = self.items.get(job.id)
        if not item:
            item = DownloadItemWidget(job)
            item.cancel_requested.connect(self.cancel_requested)
            item.retry_requested.connect(self.retry_requested)
            item.open_requested.connect(self.open_requested)
            self.items[job.id] = item
            self.queue_layout.insertWidget(self.queue_layout.count() - 1, item)
            self.queue_empty.setVisible(False)
        item.update_job(job)

    def set_queue_stats(self, total: int, active: int, queued: int, maximum: int) -> None:
        if total == 0:
            self.queue_count.setText("")
            self.queue_empty.setVisible(True)
        else:
            self.queue_count.setText(f"{total} élément{'s' if total != 1 else ''} · {active} actif{'s' if active != 1 else ''}")
            self.queue_empty.setVisible(False)
        self.start_queue_button.setVisible(queued > 0)
        self.start_queue_button.setEnabled(active < maximum)

    def _update_actions(self, *_args) -> None:
        ready = self.media is not None
        self.queue_button.setEnabled(ready)
        self.download_button.setEnabled(ready)

    def toggle_logs(self) -> None:
        self.logs.setVisible(not self.logs.isVisible())

    def write_log(self, text: str) -> None:
        self.logs.write(text)

    def refresh_settings(self) -> None:
        # Called after settings are saved: no widget rebinding needed beyond
        # the destination default, which is read live from self.settings.
        pass
