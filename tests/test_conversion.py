"""Conversion après téléchargement (Montage H.264 / Compacte H.265).
Spec : docs/superpowers/specs/2026-11-23-conversion-montage-design.md"""
from __future__ import annotations

from app.models.application_settings import ApplicationSettings
from app.models.download_job import DownloadJob


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
