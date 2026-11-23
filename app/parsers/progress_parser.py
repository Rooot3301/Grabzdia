from __future__ import annotations

import re

from app.constants import FINAL_PATH_PREFIX, PROGRESS_PREFIX
from app.models.download_progress import DownloadProgress

_FFMPEG_TIME = re.compile(r"\btime=\s*(\d+):(\d{2}):(\d{2}(?:\.\d+)?)")
_FFMPEG_SPEED = re.compile(r"\bspeed=\s*(\d+(?:\.\d+)?)x")
_FFMPEG_SIZE = re.compile(r"\bL?size=\s*(\S+)")


def parse_progress(line: str) -> DownloadProgress | None:
    line = line.strip()
    if line.startswith(FINAL_PATH_PREFIX):
        return DownloadProgress(percent=100.0, state="finished", final_path=line[len(FINAL_PATH_PREFIX):])
    if not line.startswith(PROGRESS_PREFIX): return None
    fields = line[len(PROGRESS_PREFIX):].split("|")
    if len(fields) < 5: return None
    try: percent = float(fields[0].replace("%", "").strip() or 0)
    except ValueError: percent = 0.0
    return DownloadProgress(percent=max(0.0, min(100.0, percent)), downloaded=fields[1], total=fields[2], speed=fields[3], eta=fields[4])


def parse_ffmpeg_progress(line: str, section_seconds: int) -> DownloadProgress | None:
    """Ligne de stats FFmpeg (« … size= 256KiB time=00:01:15.00 … speed=1.5x ») →
    progression d'un extrait.

    Pour un extrait, yt-dlp délègue le téléchargement à FFmpeg et n'émet sa
    propre ligne de progression qu'à 100 %. Le `time=` de FFmpeg part de 0 au
    début de l'extrait : on le rapporte à la durée de l'extrait.
    """
    match = _FFMPEG_TIME.search(line)
    if not match or section_seconds <= 0:
        return None
    hours, minutes, seconds = match.groups()
    elapsed = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    percent = max(0.0, min(100.0, elapsed / section_seconds * 100))
    size = _FFMPEG_SIZE.search(line)
    speed_match = _FFMPEG_SPEED.search(line)
    speed = float(speed_match.group(1)) if speed_match else 0.0
    eta = ""
    if speed > 0:
        eta = _format_eta(max(0.0, section_seconds - elapsed) / speed)
    return DownloadProgress(
        percent=percent,
        downloaded=size.group(1) if size else "",
        speed=f"{speed:g}×" if speed > 0 else "",
        eta=eta,
    )


def _format_eta(seconds: float) -> str:
    hours, rest = divmod(round(seconds), 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"
