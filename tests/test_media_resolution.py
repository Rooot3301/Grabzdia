from __future__ import annotations

from pathlib import Path

from app.services.disk_service import DiskService


def test_resolve_direct_path(tmp_path: Path):
    f = tmp_path / "video [abcdef123].mp4"
    f.write_bytes(b"x")
    assert DiskService.resolve_media_path(str(f)) == str(f)


def test_resolve_falls_back_to_destination(tmp_path: Path):
    real = tmp_path / "video [abcdef123].mp4"
    real.write_bytes(b"x")
    stale = r"C:\Old\video [abcdef123].mp4"
    assert DiskService.resolve_media_path(stale, str(tmp_path)) == str(real)


def test_resolve_matches_by_id_when_name_differs(tmp_path: Path):
    # File on disk has a sanitised name (fullwidth colon), stored name differs,
    # but the [id] token matches.
    real = tmp_path / "The Future： StarEngine [nWm_OhIKms8].mp4"
    real.write_bytes(b"x")
    stored = r"C:\Old\The Future StarEngine [nWm_OhIKms8].mp4"
    assert DiskService.resolve_media_path(stored, str(tmp_path)) == str(real)


def test_resolve_returns_none_when_absent(tmp_path: Path):
    assert DiskService.resolve_media_path(r"C:\nope\gone [zzzzzz99].mp4", str(tmp_path)) is None


def test_resolve_none_for_empty():
    assert DiskService.resolve_media_path("") is None
