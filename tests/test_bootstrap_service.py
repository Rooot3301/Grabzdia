from __future__ import annotations

import io
import zipfile
from pathlib import Path

from app.services import bootstrap_service
from app.services.bootstrap_service import (
    components_for,
    extract_deno,
    extract_ffmpeg,
    fetch_deno_release_info,
    latest_ytdlp_version,
    parse_ffmpeg_sha256_sidecar,
    parse_ytdlp_sums,
    read_deno_version,
    read_ytdlp_version,
    select_zip_members,
    sha256_of_file,
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


def test_sha256_of_file_matches_known_digest(tmp_path: Path):
    """L'empreinte SHA-256 doit être calculée en chunks sans erreur sur un
    fichier > 64 KiB (limite d'un chunk)."""
    import hashlib

    fixture = tmp_path / "blob.bin"
    payload = b"grabzdia" * 20000  # ~160 KiB, force plusieurs chunks
    fixture.write_bytes(payload)
    expected = hashlib.sha256(payload).hexdigest()

    assert sha256_of_file(fixture) == expected


def test_parse_ytdlp_sums_finds_the_windows_binary():
    """Le fichier SHA2-256SUMS de yt-dlp liste plusieurs cibles ; on doit
    prendre la ligne yt-dlp.exe et pas une autre variante."""
    sums = (
        "1234567890abcdef *yt-dlp\n"
        "abcdef1234567890 *yt-dlp.exe\n"
        "deadbeefcafebabe *yt-dlp_macos\n"
    )
    assert parse_ytdlp_sums(sums, "yt-dlp.exe") == "abcdef1234567890"


def test_parse_ytdlp_sums_returns_empty_when_target_absent():
    assert parse_ytdlp_sums("abc *yt-dlp\n", "yt-dlp.exe") == ""


def test_parse_ffmpeg_sha256_sidecar_extracts_hex():
    assert parse_ffmpeg_sha256_sidecar("deadbeef  ffmpeg-release-essentials.zip\n") == "deadbeef"
    # Certaines sources publient juste l'empreinte sans nom de fichier.
    assert parse_ffmpeg_sha256_sidecar("cafebabe\n") == "cafebabe"


def test_parse_ffmpeg_sha256_sidecar_empty_is_safe():
    assert parse_ffmpeg_sha256_sidecar("") == ""
    assert parse_ffmpeg_sha256_sidecar("   \n") == ""


# ---- deno (nouveau composant) --------------------------------------------

def test_read_deno_version_parses_first_line(monkeypatch, tmp_path: Path):
    """`deno --version` renvoie trois lignes, on ne garde que la version."""
    fake = tmp_path / "deno.exe"
    fake.write_bytes(b"stub")
    monkeypatch.setattr(
        bootstrap_service.subprocess, "run",
        lambda *args, **kwargs: _FakeCompleted(0, b"deno 1.46.0 (release, x86_64-pc-windows-msvc)\ntypescript 5.5.4\nv8 12.9\n"),
    )
    assert read_deno_version(fake) == "1.46.0"


def test_read_deno_version_returns_empty_when_subprocess_fails(monkeypatch, tmp_path: Path):
    fake = tmp_path / "deno.exe"
    fake.write_bytes(b"stub")
    monkeypatch.setattr(
        bootstrap_service.subprocess, "run",
        lambda *args, **kwargs: _FakeCompleted(1, b""),
    )
    assert read_deno_version(fake) == ""


def test_fetch_deno_release_info_picks_the_windows_zip_and_its_sha(monkeypatch):
    """L'API GitHub liste tous les assets ; on repère zip + sidecar sha256."""
    class _Resp:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return (
            b'{"tag_name": "v1.46.0", "assets": ['
            b'{"name": "deno-x86_64-pc-windows-msvc.zip",'
            b' "browser_download_url": "https://g/deno-x86_64-pc-windows-msvc.zip"},'
            b'{"name": "deno-x86_64-pc-windows-msvc.zip.sha256sum",'
            b' "browser_download_url": "https://g/deno-x86_64-pc-windows-msvc.zip.sha256sum"},'
            b'{"name": "deno-x86_64-apple-darwin.zip",'
            b' "browser_download_url": "https://g/mac"}'
            b']}'
        )

    monkeypatch.setattr(
        bootstrap_service.urllib.request, "urlopen",
        lambda request, timeout=10: _Resp(),
    )
    download, sha, tag = fetch_deno_release_info()
    assert download.endswith("deno-x86_64-pc-windows-msvc.zip")
    assert sha.endswith(".sha256sum")
    assert tag == "v1.46.0"


def test_fetch_deno_release_info_returns_empties_when_github_fails(monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("no network")
    monkeypatch.setattr(bootstrap_service.urllib.request, "urlopen", boom)
    assert fetch_deno_release_info() == ("", "", "")


def test_extract_deno_pulls_executable_from_archive(tmp_path: Path):
    """L'archive deno officielle est juste `deno.exe` à la racine."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("deno.exe", b"BINARY-DENO")
    zip_path = tmp_path / "deno.zip"
    zip_path.write_bytes(buffer.getvalue())

    dest = tmp_path / "bin"
    extracted = extract_deno(zip_path, dest)

    assert extracted is not None
    assert extracted.name == "deno.exe"
    assert extracted.read_bytes() == b"BINARY-DENO"


def test_extract_deno_returns_none_when_archive_is_empty(tmp_path: Path):
    """Une archive sans deno.exe doit renvoyer None, pas lever."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("README.md", b"nothing here")
    zip_path = tmp_path / "deno.zip"
    zip_path.write_bytes(buffer.getvalue())

    assert extract_deno(zip_path, tmp_path / "bin") is None


def test_components_for_pulls_deno_when_missing():
    """La résolution des composants inclut deno s'il manque."""
    components = components_for(["deno"])
    assert [c.key for c in components] == ["deno"]


def test_components_for_orders_ytdlp_ffmpeg_deno():
    """Ordre stable : yt-dlp -> ffmpeg -> deno (ordre d'importance décroissante
    au premier démarrage, et aussi ordre historique)."""
    components = components_for(["deno", "yt-dlp", "ffmpeg"])
    assert [c.key for c in components] == ["yt-dlp", "ffmpeg", "deno"]
