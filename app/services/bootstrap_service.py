"""Download and install the external binaries MediaGrab depends on.

yt-dlp and FFmpeg are fetched on first run (and on demand) from their official
sources into a writable per-user directory, so the installer stays light and
yt-dlp can be refreshed independently of the application.
"""
from __future__ import annotations

import subprocess
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

# Official sources.
YTDLP_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
# gyan.dev builds are the canonical Windows FFmpeg distribution linked from
# ffmpeg.org; the "essentials" archive bundles ffmpeg.exe and ffprobe.exe.
FFMPEG_ZIP_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_CHUNK = 262144


@dataclass(frozen=True)
class Component:
    key: str
    label: str
    provides: tuple[str, ...]


COMPONENTS: dict[str, Component] = {
    "yt-dlp": Component("yt-dlp", "yt-dlp", ("yt-dlp",)),
    "ffmpeg": Component("ffmpeg", "FFmpeg", ("ffmpeg", "ffprobe")),
}


def components_for(missing: list[str]) -> list[Component]:
    """Map missing binary names to the components that must be downloaded.

    ffmpeg and ffprobe ship together in one archive, so needing either pulls
    the single FFmpeg component. Order is stable: yt-dlp first.
    """
    keys: list[str] = []
    if "yt-dlp" in missing:
        keys.append("yt-dlp")
    if "ffmpeg" in missing or "ffprobe" in missing:
        keys.append("ffmpeg")
    return [COMPONENTS[key] for key in keys]


def select_zip_members(names: list[str]) -> dict[str, str]:
    """Pick the ffmpeg.exe / ffprobe.exe entries from an FFmpeg archive.

    Returns a mapping of target filename -> archive member. Missing members are
    simply absent from the result.
    """
    wanted = ("ffmpeg.exe", "ffprobe.exe")
    result: dict[str, str] = {}
    for target in wanted:
        # Prefer an entry under a bin/ directory, else any matching basename.
        candidates = [n for n in names if n.replace("\\", "/").endswith("/bin/" + target)]
        if not candidates:
            candidates = [n for n in names if n.replace("\\", "/").endswith("/" + target) or n == target]
        if candidates:
            result[target] = min(candidates, key=len)
    return result


def extract_ffmpeg(zip_path: Path, dest_dir: Path) -> list[Path]:
    """Extract ffmpeg.exe and ffprobe.exe from an archive into dest_dir."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []
    with zipfile.ZipFile(zip_path) as archive:
        members = select_zip_members(archive.namelist())
        for target, member in members.items():
            destination = dest_dir / target
            with archive.open(member) as source, open(destination, "wb") as out:
                out.write(source.read())
            extracted.append(destination)
    return extracted


def verify_executable(path: Path) -> bool:
    """Return True if the executable runs and reports a version."""
    try:
        completed = subprocess.run(
            [str(path), "--version"],
            capture_output=True,
            timeout=20,
            creationflags=_NO_WINDOW,
        )
        return completed.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def download_file(url: str, target: Path, on_progress=None) -> None:
    """Stream a URL to target atomically, reporting integer percent progress."""
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "MediaGrab"})
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 (https only, fixed hosts)
        total = int(response.headers.get("Content-Length", 0) or 0)
        read = 0
        with open(temporary, "wb") as handle:
            while True:
                chunk = response.read(_CHUNK)
                if not chunk:
                    break
                handle.write(chunk)
                read += len(chunk)
                if on_progress and total:
                    on_progress(min(100, int(read * 100 / total)))
    temporary.replace(target)


@dataclass
class BootstrapResult:
    installed: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures
