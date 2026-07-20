from __future__ import annotations

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, Signal

from app.parsers.metadata_parser import parse_metadata
from app.services.binary_service import BinaryService
from app.utils.url_validator import validate_media_url


def _utf8_environment() -> QProcessEnvironment:
    environment = QProcessEnvironment.systemEnvironment()
    environment.insert("PYTHONIOENCODING", "utf-8")
    environment.insert("PYTHONUTF8", "1")
    return environment


class MetadataService(QObject):
    succeeded = Signal(object)
    failed = Signal(str)
    busy_changed = Signal(bool)

    def __init__(self, binaries: BinaryService, parent: QObject | None = None) -> None:
        super().__init__(parent); self.binaries = binaries; self.process: QProcess | None = None; self.url = ""

    def analyze(self, url: str, playlist: bool = False) -> None:
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning: return
        try: self.url = validate_media_url(url); program = str(self.binaries.locate("yt-dlp"))
        except Exception as error: self.failed.emit(str(error)); return
        args = ["--dump-single-json", "--no-warnings", "--yes-playlist" if playlist else "--no-playlist", self.url]
        self.process = QProcess(self); self.process.setProgram(program); self.process.setArguments(args)
        self.process.setProcessEnvironment(_utf8_environment())
        self.process.finished.connect(self._finished); self.process.errorOccurred.connect(lambda _: self._fail("Impossible d’exécuter yt-dlp."))
        self.busy_changed.emit(True); self.process.start()

    def _finished(self, code: int, _status: QProcess.ExitStatus) -> None:
        assert self.process
        output = bytes(self.process.readAllStandardOutput()).decode("utf-8", "replace")
        error = bytes(self.process.readAllStandardError()).decode("utf-8", "replace")
        self.busy_changed.emit(False)
        if code: self.failed.emit(self._friendly_error(error))
        else:
            try: self.succeeded.emit(parse_metadata(output, self.url))
            except Exception as exc: self.failed.emit(str(exc))
        self.process.deleteLater(); self.process = None

    def _fail(self, message: str) -> None: self.busy_changed.emit(False); self.failed.emit(message)

    @staticmethod
    def _friendly_error(error: str) -> str:
        lower = error.lower()
        if "private" in lower or "login" in lower: return "Ce contenu est privé ou nécessite une authentification."
        if "unsupported url" in lower: return "Cette URL n’est pas prise en charge par yt-dlp."
        if "not available" in lower or "removed" in lower: return "Ce média n’est plus disponible."
        return "L’analyse a échoué. Consultez les logs pour les détails."

    def cancel(self) -> None:
        if self.process: self.process.kill()

