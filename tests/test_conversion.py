"""Conversion après téléchargement (Montage H.264 / Compacte H.265).
Spec : docs/superpowers/specs/2026-11-23-conversion-montage-design.md"""
from __future__ import annotations

import pytest
from PySide6.QtCore import QObject, QProcess, Signal

from app.models.application_settings import ApplicationSettings
from app.models.download_job import DownloadJob, DownloadStatus
from app.parsers.progress_parser import FfmpegProgressReader
from app.services.conversion_service import ConversionService
from app.services.download_service import DownloadRunner


def _job(**overrides) -> DownloadJob:
    base = {
        "url": "https://example.com/v", "title": "t", "mode": "video", "quality": "1080p",
        "output_format": "mp4", "destination": ".", "filename_template": "%(title)s [%(id)s].%(ext)s",
    }
    base.update(overrides)
    return DownloadJob(**base)


# ---- Task 1 : modèle et réglage ----------------------------------------------

def test_job_conversion_roundtrip():
    restored = DownloadJob.from_dict(_job(conversion="edit", encoder="h264_nvenc").to_dict())
    assert (restored.conversion, restored.encoder, restored.phase) == ("edit", "h264_nvenc", "")


def test_legacy_job_has_no_conversion():
    data = _job().to_dict()
    for key in ("conversion", "phase", "encoder"):
        data.pop(key)
    restored = DownloadJob.from_dict(data)
    assert (restored.conversion, restored.phase, restored.encoder) == ("", "", "")


def test_settings_remember_conversion():
    settings = ApplicationSettings()
    assert settings.last_conversion == ""
    settings.last_conversion = "compact"
    assert ApplicationSettings.from_dict(settings.to_dict()).last_conversion == "compact"
    assert ApplicationSettings.from_dict({"theme": "dark"}).last_conversion == ""


# ---- Task 2 : logique pure ----------------------------------------------------

EDIT_ORDER = ["h264_nvenc", "h264_amf", "h264_qsv", "libx264"]
COMPACT_ORDER = ["hevc_nvenc", "hevc_amf", "hevc_qsv", "libx265"]


@pytest.fixture(autouse=True)
def _forget_preferred_encoders():
    ConversionService.preferred.clear()
    yield
    ConversionService.preferred.clear()


def _contains(args: list[str], pair: list[str]) -> bool:
    return any(args[i:i + len(pair)] == pair for i in range(len(args)))


def test_encoder_order_edit_and_compact():
    assert ConversionService.encoder_order("edit") == EDIT_ORDER
    assert ConversionService.encoder_order("compact") == COMPACT_ORDER


def test_encoder_order_puts_preferred_first():
    ConversionService.preferred["edit"] = "libx264"
    assert ConversionService.encoder_order("edit") == ["libx264", "h264_nvenc", "h264_amf", "h264_qsv"]


def test_unknown_preset_raises():
    with pytest.raises(ValueError):
        ConversionService.encoder_order("prores")


def test_ffmpeg_arguments_edit_nvenc(tmp_path):
    source, temp = tmp_path / "v.webm", tmp_path / "v.converting.mp4"
    args = ConversionService.ffmpeg_arguments(source, temp, "h264_nvenc")
    for pair in (["-i", str(source)], ["-map", "0:V:0"], ["-map", "0:a?"], ["-fps_mode", "cfr"],
                 ["-pix_fmt", "yuv420p"], ["-c:a", "aac"], ["-c:v", "h264_nvenc"], ["-progress", "pipe:1"]):
        assert _contains(args, pair), pair
    assert args[-1] == str(temp)
    assert "-tag:v" not in args


@pytest.mark.parametrize("encoder", COMPACT_ORDER)
def test_compact_encoders_tag_hvc1(tmp_path, encoder):
    args = ConversionService.ffmpeg_arguments(tmp_path / "a.mp4", tmp_path / "b.mp4", encoder)
    assert _contains(args, ["-tag:v", "hvc1"])
    assert _contains(args, ["-c:v", encoder])


