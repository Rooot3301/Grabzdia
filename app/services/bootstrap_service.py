"""Download and install the external binaries Grabzdia depends on.

yt-dlp and FFmpeg are fetched on first run (and on demand) from their official
sources into a writable per-user directory, so the installer stays light and
yt-dlp can be refreshed independently of the application.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

# Official sources.
YTDLP_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
YTDLP_SUMS_URL = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/SHA2-256SUMS"
YTDLP_LATEST_API = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
# gyan.dev builds are the canonical Windows FFmpeg distribution linked from
# ffmpeg.org; the "essentials" archive bundles ffmpeg.exe and ffprobe.exe.
FFMPEG_ZIP_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
FFMPEG_ZIP_SHA256_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip.sha256"

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


def read_ytdlp_version(path: Path) -> str:
    """Return the version string reported by `yt-dlp --version` (e.g. '2024.11.04'), or ''.

    Used to skip re-downloading yt-dlp when the local build is already the
    latest release.
    """
    try:
        completed = subprocess.run(
            [str(path), "--version"],
            capture_output=True,
            timeout=10,
            creationflags=_NO_WINDOW,
        )
        if completed.returncode == 0:
            return completed.stdout.decode("utf-8", "replace").strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return ""


def sha256_of_file(path: Path) -> str:
    """SHA-256 hex digest of a local file, computed in 64 KiB chunks."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_ytdlp_sums(text: str, target: str = "yt-dlp.exe") -> str:
    """Extract the hex digest for `target` from a yt-dlp SHA2-256SUMS file.

    Each line is `<hex> *<name>` (or with two spaces). Returns '' if absent.
    """
    for raw in text.splitlines():
        parts = raw.strip().split()
        if len(parts) >= 2 and parts[-1].lstrip("*").strip() == target:
            return parts[0].lower()
    return ""


def parse_ffmpeg_sha256_sidecar(text: str) -> str:
    """Extract the hex digest from a gyan.dev `.zip.sha256` sidecar.

    Format is `<hex>  <filename>` (two spaces, GNU sha256sum style) or
    just `<hex>` on its own. Returns '' if unparseable.
    """
    stripped = text.strip()
    if not stripped:
        return ""
    return stripped.split()[0].lower()


def fetch_ytdlp_sha256(target: str = "yt-dlp.exe") -> str:
    """Fetch and parse yt-dlp's SHA2-256SUMS release asset, or '' on failure.

    Silent by design : a network hiccup on the sidecar must not turn a
    successful download into an installer failure. The caller decides
    whether to enforce the check or degrade gracefully.
    """
    try:
        request = urllib.request.Request(YTDLP_SUMS_URL, headers={"User-Agent": "Grabzdia"})
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310 (fixed https host)
            text = response.read().decode("utf-8", "replace")
        return parse_ytdlp_sums(text, target)
    except Exception:  # noqa: BLE001
        return ""


def fetch_ffmpeg_sha256() -> str:
    """Fetch and parse gyan.dev's `.zip.sha256` sidecar, or '' on failure."""
    try:
        request = urllib.request.Request(FFMPEG_ZIP_SHA256_URL, headers={"User-Agent": "Grabzdia"})
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310 (fixed https host)
            text = response.read().decode("utf-8", "replace")
        return parse_ffmpeg_sha256_sidecar(text)
    except Exception:  # noqa: BLE001
        return ""


def latest_ytdlp_version() -> str:
    """Return the `tag_name` of yt-dlp's latest GitHub release, or '' on failure.

    Failures are silent by design: this is a "should I download?" probe, and
    when it can't answer we must not block the app — the caller falls back to
    the existing binary. Runs off the UI thread inside BootstrapWorker.
    """
    try:
        request = urllib.request.Request(
            YTDLP_LATEST_API,
            headers={"User-Agent": "Grabzdia", "Accept": "application/vnd.github+json"},
        )
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310 (fixed https host)
            data = json.load(response)
        return str(data.get("tag_name", "")).strip()
    except Exception:  # noqa: BLE001 (any failure ⇒ skip the update, never crash startup)
        return ""


def download_file(url: str, target: Path, on_progress=None) -> None:
    """Stream a URL to target atomically, reporting integer percent progress."""
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "Grabzdia"})
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
