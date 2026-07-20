from __future__ import annotations

import pytest

from app.exceptions import BinaryNotFoundError
from app.services.binary_service import BinaryService


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    managed = tmp_path / "managed"
    bundled = tmp_path / "bundled"
    managed.mkdir()
    bundled.mkdir()
    monkeypatch.setattr("app.services.binary_service.managed_binary_dir", lambda: managed)
    monkeypatch.setattr("app.services.binary_service.binary_dir", lambda: bundled)
    monkeypatch.setattr("app.services.binary_service.shutil.which", lambda *_: None)
    return managed, bundled


def test_locate_prefers_managed_dir(dirs):
    managed, bundled = dirs
    (managed / "yt-dlp.exe").write_text("x")
    (bundled / "yt-dlp.exe").write_text("x")
    assert BinaryService().locate("yt-dlp") == managed / "yt-dlp.exe"


def test_locate_falls_back_to_bundled_dir(dirs):
    _managed, bundled = dirs
    (bundled / "ffmpeg.exe").write_text("x")
    assert BinaryService().locate("ffmpeg") == bundled / "ffmpeg.exe"


def test_locate_raises_when_absent_everywhere(dirs):
    with pytest.raises(BinaryNotFoundError):
        BinaryService().locate("ffprobe")


def test_missing_lists_all_absent(dirs):
    assert sorted(BinaryService().missing()) == ["ffmpeg", "ffprobe", "yt-dlp"]


def test_missing_is_empty_when_all_present(dirs):
    managed, _bundled = dirs
    for name in ("yt-dlp.exe", "ffmpeg.exe", "ffprobe.exe"):
        (managed / name).write_text("x")
    assert BinaryService().missing() == []
