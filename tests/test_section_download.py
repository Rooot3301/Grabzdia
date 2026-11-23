"""Téléchargement d'un extrait (plage de temps) : modèle, arguments yt-dlp,
progression FFmpeg. Voir docs/superpowers/specs/2026-11-23-plage-de-temps-design.md."""
from __future__ import annotations

import pytest

from app.models.download_job import DownloadJob
from app.parsers.progress_parser import parse_ffmpeg_progress
from app.services.download_service import DownloadRunner


def _job(**overrides) -> DownloadJob:
    base = {
        "url": "https://example.com/v", "title": "t", "mode": "video", "quality": "1080p",
        "output_format": "mp4", "destination": ".", "filename_template": "%(title)s [%(id)s].%(ext)s",
    }
    base.update(overrides)
    return DownloadJob(**base)


def _section(**overrides) -> DownloadJob:
    return _job(section_start=300, section_end=600, **overrides)


def _value_after(args: list[str], flag: str) -> str:
    return args[args.index(flag) + 1]


# ---- modèle ------------------------------------------------------------------

def test_job_without_range_is_not_a_section():
    assert _job().has_section() is False


def test_job_with_range_is_a_section():
    assert _section().has_section() is True
    assert _section().section_length() == 300


def test_section_survives_the_queue_roundtrip():
    restored = DownloadJob.from_dict(_section().to_dict())
    assert (restored.section_start, restored.section_end) == (300, 600)


def test_legacy_queue_entry_has_no_section():
    data = _job().to_dict()
    data.pop("section_start")
    data.pop("section_end")
    assert DownloadJob.from_dict(data).has_section() is False


# ---- arguments yt-dlp --------------------------------------------------------

def test_full_download_has_no_section_arguments():
    args = DownloadRunner(_job(), binaries=None).arguments()
    for flag in ("--download-sections", "--no-quiet", "--downloader-args"):
        assert flag not in args
    assert _value_after(args, "--output") == "%(title)s [%(id)s].%(ext)s"


def test_section_asks_ytdlp_for_the_time_range():
    args = DownloadRunner(_section(), binaries=None).arguments()
    assert _value_after(args, "--download-sections") == "*00:05:00-00:10:00"


def test_section_gets_its_own_file_name():
    # Sans suffixe, l'extrait écraserait le téléchargement complet (même nom).
    args = DownloadRunner(_section(), binaries=None).arguments()
    assert _value_after(args, "--output") == "%(title)s [%(id)s] [extrait 00h05m00s-00h10m00s].%(ext)s"


def test_section_suffix_leaves_custom_template_without_ext_dot_untouched():
    args = DownloadRunner(_section(filename_template="%(title)s_%(ext)s"), binaries=None).arguments()
    assert _value_after(args, "--output") == "%(title)s_%(ext)s"


def test_section_streams_ffmpeg_stats_without_its_banner():
    args = DownloadRunner(_section(), binaries=None).arguments()
    assert "--no-quiet" in args
    assert _value_after(args, "--downloader-args") == "ffmpeg_i1:-hide_banner -loglevel error -stats"


def test_section_skips_the_download_archive():
    # L'archive noterait l'id : le téléchargement complet serait ensuite ignoré.
    args = DownloadRunner(_section(use_archive=True), binaries=None).arguments()
    assert "--download-archive" not in args


def test_full_download_still_uses_the_archive():
    args = DownloadRunner(_job(use_archive=True), binaries=None).arguments()
    assert "--download-archive" in args


def test_section_disables_sponsorblock():
    # Les segments SponsorBlock sont horodatés sur la vidéo entière.
    args = DownloadRunner(_section(sponsorblock=True), binaries=None).arguments()
    assert "--sponsorblock-remove" not in args


def test_section_works_in_audio_mode():
    args = DownloadRunner(_section(mode="audio", output_format="mp3"), binaries=None).arguments()
    assert "-x" in args
    assert _value_after(args, "--download-sections") == "*00:05:00-00:10:00"


# ---- progression FFmpeg ------------------------------------------------------

FFMPEG_LINE = (
    "frame=  179 fps= 70 q=-1.0 size=     256KiB time=00:01:15.00 "
    "bitrate= 405.5kbits/s speed=1.50x elapsed=0:00:02.54    "
)


def test_ffmpeg_stats_become_a_percentage_of_the_section():
    value = parse_ffmpeg_progress(FFMPEG_LINE, 300)
    assert value is not None
    assert value.percent == pytest.approx(25.0)
    assert value.downloaded == "256KiB"
    assert value.speed == "1.5×"
    # 225 s restantes à 1,5× → 150 s
    assert value.eta == "02:30"


def test_ffmpeg_final_line_uses_lsize_and_caps_at_100():
    line = "frame= 5427 fps= 57 q=-1.0 Lsize=   13066KiB time=00:05:00.40 bitrate= 594.6kbits/s speed=1.88x"
    value = parse_ffmpeg_progress(line, 300)
    assert value is not None
    assert value.percent == 100.0
    assert value.downloaded == "13066KiB"


def test_ffmpeg_hour_long_eta_keeps_hours():
    line = "size=  1KiB time=00:00:00.00 bitrate=N/A speed=1.00x"
    assert parse_ffmpeg_progress(line, 3 * 3600).eta == "3:00:00"


@pytest.mark.parametrize(
    "line",
    [
        "[download] Destination: x.mp4",
        "frame=    0 fps=0.0 q=0.0 size=       0KiB time=N/A bitrate=N/A speed=N/A",
        "",
    ],
)
def test_ffmpeg_parser_ignores_other_lines(line):
    assert parse_ffmpeg_progress(line, 300) is None


def test_ffmpeg_missing_speed_gives_no_eta():
    value = parse_ffmpeg_progress("size= 10KiB time=00:00:30.00 bitrate=N/A speed=N/A", 300)
    assert value is not None and value.percent == pytest.approx(10.0)
    assert value.eta == "" and value.speed == ""


# ---- relai du runner ---------------------------------------------------------

class _FakeProcess:
    def __init__(self, data: bytes) -> None:
        self.data = data

    def readAllStandardOutput(self) -> bytes:  # noqa: N802 (API Qt)
        return self.data


def _read(runner: DownloadRunner, text: str) -> tuple[list, list]:
    progress, output = [], []
    runner.progress.connect(lambda _id, value: progress.append(value))
    runner.output.connect(output.append)
    runner.process = _FakeProcess(text.encode())
    runner._read()
    return progress, output


def test_runner_turns_ffmpeg_stats_into_progress_without_logging_them():
    progress, output = _read(DownloadRunner(_section(), binaries=None), "[info] ok\n" + FFMPEG_LINE + "\r")
    assert [round(p.percent) for p in progress] == [25]
    assert output == ["[info] ok"]


def test_runner_ignores_ffmpeg_stats_for_full_downloads():
    progress, output = _read(DownloadRunner(_job(), binaries=None), FFMPEG_LINE + "\n")
    assert progress == []
    assert len(output) == 1
