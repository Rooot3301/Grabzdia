from __future__ import annotations

import pytest

from app.models.application_settings import ApplicationSettings
from app.models.media_info import MediaFormat, MediaInfo

pytest.importorskip("pytestqt")


def test_settings_roundtrip_keeps_new_fields():
    settings = ApplicationSettings()
    settings.last_mode = "audio"
    settings.last_audio_format = "FLAC"
    settings.auto_update_ytdlp = True
    restored = ApplicationSettings.from_dict(settings.to_dict())
    assert restored.last_mode == "audio"
    assert restored.last_audio_format == "FLAC"
    assert restored.auto_update_ytdlp is True


def test_settings_from_legacy_dict_uses_defaults():
    # An old settings file without the new keys must still load.
    legacy = {"theme": "dark", "parallel_downloads": 3}
    restored = ApplicationSettings.from_dict(legacy)
    assert restored.parallel_downloads == 3
    assert restored.last_mode == "video"
    assert restored.auto_update_ytdlp is False


@pytest.fixture
def page(qtbot, tmp_path):
    from app.ui.pages import DownloadPage

    settings = ApplicationSettings()
    settings.default_download_directory = str(tmp_path)
    settings.last_download_directory = str(tmp_path)
    widget = DownloadPage(settings)
    qtbot.addWidget(widget)
    return widget


def test_batch_enqueues_valid_urls_only(page):
    jobs: list[object] = []
    page.job_ready.connect(lambda job, _start: jobs.append(job))
    page.enqueue_batch([
        "https://example.com/a",
        "   ",
        "not a url",
        "ftp://example.com/x",
        "https://example.com/b",
    ])
    assert len(jobs) == 2
    assert {job.url for job in jobs} == {"https://example.com/a", "https://example.com/b"}


def test_batch_reports_error_when_no_valid_url(page):
    errors: list[str] = []
    page.error.connect(errors.append)
    page.enqueue_batch(["nope", "also nope"])
    assert errors


def test_remembered_options_are_restored(qtbot, tmp_path):
    from app.ui.pages import DownloadPage

    settings = ApplicationSettings()
    settings.default_download_directory = str(tmp_path)
    settings.last_download_directory = str(tmp_path)
    settings.last_mode = "audio"
    settings.last_audio_format = "Opus"
    page = DownloadPage(settings)
    qtbot.addWidget(page)
    assert page.mode_audio.isChecked()
    assert page.format.currentText() == "Opus"


def test_redownload_from_history_builds_job(qtbot, monkeypatch):
    from app.ui.main_window import MainWindow

    monkeypatch.setattr(MainWindow, "_check_updates", lambda self, silent=True: None, raising=False)
    win = MainWindow()
    qtbot.addWidget(win)
    entry = {
        "url": "https://example.com/watch?v=abc",
        "title": "Ancienne vidéo",
        "mode": "video",
        "quality": "720p",
        "output_format": "mkv",
        "destination": "",
    }
    win._redownload(entry)
    assert any(job.url == "https://example.com/watch?v=abc" for job in win.manager.jobs)
    assert win.stack.currentIndex() == 0


def test_history_search_filters(qtbot, tmp_path, monkeypatch):
    from app.services.history_service import HistoryService
    from app.ui.pages import HistoryPage

    service = HistoryService()
    entries = [
        {"title": "Documentaire nature", "status": "completed"},
        {"title": "Concert live", "status": "completed"},
    ]
    monkeypatch.setattr(service, "load", lambda: entries)
    page = HistoryPage(service)
    qtbot.addWidget(page)
    assert page.table.rowCount() == 2
    page.search.setText("concert")
    assert page.table.rowCount() == 1


def test_media_info_unused_import_guard():
    # Ensure the shared imports resolve (guards against accidental breakage).
    info = MediaInfo(media_id="i", title="t", original_url="https://x/y", formats=[MediaFormat(format_id="1")])
    assert info.title == "t"
