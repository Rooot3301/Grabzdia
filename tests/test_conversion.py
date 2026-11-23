"""Conversion après téléchargement (Montage H.264 / Compacte H.265).
Spec : docs/superpowers/specs/2026-11-23-conversion-montage-design.md"""
from __future__ import annotations

import pytest

from app.models.application_settings import ApplicationSettings
from app.models.download_job import DownloadJob
from app.parsers.progress_parser import FfmpegProgressReader
from app.services.conversion_service import ConversionService


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
