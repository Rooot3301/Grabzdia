from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QAction, QDesktopServices, QIcon, QKeySequence, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QWidget,
)

from app.models.download_job import DownloadJob, DownloadStatus
from app.models.media_info import MediaInfo
from app.services.binary_service import BinaryService
from app.services.bootstrap_service import COMPONENTS
from app.services.bootstrap_worker import BootstrapWorker, start_worker
from app.services.disk_service import DiskService
from app.services.download_service import DownloadManager
from app.services.history_service import HistoryService
from app.services.metadata_service import MetadataService
from app.services.notification_service import NotificationService
from app.services.queue_service import QueueService
from app.services.settings_service import SettingsService
from app.services.update_service import UpdateCheckWorker, is_newer
from app.ui.pages import DownloadPage, HistoryPage, SettingsPage
from app.ui.sidebar import Sidebar
from app.ui.update_dialog import UpdateDialog
from app.utils.filename import validate_output_template
from app.utils.paths import app_icon_path, logo_path
from app.version import __version__


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MediaGrab")
        self.resize(1080, 900)
        self.setMinimumSize(900, 680)

        self.settings_service = SettingsService()
        self.settings = self.settings_service.load()
        self.history_service = HistoryService()
        self.queue_service = QueueService()
        self.binaries = BinaryService()
        self.metadata = MetadataService(self.binaries, self)
        self.manager = DownloadManager(self.binaries, self.settings.parallel_downloads, self)
        self.network = QNetworkAccessManager(self)
        self.notifications = NotificationService(self._icon(), self)
        self.notifications.enabled = self.settings.notifications

        self.setAcceptDrops(True)
        self._build_ui()
        self._connect()
        self._shortcuts()
        self._refresh_binary_status()
        self._restore_queue()
        self._update_stats()
        self._maybe_auto_update()
        if self.settings.auto_check_updates:
            self._check_updates(silent=True)

    # ---- construction ------------------------------------------------------
    def _build_ui(self) -> None:
        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sidebar = Sidebar()
        self.stack = QStackedWidget()

        self.download_page = DownloadPage(self.settings)
        self.history_page = HistoryPage(self.history_service)
        self.settings_page = SettingsPage(self.settings)
        for page in (self.download_page, self.history_page, self.settings_page):
            self.stack.addWidget(page)

        layout.addWidget(self.sidebar)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(central)
        self.statusBar().showMessage("Prêt — téléchargez uniquement les contenus que vous êtes autorisé à utiliser.")

    def _connect(self) -> None:
        self.sidebar.navigated.connect(self.stack.setCurrentIndex)

        self.download_page.analyze_requested.connect(self.metadata.analyze)
        self.download_page.job_ready.connect(self._on_job_ready)
        self.download_page.options_remembered.connect(lambda: self.settings_service.save(self.settings))
        self.download_page.start_queue_requested.connect(self.manager.start_available)
        self.download_page.error.connect(self._error)
        self.download_page.destination_changed.connect(self._destination_changed)
        self.download_page.cancel_requested.connect(self.manager.cancel)
        self.download_page.retry_requested.connect(self.manager.retry)
        self.download_page.open_requested.connect(self._open_target)

        self.metadata.succeeded.connect(self._metadata_ready)
        self.metadata.failed.connect(self._error)
        self.metadata.busy_changed.connect(self.download_page.set_busy)

        self.manager.job_updated.connect(self._job_updated)
        self.manager.job_finished.connect(self._job_finished)

        self.settings_page.saved.connect(self._settings_saved)
        self.settings_page.update_ytdlp_requested.connect(self._update_ytdlp)
        self.settings_page.check_updates_requested.connect(lambda: self._check_updates(silent=False))
        self.history_page.redownload_requested.connect(self._redownload)

        self.notifications.activated.connect(self._raise_window)

    def _shortcuts(self) -> None:
        shortcuts = {
            "Ctrl+,": lambda: self._go_to(2),
            "Ctrl+O": self.download_page.browse_button.animateClick,
            "Ctrl+Return": self.download_page.download_button.animateClick,
            "Ctrl+L": self.download_page.toggle_logs,
        }
        for sequence, handler in shortcuts.items():
            action = QAction(self)
            action.setShortcut(QKeySequence(sequence))
            action.triggered.connect(handler)
            self.addAction(action)

    def _go_to(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        self.sidebar.set_current(index)

    # ---- metadata / thumbnail ---------------------------------------------
    def _metadata_ready(self, media: MediaInfo) -> None:
        self.download_page.set_media(media)
        if media.thumbnail_url:
            reply = self.network.get(QNetworkRequest(QUrl(media.thumbnail_url)))
            reply.finished.connect(lambda r=reply: self._thumbnail_ready(r))

    def _thumbnail_ready(self, reply: QNetworkReply) -> None:
        pixmap = QPixmap()
        if pixmap.loadFromData(reply.readAll()):
            self.download_page.set_thumbnail(pixmap)
        reply.deleteLater()

    # ---- queue persistence -------------------------------------------------
    def _restore_queue(self) -> None:
        pending = {DownloadStatus.QUEUED, DownloadStatus.RUNNING, DownloadStatus.PAUSED}
        for data in self.queue_service.load():
            try:
                job = DownloadJob.from_dict(data)
            except Exception:
                continue
            if job.status not in pending:
                continue
            # A previously running/paused job resumes as queued, progress reset.
            job.status = DownloadStatus.QUEUED
            job.progress = 0.0
            job.speed = job.eta = job.downloaded = job.total = ""
            job.error = ""
            self.manager.jobs.append(job)
            self.download_page.update_job(job)

    def _persist_queue(self) -> None:
        pending = {DownloadStatus.QUEUED, DownloadStatus.RUNNING, DownloadStatus.PAUSED}
        self.queue_service.save([job for job in self.manager.jobs if job.status in pending])

    # ---- queue / jobs ------------------------------------------------------
    def _on_job_ready(self, job: DownloadJob, start: bool) -> None:
        self.manager.enqueue(job, start)
        self.settings_service.save(self.settings)
        self._persist_queue()

    def _redownload(self, entry: dict) -> None:
        url = entry.get("url", "")
        if not url:
            self._error("Cette entrée d’historique ne contient pas d’URL.")
            return
        job = DownloadJob(
            url=url,
            title=entry.get("title", url),
            mode=entry.get("mode", "video"),
            quality=entry.get("quality", "auto"),
            output_format=entry.get("output_format", "mp4"),
            destination=entry.get("destination") or self.settings.last_download_directory,
            filename_template=entry.get("filename_template", self.settings.filename_template),
            video_codec=entry.get("video_codec", "auto"),
            audio_bitrate=str(entry.get("audio_bitrate", "320")),
            subtitles=bool(entry.get("subtitles", False)),
            embed_metadata=bool(entry.get("embed_metadata", True)),
            embed_thumbnail=bool(entry.get("embed_thumbnail", True)),
            playlist=bool(entry.get("playlist", False)),
            use_archive=bool(entry.get("use_archive", False)),
        )
        self.manager.enqueue(job, True)
        self._persist_queue()
        self._go_to(0)
        self._update_stats()

    def _job_updated(self, job: DownloadJob) -> None:
        self.download_page.update_job(job)
        self._update_stats()

    def _job_finished(self, job: DownloadJob) -> None:
        self.history_service.add(job.to_dict(), self.settings.history_limit)
        self.history_page.refresh()
        self._persist_queue()
        self.statusBar().showMessage(f"{job.title} : {job.status.value}", 8000)
        if job.status == DownloadStatus.COMPLETED:
            self.notifications.notify("Téléchargement terminé", job.title, success=True)
        elif job.status == DownloadStatus.FAILED:
            self.notifications.notify("Téléchargement échoué", job.title, success=False)

    def _update_stats(self) -> None:
        queued = sum(job.status == DownloadStatus.QUEUED for job in self.manager.jobs)
        active = len(self.manager.runners)
        total = len(self.manager.jobs)
        self.download_page.set_queue_stats(total, active, queued, self.manager.maximum)

    # ---- destinations ------------------------------------------------------
    def _destination_changed(self, value: str) -> None:
        self.settings.last_download_directory = value
        self.settings_service.save(self.settings)

    def _open_target(self, job_id: str) -> None:
        target = self.manager.find(job_id).destination if job_id else self.download_page.destination.text()
        try:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(DiskService.validate_destination(target))))
        except Exception as error:
            self._error(str(error))

    # ---- settings ----------------------------------------------------------
    def _settings_saved(self) -> None:
        try:
            validate_output_template(self.settings.filename_template)
        except ValueError as error:
            self._error(str(error))
            return
        self.settings_service.save(self.settings)
        self.manager.maximum = self.settings.parallel_downloads
        self.notifications.enabled = self.settings.notifications
        self.manager.start_available()
        self.download_page.refresh_settings()
        self._update_stats()
        self.statusBar().showMessage("Paramètres enregistrés.", 4000)

    # ---- misc --------------------------------------------------------------
    def _icon(self) -> QIcon:
        icon = app_icon_path()
        return QIcon(str(icon if icon.exists() else logo_path()))

    def _raise_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _refresh_binary_status(self) -> None:
        missing = self.binaries.missing()
        if missing:
            text = "Composants manquants : " + ", ".join(missing)
            self.sidebar.set_status(text, "missing")
            self.settings_page.set_component_status(text + ". Ils seront téléchargés au démarrage.")
            self.statusBar().showMessage(text + ".")
        else:
            self.sidebar.set_status("Composants prêts", "ok")
            self.settings_page.set_component_status("yt-dlp et FFmpeg sont installés et prêts.")

    def _maybe_auto_update(self) -> None:
        if self.settings.auto_update_ytdlp and "yt-dlp" not in self.binaries.missing():
            self._update_ytdlp()

    def _check_updates(self, silent: bool) -> None:
        if not silent:
            self.settings_page.set_check_enabled(False)
            self.settings_page.set_update_status("Recherche en cours…")
        worker = UpdateCheckWorker()
        worker.finished.connect(lambda info, error: self._on_update_checked(info, error, silent))
        self._update_check_worker = worker
        self._update_check_thread = start_worker(self, worker)

    def _on_update_checked(self, info: object, error: str, silent: bool) -> None:
        self.settings_page.set_check_enabled(True)
        if error or not isinstance(info, dict):
            if not silent:
                self.settings_page.set_update_status("Vérification impossible. Réessayez plus tard.")
            return
        latest = info.get("version", "")
        if latest and is_newer(latest, __version__):
            self.settings_page.set_update_status(f"Nouvelle version disponible : {latest}")
            UpdateDialog(info, self).exec()
        elif not silent:
            self.settings_page.set_update_status(f"MediaGrab est à jour (version {__version__}).")

    def _update_ytdlp(self) -> None:
        self.settings_page.set_update_enabled(False)
        worker = BootstrapWorker([COMPONENTS["yt-dlp"]])
        worker.progress.connect(lambda percent: self.settings_page.set_component_status(f"Téléchargement de yt-dlp… {percent} %"))
        worker.finished.connect(self._ytdlp_updated)
        self._update_worker = worker
        self._update_thread = start_worker(self, worker)

    def _ytdlp_updated(self, success: bool, message: str) -> None:
        self.settings_page.set_update_enabled(True)
        if success:
            self._refresh_binary_status()
            self.statusBar().showMessage("yt-dlp mis à jour.", 4000)
        else:
            self.settings_page.set_component_status(message)
            self._error(message)

    def _error(self, message: str) -> None:
        QMessageBox.warning(self, "MediaGrab", message)
        self.download_page.write_log(message)

    # ---- drag & drop -------------------------------------------------------
    def dragEnterEvent(self, event) -> None:
        data = event.mimeData()
        if data.hasUrls() or data.hasText():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        data = event.mimeData()
        candidates = [url.toString() for url in data.urls()] if data.hasUrls() else data.text().splitlines()
        urls = [candidate.strip() for candidate in candidates if candidate.strip()]
        if not urls:
            return
        self._go_to(0)
        if len(urls) == 1:
            self.download_page.load_url(urls[0])
        else:
            self.download_page.enqueue_batch(urls)
        event.acceptProposedAction()

    def closeEvent(self, event) -> None:
        self.metadata.cancel()
        self.manager.shutdown()
        self.notifications.shutdown()
        self._persist_queue()
        self.settings_service.save(self.settings)
        event.accept()
