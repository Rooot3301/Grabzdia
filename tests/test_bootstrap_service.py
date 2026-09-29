from __future__ import annotations

import io
import zipfile
from pathlib import Path

from app.services import bootstrap_service
from app.services.bootstrap_service import (
    components_for,
    extract_ffmpeg,
    latest_ytdlp_version,
    read_ytdlp_version,
    select_zip_members,
)


def test_components_for_yt_dlp_only():
    components = components_for(["yt-dlp"])
    assert [c.key for c in components] == ["yt-dlp"]


def test_components_for_ffprobe_pulls_ffmpeg_component():
    components = components_for(["ffprobe"])
    assert [c.key for c in components] == ["ffmpeg"]


def test_components_for_all_missing_is_ordered():
    components = components_for(["ffmpeg", "yt-dlp", "ffprobe"])
    assert [c.key for c in components] == ["yt-dlp", "ffmpeg"]


def test_components_for_nothing_missing():
    assert components_for([]) == []


def test_select_zip_members_prefers_bin_directory():
    names = [
        "ffmpeg-6.1-essentials_build/",
        "ffmpeg-6.1-essentials_build/bin/ffmpeg.exe",
        "ffmpeg-6.1-essentials_build/bin/ffprobe.exe",
        "ffmpeg-6.1-essentials_build/doc/ffmpeg.html",
    ]
    members = select_zip_members(names)
    assert members["ffmpeg.exe"].endswith("/bin/ffmpeg.exe")
    assert members["ffprobe.exe"].endswith("/bin/ffprobe.exe")


def test_select_zip_members_missing_entry_is_absent():
    members = select_zip_members(["build/bin/ffmpeg.exe"])
    assert "ffmpeg.exe" in members
    assert "ffprobe.exe" not in members


def test_extract_ffmpeg_writes_both_executables(tmp_path: Path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("build/bin/ffmpeg.exe", b"FFMPEG-BINARY")
        archive.writestr("build/bin/ffprobe.exe", b"FFPROBE-BINARY")
        archive.writestr("build/README.txt", b"docs")
    zip_path = tmp_path / "ffmpeg.zip"
    zip_path.write_bytes(buffer.getvalue())

    dest = tmp_path / "bin"
    extracted = extract_ffmpeg(zip_path, dest)

    names = sorted(p.name for p in extracted)
    assert names == ["ffmpeg.exe", "ffprobe.exe"]
    assert (dest / "ffmpeg.exe").read_bytes() == b"FFMPEG-BINARY"
    assert (dest / "ffprobe.exe").read_bytes() == b"FFPROBE-BINARY"


class _FakeCompleted:
    def __init__(self, code: int, out: bytes = b"") -> None:
        self.returncode = code
        self.stdout = out
        self.stderr = b""


def test_read_ytdlp_version_returns_stripped_stdout(monkeypatch, tmp_path: Path):
    """La sortie de `yt-dlp --version` doit être remontée nettoyée."""
    fake = tmp_path / "yt-dlp.exe"
    fake.write_bytes(b"stub")
    monkeypatch.setattr(
        bootstrap_service.subprocess, "run",
        lambda *args, **kwargs: _FakeCompleted(0, b"2024.11.04\n"),
    )
    assert read_ytdlp_version(fake) == "2024.11.04"


def test_read_ytdlp_version_returns_empty_on_failure(monkeypatch, tmp_path: Path):
    """Échec de subprocess -> '' (le worker doit alors télécharger sans hésiter)."""
    fake = tmp_path / "yt-dlp.exe"
    fake.write_bytes(b"stub")

    def boom(*args, **kwargs):
        raise OSError("permission denied")

    monkeypatch.setattr(bootstrap_service.subprocess, "run", boom)
    assert read_ytdlp_version(fake) == ""


def test_latest_ytdlp_version_reads_tag_name(monkeypatch):
    """Réponse GitHub happy path : on remonte `tag_name`."""
    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return b'{"tag_name": "2024.12.13"}'

    monkeypatch.setattr(
        bootstrap_service.urllib.request, "urlopen",
        lambda request, timeout=10: _Resp(),
    )
    assert latest_ytdlp_version() == "2024.12.13"


def test_latest_ytdlp_version_returns_empty_when_github_fails(monkeypatch):
    """Hors ligne, 5xx, rate limit -> '' pour que le démarrage ne bloque jamais."""
    def boom(*args, **kwargs):
        raise OSError("no network")

    monkeypatch.setattr(bootstrap_service.urllib.request, "urlopen", boom)
    assert latest_ytdlp_version() == ""