def test_probe_arguments(tmp_path):
    source = tmp_path / "v.mp4"
    assert ConversionService.probe_arguments(source) == [
        "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(source)]


def test_paths_with_special_characters(tmp_path):
    source = tmp_path / "Ma vidéo, « live » [abc].webm"
    assert ConversionService.target_path(source) == tmp_path / "Ma vidéo, « live » [abc].mp4"
    assert ConversionService.temp_path(source) == tmp_path / "Ma vidéo, « live » [abc].converting.mp4"


def _write(path, size: int):
    path.write_bytes(b"x" * size)
    return path


def test_finalize_edit_replaces_same_name_mp4(tmp_path):
    source = _write(tmp_path / "v.mp4", 100)
    temp = _write(tmp_path / "v.converting.mp4", 300)
    final, note = ConversionService.finalize(source, temp, "edit")
    assert final == source and source.stat().st_size == 300
    assert not temp.exists() and note == ""


def test_finalize_edit_from_webm_removes_original(tmp_path):
    source = _write(tmp_path / "Ma vidéo, live.webm", 100)
    temp = _write(tmp_path / "Ma vidéo, live.converting.mp4", 50)
    final, _ = ConversionService.finalize(source, temp, "edit")
    assert final == tmp_path / "Ma vidéo, live.mp4" and final.is_file()
    assert not source.exists() and not temp.exists()


def test_finalize_compact_keeps_smaller_original(tmp_path):
    source = _write(tmp_path / "v.mkv", 100)
    temp = _write(tmp_path / "v.converting.mp4", 150)
    final, note = ConversionService.finalize(source, temp, "compact")
    assert final == source and source.stat().st_size == 100
    assert not temp.exists() and note


def test_finalize_compact_replaces_when_smaller(tmp_path):
    source = _write(tmp_path / "v.mkv", 100)
    temp = _write(tmp_path / "v.converting.mp4", 40)
    final, note = ConversionService.finalize(source, temp, "compact")
    assert final == tmp_path / "v.mp4" and final.stat().st_size == 40
    assert not source.exists() and note == ""


def _feed(reader, *lines):
    results = [reader.feed(line) for line in lines]
    return [r for r in results if r is not None]


def test_progress_reader_percent_speed_eta():
    reader = FfmpegProgressReader(300)
    [value] = _feed(reader, "frame=12", "out_time_us=75000000", "speed=1.5x", "progress=continue")
    assert value.percent == pytest.approx(25.0)
    assert value.speed == "1.5×" and value.eta == "02:30"
    assert reader.seen_progress


def test_progress_reader_end_is_100():
    reader = FfmpegProgressReader(300)
    [value] = _feed(reader, "out_time_us=299000000", "speed=2x", "progress=end")
    assert value.percent == 100.0


def test_progress_reader_without_duration_stays_at_zero():
    reader = FfmpegProgressReader(0)
    [value] = _feed(reader, "out_time_us=5000000", "speed=1x", "progress=continue")
    assert value.percent == 0.0 and value.eta == ""


def test_progress_reader_ignores_na():
    reader = FfmpegProgressReader(300)
    [value] = _feed(reader, "out_time_us=N/A", "speed=N/A", "progress=continue")
    assert value.percent == 0.0 and value.speed == ""
    assert not reader.seen_progress


# ---- Task 3 : ConversionRunner ------------------------------------------------

class FakeProcess:
    """Remplace QProcess : sorties consommables, aucun vrai processus."""

    def __init__(self, out: bytes = b"", err: bytes = b"") -> None:
        self.out, self.err = out, err
        self.terminated = False

    def readAllStandardOutput(self) -> bytes:  # noqa: N802 (API Qt)
        data, self.out = self.out, b""
        return data

    def readAllStandardError(self) -> bytes:  # noqa: N802 (API Qt)
        data, self.err = self.err, b""
        return data

    def state(self):
        from PySide6.QtCore import QProcess

        return QProcess.ProcessState.Running

    def terminate(self) -> None:
        self.terminated = True

    def kill(self) -> None:
        pass

    def deleteLater(self) -> None:  # noqa: N802 (API Qt)
        pass


class FakeBinaries:
    def locate(self, name: str):
        from pathlib import Path

        return Path(f"{name}.exe")


@pytest.fixture
def conversion(qtbot, tmp_path, monkeypatch):
    """Runner sur un faux fichier source ; `_launch` enregistre les lancements."""
    from app.services.conversion_runner import ConversionRunner

    source = tmp_path / "Ma vidéo, live.webm"
    source.write_bytes(b"x" * 100)
    runner = ConversionRunner(source, "edit", FakeBinaries())
    launches: list[tuple[str, list[str]]] = []

    def fake_launch(program, args, _on_done):
        launches.append((program, args))
        runner.process = FakeProcess()

    monkeypatch.setattr(runner, "_launch", fake_launch)
    events = {"finished": [], "failed": [], "encoder": [], "progress": []}
    runner.finished.connect(lambda path, note: events["finished"].append((path, note)))
    runner.failed.connect(lambda reason, details: events["failed"].append((reason, details)))
    runner.encoder_chosen.connect(events["encoder"].append)
    runner.progress.connect(events["progress"].append)
    return runner, source, launches, events


def _encoder_of(args: list[str]) -> str:
    return args[args.index("-c:v") + 1]


def _probe(runner, stdout: bytes) -> None:
    runner.start()
    runner.process = FakeProcess(out=stdout)
    runner._probe_done(0)


def test_probe_duration_feeds_the_progress_reader(conversion):
    runner, _source, launches, _events = conversion
    _probe(runner, b"300.5\n")
    assert launches[0][0] == "ffprobe.exe"
    program, args = launches[1]
    assert program == "ffmpeg.exe" and _encoder_of(args) == "h264_nvenc"
    assert runner._reader.duration == 300.5


def test_unreadable_probe_still_converts(conversion):
    runner, _source, launches, _events = conversion
    _probe(runner, b"")
    assert launches[-1][0] == "ffmpeg.exe"
    assert runner._reader.duration == 0


def test_gpu_failure_without_progress_falls_back(conversion):
    runner, source, launches, events = conversion
    _probe(runner, b"300\n")
    temp = source.with_name(source.stem + ".converting.mp4")
    temp.write_bytes(b"partial")
    runner._encode_done(1)
    assert _encoder_of(launches[-1][1]) == "h264_amf"
    assert not temp.exists()
    assert events["failed"] == []


def test_failure_after_progress_does_not_fall_back(conversion):
    runner, source, launches, events = conversion
    _probe(runner, b"300\n")
    temp = source.with_name(source.stem + ".converting.mp4")
    temp.write_bytes(b"partial")
    runner.process = FakeProcess(out=b"out_time_us=1000000\nprogress=continue\n", err=b"No space left on device\n")
    runner._encode_done(1)
    assert len(launches) == 2  # probe + un seul encodage
    assert len(events["failed"]) == 1
    assert source.read_bytes() == b"x" * 100 and not temp.exists()


def test_last_encoder_failure_reports_tail(conversion):
    runner, _source, _launches, events = conversion
    from app.services.conversion_service import ConversionService

    ConversionService.preferred["edit"] = "libx264"
    _probe(runner, b"300\n")
    runner._encoders.clear()  # libx264 est le dernier essai
    runner.process = FakeProcess(err=b"No space left on device\n")
    runner._encode_done(1)
    [(reason, details)] = events["failed"]
    assert reason == "Conversion impossible." and "No space left on device" in details


def test_success_remembers_encoder_and_finalizes(conversion):
    runner, source, _launches, events = conversion
    from app.services.conversion_service import ConversionService

    _probe(runner, b"300\n")
    source.with_name(source.stem + ".converting.mp4").write_bytes(b"y" * 50)
    runner._encode_done(0)
    assert ConversionService.preferred["edit"] == "h264_nvenc"
    [(path, _note)] = events["finished"]
    assert path == str(source.with_suffix(".mp4"))


def test_encoder_chosen_emitted_on_each_attempt(conversion):
    runner, _source, _launches, events = conversion
    _probe(runner, b"300\n")
    runner._encode_done(1)
    assert events["encoder"] == ["h264_nvenc", "h264_amf"]


def test_progress_is_relayed(conversion):
    runner, _source, _launches, events = conversion
    _probe(runner, b"200\n")
    runner.process = FakeProcess(out=b"out_time_us=50000000\nspeed=2x\nprogress=continue\n")
    runner._read_stdout()
    assert [round(p.percent) for p in events["progress"]] == [25]


def test_cancel_removes_temp_and_emits_nothing(conversion):
    runner, source, _launches, events = conversion
    _probe(runner, b"300\n")
    temp = source.with_name(source.stem + ".converting.mp4")
    temp.write_bytes(b"partial")
    process = runner.process
    runner.cancel()
    assert process.terminated
    runner._encode_done(1)
    assert not temp.exists() and source.exists()
    assert events["finished"] == [] and events["failed"] == []


# ---- Task 4 : enchaînement dans DownloadRunner -----------------------------------

class FakeConverter(QObject):
    progress = Signal(object)
    encoder_chosen = Signal(str)
    finished = Signal(str, str)
    failed = Signal(str, str)
    output = Signal(str)
    instances: list[FakeConverter] = []

    def __init__(self, source, preset, binaries, parent=None) -> None:
        super().__init__(parent)
        self.source, self.preset = source, preset
        self.started = self.cancelled = False
        FakeConverter.instances.append(self)

    def start(self) -> None:
        self.started = True

    def cancel(self) -> None:
        self.cancelled = True


@pytest.fixture
def chained(qtbot, tmp_path, monkeypatch):
    FakeConverter.instances.clear()
    monkeypatch.setattr("app.services.download_service.ConversionRunner", FakeConverter)
    media = tmp_path / "v.webm"
    media.write_bytes(b"x")

    def make(**overrides):
        job = _job(**{"conversion": "edit", "final_path": str(media), "destination": str(tmp_path), **overrides})
        job.status = DownloadStatus.RUNNING
        runner = DownloadRunner(job, binaries=FakeBinaries())
        events = {"finished": [], "failed": []}
        runner.finished.connect(events["finished"].append)
        runner.failed.connect(lambda _id, message: events["failed"].append(message))
        return runner, job, events

    return make


DONE = QProcess.ExitStatus.NormalExit


def test_download_without_conversion_finishes_as_before(chained):
    runner, job, events = chained(conversion="")
    runner._done(0, DONE)
    assert job.status == DownloadStatus.COMPLETED and len(events["finished"]) == 1
    assert FakeConverter.instances == []


def test_successful_download_starts_conversion(chained):
    runner, job, events = chained()
    job.progress = 100.0
    runner._done(0, DONE)
    [converter] = FakeConverter.instances
    assert converter.started and converter.preset == "edit"
    assert job.phase == "convert" and job.progress == 0.0
    assert job.status == DownloadStatus.RUNNING
    assert events["finished"] == []


def test_audio_job_is_never_converted(chained):
    runner, job, events = chained(mode="audio", output_format="mp3")
    runner._done(0, DONE)
    assert FakeConverter.instances == [] and job.status == DownloadStatus.COMPLETED


def test_missing_file_skips_conversion(chained, tmp_path):
    runner, job, events = chained(final_path=str(tmp_path / "absent.webm"))
    runner._done(0, DONE)
    assert FakeConverter.instances == [] and job.status == DownloadStatus.COMPLETED


def test_conversion_success_completes_with_new_path(chained):
    runner, job, events = chained()
    runner._done(0, DONE)
    FakeConverter.instances[0].finished.emit("x.mp4", "")
    assert job.final_path == "x.mp4" and job.phase == ""
    assert job.status == DownloadStatus.COMPLETED and len(events["finished"]) == 1


def test_conversion_failure_fails_the_job(chained):
    runner, job, events = chained()
    runner._done(0, DONE)
    FakeConverter.instances[0].failed.emit("Conversion impossible.", "No space left on device")
    assert job.status == DownloadStatus.FAILED and job.phase == ""
    assert events["failed"] == ["Conversion impossible."]
    assert "No space left" in job.error_output and job.error_hint


def test_cancel_during_conversion(chained):
    runner, job, events = chained()
    runner._done(0, DONE)
    runner.cancel()
    runner.cancel()  # double clic : un seul événement
    assert FakeConverter.instances[0].cancelled
    assert job.status == DownloadStatus.CANCELLED
    assert events["failed"] == ["Téléchargement annulé."]


def test_cancel_during_probe_does_not_crash(tmp_path):
    from app.services.conversion_runner import ConversionRunner

    source = tmp_path / "v.webm"
    source.write_bytes(b"x")
    runner = ConversionRunner(source, "edit", FakeBinaries())
    runner.cancel()  # aucun processus encore
    runner._probe_done(0)  # la fin de ffprobe arrive après l'annulation
    assert runner.process is None and runner._encoder == ""


def test_encoder_chosen_is_recorded(chained):
    runner, job, _events = chained()
    runner._done(0, DONE)
    FakeConverter.instances[0].encoder_chosen.emit("hevc_amf")
    assert job.encoder == "hevc_amf"


def test_start_resets_phase(chained, monkeypatch):
    runner, job, _events = chained()
    job.phase, job.encoder = "convert", "h264_nvenc"
    monkeypatch.setattr(QProcess, "start", lambda self: None)
    runner.binaries = type("B", (), {"locate": lambda self, name: f"{name}.exe"})()
    runner.start()
    assert (job.phase, job.encoder) == ("", "")
