from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

from app.models.download_job import DownloadJob, DownloadStatus
from app.services.disk_service import DiskService

STATUS_LABELS = {
    DownloadStatus.QUEUED: "En attente",
    DownloadStatus.RUNNING: "Téléchargement",
    DownloadStatus.PAUSED: "En pause",
    DownloadStatus.COMPLETED: "Terminé",
    DownloadStatus.FAILED: "Échec",
    DownloadStatus.CANCELLED: "Annulé",
}


class DownloadItemWidget(QFrame):
    cancel_requested = Signal(str)
    retry_requested = Signal(str)
    open_requested = Signal(str)
    play_requested = Signal(str)

    def __init__(self, job: DownloadJob, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("downloadCard")
        self.job_id = job.id
        self.title = QLabel()
        self.title.setObjectName("itemTitle")
        self.status = QLabel()
        self.status.setObjectName("statusPill")
        self.details = QLabel()
        self.details.setObjectName("mutedText")
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.cancel = QPushButton("Annuler")
        self.retry = QPushButton("Relancer")
        self.play = QPushButton("Lire")
        self.play.setObjectName("primaryButton")
        self.open = QPushButton("Ouvrir le dossier")

        heading = QHBoxLayout()
        heading.addWidget(self.title, 1)
        heading.addWidget(self.status)
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(self.cancel)
        buttons.addWidget(self.retry)
        buttons.addWidget(self.play)
        buttons.addWidget(self.open)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.addLayout(heading)
        layout.addWidget(self.details)
        layout.addWidget(self.bar)
        layout.addLayout(buttons)
        self.cancel.clicked.connect(lambda: self.cancel_requested.emit(self.job_id))
        self.retry.clicked.connect(lambda: self.retry_requested.emit(self.job_id))
        self.open.clicked.connect(lambda: self.open_requested.emit(self.job_id))
        self.play.clicked.connect(lambda: self.play_requested.emit(self.job_id))
        self.update_job(job)

    def update_job(self, job: DownloadJob) -> None:
        self.title.setText(job.title)
        self.status.setText(STATUS_LABELS[job.status])
        self.status.setProperty("state", job.status.value)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        self.bar.setValue(round(job.progress))
        transfer = " · ".join(value for value in (job.downloaded, job.total, job.speed, f"ETA {job.eta}" if job.eta else "") if value)
        details = f"{job.mode.upper()} · {job.quality} · {job.output_format.upper()}"
        self.details.setText(details + (f"   {transfer}" if transfer else "") + (f" — {job.error}" if job.error else ""))
        self.cancel.setVisible(job.status == DownloadStatus.RUNNING)
        self.retry.setVisible(job.status in {DownloadStatus.FAILED, DownloadStatus.CANCELLED})
        self.open.setVisible(job.status == DownloadStatus.COMPLETED)
        playable = job.status == DownloadStatus.COMPLETED and DiskService.resolve_media_path(job.final_path, job.destination) is not None
        self.play.setVisible(playable)
