from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal

from app.services.bootstrap_service import (
    DENO_FALLBACK_URL,
    FFMPEG_ZIP_URL,
    YTDLP_URL,
    Component,
    download_file,
    extract_deno,
    extract_ffmpeg,
    fetch_deno_release_info,
    fetch_deno_sha256,
    fetch_ffmpeg_sha256,
    fetch_ytdlp_sha256,
    latest_ytdlp_version,
    read_deno_version,
    read_ytdlp_version,
    sha256_of_file,
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
                elif component.key == "deno":
                    self._install_deno(dest)
            self.finished.emit(True, "Composants installés avec succès.")
        except Exception as error:  # noqa: BLE001 (surface any failure to the UI)
            self.finished.emit(False, _friendly(error))

    def _install_ytdlp(self, dest: Path) -> None:
        target = dest / "yt-dlp.exe"
        # Skip the ~20 MB download when the local build already matches the
        # latest GitHub tag. Silent probes: if either version lookup fails
        # (offline, GitHub 5xx, rate limit), we fall through to downloading
        # rather than blocking startup.
        if target.is_file():
            local = read_ytdlp_version(target)
            latest = latest_ytdlp_version()
            if local and latest and local == latest:
                self.progress.emit(100)
                return
        download_file(YTDLP_URL, target, self.progress.emit)
        # Integrity check against the official SHA2-256SUMS release asset :
        # si on ne peut pas récupérer la référence (offline, 5xx), on
        # continue plutôt que bloquer — mais si on l'a et qu'elle ne
        # correspond pas, on supprime le fichier et on refuse net (fichier
        # potentiellement corrompu ou man-in-the-middle).
        expected = fetch_ytdlp_sha256()
        if expected:
            actual = sha256_of_file(target)
            if actual != expected:
                target.unlink(missing_ok=True)
                raise RuntimeError(
                    "yt-dlp téléchargé ne correspond pas à l'empreinte officielle "
                    "(fichier corrompu ou interception réseau)."
                )
        if not verify_executable(target):
            raise RuntimeError("yt-dlp a été téléchargé mais ne s’exécute pas.")

    def _install_ffmpeg(self, dest: Path) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "ffmpeg.zip"
            download_file(FFMPEG_ZIP_URL, archive, self.progress.emit)
            expected = fetch_ffmpeg_sha256()
            if expected:
                actual = sha256_of_file(archive)
                if actual != expected:
                    raise RuntimeError(
                        "L'archive FFmpeg téléchargée ne correspond pas à "
                        "l'empreinte publiée par gyan.dev (fichier corrompu "
                        "ou interception réseau)."
                    )
            self.component_started.emit("FFmpeg (extraction)")
            extracted = extract_ffmpeg(archive, dest)
        names = {path.name for path in extracted}
        if not {"ffmpeg.exe", "ffprobe.exe"} <= names:
            raise RuntimeError("L’archive FFmpeg est incomplète.")

    def _install_deno(self, dest: Path) -> None:
        target = dest / "deno.exe"
        download_url, sha_url, tag = fetch_deno_release_info()
        # Skip du download si la version locale correspond déjà au tag
        # dernier publié (same logique que yt-dlp). Le tag commence par
        # 'v', on l'enlève pour comparer à `deno --version`.
        if target.is_file() and tag:
            local = read_deno_version(target)
            if local and tag.lstrip("v") == local:
                self.progress.emit(100)
                return
        # Fallback sur l'URL « latest download » GitHub si l'API ne nous a
        # pas donné d'asset (rate limit, 5xx, format inattendu).
        archive_url = download_url or DENO_FALLBACK_URL
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "deno.zip"
            download_file(archive_url, archive, self.progress.emit)
            # Vérif SHA : si on l'a, on exige la correspondance ; sinon on
            # continue plutôt que bloquer le premier démarrage offline.
            expected = fetch_deno_sha256(sha_url) if sha_url else ""
            if expected:
                actual = sha256_of_file(archive)
                if actual != expected:
                    raise RuntimeError(
                        "L'archive deno téléchargée ne correspond pas à "
                        "l'empreinte publiée par denoland (fichier corrompu "
                        "ou interception réseau)."
                    )
            self.component_started.emit("deno (extraction)")
            extracted = extract_deno(archive, dest)
        if extracted is None:
            raise RuntimeError("L'archive deno ne contient pas deno.exe.")
        if not verify_executable(extracted):
            raise RuntimeError("deno a été téléchargé mais ne s'exécute pas.")


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
