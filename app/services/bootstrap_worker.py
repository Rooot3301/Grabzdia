from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal

from app.services.bootstrap_service import (
    FFMPEG_ZIP_URL,
    YTDLP_URL,
    Component,
    download_file,
    extract_ffmpeg,
    verify_executable,
)
from app.utils.paths import managed_binary_dir


def _friendly(error: Exception) -> str:
    text = str(error).lower()
    if "getaddrinfo" in text or "urlopen" in text or "timed out" in text or "connection" in text:
        return "Échec réseau : vérifiez votre connexion Internet, puis réessayez."
    return f"Échec du téléchargement : {error}"


class BootstrapWorker(QObject):
    """Downloads and installs the requested components off the UI thread."""

    component_started = Signal(str)  # human label of the component in progress
    progress = Signal(int)  # 0..100 for the current component
    finished = Signal(bool, str)  # success, message

    def __init__(self, components: list[Component]) -> None:
        super().__init__()
        self.components = components

    def run(self) -> None:
        dest = managed_binary_dir()
        try:
            dest.mkdir(parents=True, exist_ok=True)
            for component in self.components:
                self.component_started.emit(component.label)
                self.progress.emit(0)
                if component.key == "yt-dlp":
                    self._install_ytdlp(dest)
                elif component.key == "ffmpeg":
                    self._install_ffmpeg(dest)
            self.finished.emit(True, "Composants installés avec succès.")
        except Exception as error:  # noqa: BLE001 (surface any failure to the UI)
            self.finished.emit(False, _friendly(error))

    def _install_ytdlp(self, dest: Path) -> None:
        target = dest / "yt-dlp.exe"
        download_file(YTDLP_URL, target, self.progress.emit)
        if not verify_executable(target):
            raise RuntimeError("yt-dlp a été téléchargé mais ne s’exécute pas.")

    def _install_ffmpeg(self, dest: Path) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "ffmpeg.zip"
            download_file(FFMPEG_ZIP_URL, archive, self.progress.emit)
            self.component_started.emit("FFmpeg (extraction)")
            extracted = extract_ffmpeg(archive, dest)
        names = {path.name for path in extracted}
        if not {"ffmpeg.exe", "ffprobe.exe"} <= names:
            raise RuntimeError("L’archive FFmpeg est incomplète.")


def start_worker(parent: QObject, worker: BootstrapWorker) -> QThread:
    """Move worker to a new QThread and start it. Caller must keep a reference."""
    thread = QThread(parent)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(thread.quit)
    thread.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    thread.start()
    return thread
