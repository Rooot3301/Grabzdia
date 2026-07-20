from __future__ import annotations

from datetime import UTC, datetime

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

from app.constants import FINAL_PATH_PREFIX, PROGRESS_PREFIX
from app.models.download_job import DownloadJob, DownloadStatus
from app.parsers.progress_parser import parse_progress
from app.services.binary_service import BinaryService
from app.services.format_service import FormatService
from app.utils.filename import validate_output_template
from app.utils.paths import archive_path
from app.utils.url_validator import validate_media_url


class DownloadRunner(QObject):
    progress = Signal(str, object)
    finished = Signal(str)
    failed = Signal(str, str)
    output = Signal(str)

    def __init__(self, job: DownloadJob, binaries: BinaryService, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.job = job
        self.binaries = binaries
        self.process: QProcess | None = None
        self.cancelled = False

    def arguments(self) -> list[str]:
        validate_media_url(self.job.url)
        validate_output_template(self.job.filename_template)
        args = [
            "--newline",
            "--progress",
            "--progress-template",
            f"download:{PROGRESS_PREFIX}%(progress._percent_str)s|%(progress._downloaded_bytes_str)s|%(progress._total_bytes_str)s|%(progress._speed_str)s|%(progress._eta_str)s",
            "--print",
            f"after_move:{FINAL_PATH_PREFIX}%(filepath)s",
            "--paths",
            self.job.destination,
            "--output",
            self.job.filename_template,
            "--continue",
            "--part",
        ]
        if not self.job.playlist:
            args.append("--no-playlist")
        if self.job.use_archive:
            args += ["--download-archive", str(archive_path())]
        if self.job.subtitles:
            args.append("--write-subs")
        if self.job.auto_subtitles:
            args.append("--write-auto-subs")
        if self.job.embed_subtitles and self.job.mode == "video":
            args.append("--embed-subs")
        if self.job.embed_thumbnail:
            args.append("--embed-thumbnail")
        if self.job.embed_metadata:
            args.append("--embed-metadata")
        if self.job.keep_temporary:
            args.append("--keep-video")
        if self.job.mode == "audio":
            args += ["-x", "--audio-format", self.job.output_format, "--audio-quality", f"{self.job.audio_bitrate}K"]
        else:
            args += [
                "-f",
                FormatService().video_selector(self.job.quality, self.job.output_format, self.job.video_codec),
                "--merge-output-format",
                FormatService.merge_format(self.job.output_format),
            ]
        args.append(self.job.url)
        return args

    def start(self) -> None:
        try:
            program = str(self.binaries.locate("yt-dlp"))
            arguments = self.arguments()
        except Exception as error:
            self.failed.emit(self.job.id, str(error))
            return
        self.job.status = DownloadStatus.RUNNING
        self.process = QProcess(self)
        self.process.setProgram(program)
        self.process.setArguments(arguments)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read)
        self.process.finished.connect(self._done)
        self.process.errorOccurred.connect(lambda _: self.failed.emit(self.job.id, "Impossible d’exécuter yt-dlp."))
        self.process.start()

    def _read(self) -> None:
        assert self.process
        for raw in bytes(self.process.readAllStandardOutput()).decode("utf-8", "replace").splitlines():
            parsed = parse_progress(raw)
            if parsed:
                if parsed.final_path:
                    self.job.final_path = parsed.final_path
                self.progress.emit(self.job.id, parsed)
            else:
                self.output.emit(raw)

    def _done(self, code: int, _status: QProcess.ExitStatus) -> None:
        self.job.finished_at = datetime.now(UTC).isoformat()
        if self.cancelled:
            self.job.status = DownloadStatus.CANCELLED
            self.failed.emit(self.job.id, "Téléchargement annulé.")
        elif code == 0:
            self.job.status = DownloadStatus.COMPLETED
            self.finished.emit(self.job.id)
        else:
            self.job.status = DownloadStatus.FAILED
            self.failed.emit(self.job.id, "Le téléchargement a échoué.")
        if self.process:
            self.process.deleteLater()
            self.process = None

    def cancel(self) -> None:
        if not self.process:
            return
        self.cancelled = True
        self.process.terminate()
        QTimer.singleShot(2000, self._kill_if_running)

    def _kill_if_running(self) -> None:
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()


class DownloadManager(QObject):
    job_updated = Signal(object)
    job_finished = Signal(object)

    def __init__(self, binaries: BinaryService, maximum: int = 2, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.binaries = binaries
        self.maximum = maximum
        self.jobs: list[DownloadJob] = []
        self.runners: dict[str, DownloadRunner] = {}

    def enqueue(self, job: DownloadJob, start: bool = True) -> None:
        self.jobs.append(job)
        self.job_updated.emit(job)
        if start:
            self.start_available()

    def start_available(self) -> None:
        while len(self.runners) < self.maximum:
            job = next((j for j in self.jobs if j.status == DownloadStatus.QUEUED), None)
            if not job:
                break
            runner = DownloadRunner(job, self.binaries, self)
            self.runners[job.id] = runner
            runner.progress.connect(self._progress)
            runner.finished.connect(self._complete)
            runner.failed.connect(self._failed)
            runner.start()
            self.job_updated.emit(job)

    def _progress(self, job_id: str, value: object) -> None:
        job = self.find(job_id)
        job.progress = value.percent
        job.speed = value.speed
        job.eta = value.eta
        job.downloaded = value.downloaded
        job.total = value.total
        self.job_updated.emit(job)

    def _complete(self, job_id: str) -> None:
        job = self.find(job_id)
        self.runners.pop(job_id, None)
        self.job_updated.emit(job)
        self.job_finished.emit(job)
        self.start_available()

    def _failed(self, job_id: str, message: str) -> None:
        job = self.find(job_id)
        job.error = message
        self.runners.pop(job_id, None)
        self.job_updated.emit(job)
        self.job_finished.emit(job)
        self.start_available()

    def cancel(self, job_id: str) -> None:
        runner = self.runners.get(job_id)
        if runner:
            runner.cancel()
        else:
            job = self.find(job_id)
            job.status = DownloadStatus.CANCELLED
            self.job_updated.emit(job)

    def retry(self, job_id: str) -> None:
        job = self.find(job_id)
        job.status = DownloadStatus.QUEUED
        job.error = ""
        job.progress = 0
        self.job_updated.emit(job)
        self.start_available()

    def find(self, job_id: str) -> DownloadJob:
        return next(j for j in self.jobs if j.id == job_id)

    def shutdown(self) -> None:
        for runner in list(self.runners.values()):
            runner.cancel()
