"""Exécute une conversion : ffprobe (durée) puis FFmpeg, avec repli d'encodeur
GPU → processeur. Voir conversion_service pour la logique pure."""
from __future__ import annotations

import contextlib
import logging
from collections import deque
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, Signal

from app.parsers.progress_parser import FfmpegProgressReader
from app.services.binary_service import BinaryService
from app.services.conversion_service import ConversionService

logger = logging.getLogger(__name__)

FAILED_REASON = "Conversion impossible."
TAIL_LINES = 50


class ConversionRunner(QObject):
    progress = Signal(object)  # DownloadProgress
    encoder_chosen = Signal(str)
    finished = Signal(str, str)  # chemin final, note
    failed = Signal(str, str)  # motif, détails (fin de la sortie FFmpeg)
    output = Signal(str)  # lignes d'erreur FFmpeg, pour le panneau de logs

    def __init__(self, source: Path, preset: str, binaries: BinaryService, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.source = source
        self.preset = preset
        self.binaries = binaries
        self.temp = ConversionService.temp_path(source)
        self.process: QProcess | None = None
        self.cancelled = False
        self.tail: deque[str] = deque(maxlen=TAIL_LINES)
        self._encoders: list[str] = []
        self._encoder = ""
        self._duration = 0.0
        self._reader: FfmpegProgressReader | None = None

    # ---- étapes ------------------------------------------------------------
    def start(self) -> None:
        try:
            probe = str(self.binaries.locate("ffprobe"))
        except Exception:  # noqa: BLE001 (sans ffprobe on convertit quand même, sans pourcentage)
            self._start_encoding()
            return
        self._launch(probe, ConversionService.probe_arguments(self.source), self._probe_done)

    def _probe_done(self, _code: int) -> None:
        text = self._take_stdout()
        self._release_process()
        if self.cancelled:
            return
        try:
            self._duration = max(0.0, float(text.strip()))
        except ValueError:
            self._duration = 0.0
        self._start_encoding()

    def _start_encoding(self) -> None:
        self._encoders = ConversionService.encoder_order(self.preset)
        self._next_encoder()

    def _next_encoder(self) -> None:
        self._encoder = self._encoders.pop(0)
        self._reader = FfmpegProgressReader(self._duration)
        self.encoder_chosen.emit(self._encoder)
        try:
            ffmpeg = str(self.binaries.locate("ffmpeg"))
        except Exception as error:  # noqa: BLE001
            self.failed.emit(FAILED_REASON, str(error))
            return
        self._launch(ffmpeg, ConversionService.ffmpeg_arguments(self.source, self.temp, self._encoder), self._encode_done)

    def _encode_done(self, code: int) -> None:
        self._read_stdout()
        self._read_stderr()
        self._release_process()
        if self.cancelled:
            self._remove_temp()
            return
        if code == 0:
            self._finalize()
            return
        self._remove_temp()
        # Un encodeur GPU absent échoue dès l'initialisation, sans progression :
        # on passe au suivant. Après progression, l'échec est réel (disque plein…).
        if self._encoders and not (self._reader and self._reader.seen_progress):
            self.output.emit(f"Encodeur {self._encoder} indisponible, essai du suivant.")
            self._next_encoder()
            return
        self.failed.emit(FAILED_REASON, "\n".join(self.tail))

    def _finalize(self) -> None:
        try:
            final, note = ConversionService.finalize(self.source, self.temp, self.preset)
        except OSError as error:
            self._remove_temp()
            self.failed.emit(FAILED_REASON, str(error))
            return
        # Seul un encodeur GPU est mémorisé : un repli processeur ponctuel (8K
        # refusé par le GPU, pilote capricieux) ne doit pas condamner toutes les
        # conversions suivantes de la session au processeur.
        if not self._encoder.startswith("lib"):
            ConversionService.preferred[self.preset] = self._encoder
        if note:
            self.output.emit(note)
        self.finished.emit(str(final), note)

    def cancel(self) -> None:
        """Annulation utilisateur : le fichier temporaire est jeté de toute façon,
        donc kill() direct (terminate() n'arrête pas ffmpeg sous Windows)."""
        self.cancelled = True
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()

    def abort(self) -> None:
        """Fermeture de l'appli : arrêt synchrone et nettoyage immédiat, car la
        boucle d'événements ne tournera plus pour appeler _encode_done."""
        self.cancelled = True
        if self.process:
            self.process.kill()
            self.process.waitForFinished(2000)
        self._remove_temp()

    def _remove_temp(self) -> None:
        # Un antivirus peut verrouiller le fichier fraîchement fermé : ne jamais
        # laisser l'exception bloquer la tâche en « Conversion ».
        with contextlib.suppress(OSError):
            self.temp.unlink(missing_ok=True)

    # ---- processus -----------------------------------------------------------
    def _launch(self, program: str, args: list[str], on_done: Callable[[int], None]) -> None:
        process = QProcess(self)
        process.setProgram(program)
        process.setArguments(args)
        process.readyReadStandardOutput.connect(self._read_stdout_if_encoding)
        process.readyReadStandardError.connect(self._read_stderr)
        process.finished.connect(lambda code, _status: on_done(code))
        # FailedToStart n'émet pas finished : on le traite comme un échec.
        process.errorOccurred.connect(
            lambda error: on_done(-1) if error == QProcess.ProcessError.FailedToStart else None
        )
        self.process = process
        process.start()

    def _read_stdout_if_encoding(self) -> None:
        # Pendant ffprobe, stdout contient la durée : lue d'un bloc à la fin.
        if self._reader is not None:
            self._read_stdout()

    def _read_stdout(self) -> None:
        if not self.process or self._reader is None:
            return
        for line in self._take_stdout().splitlines():
            value = self._reader.feed(line)
            if value is not None:
                self.progress.emit(value)

    def _read_stderr(self) -> None:
        if not self.process:
            return
        for line in bytes(self.process.readAllStandardError()).decode("utf-8", "replace").splitlines():
            if line.strip():
                self.tail.append(line)
                self.output.emit(line)

    def _take_stdout(self) -> str:
        if not self.process:
            return ""
        return bytes(self.process.readAllStandardOutput()).decode("utf-8", "replace")

    def _release_process(self) -> None:
        if self.process:
            self.process.deleteLater()
            self.process = None
