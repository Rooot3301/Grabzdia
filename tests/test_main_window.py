from __future__ import annotations

import pytest

from app.models.application_settings import ApplicationSettings
from app.models.media_info import MediaFormat, MediaInfo

pytest.importorskip("pytestqt")


@pytest.fixture
def window(qtbot, monkeypatch):
    from app.ui.main_window import MainWindow

    # Never hit the network for the startup update check during tests.
    monkeypatch.setattr(MainWindow, "_check_updates", lambda self, silent=True: None, raising=False)
    win = MainWindow()
    qtbot.addWidget(win)
    return win


@pytest.fixture
def page(qtbot):
    """A standalone DownloadPage (its error signal is not wired to a dialog)."""
    from app.ui.pages import DownloadPage

    widget = DownloadPage(ApplicationSettings())
    qtbot.addWidget(widget)
    return widget


def test_window_has_three_pages(window):
    assert window.stack.count() == 3


def test_navigation_updates_stack(window):
    window.sidebar.navigated.emit(2)
    assert window.stack.currentIndex() == 2


def test_audio_mode_switches_formats(page):
    page.mode_audio.setChecked(True)
    formats = [page.format.itemText(i) for i in range(page.format.count())]
    assert formats == ["MP3", "M4A", "FLAC", "WAV", "Opus"]
    page.mode_video.setChecked(True)
    formats = [page.format.itemText(i) for i in range(page.format.count())]
    assert formats == ["MP4", "MKV", "WebM"]


def test_enqueue_without_media_emits_error(page):
    received: list[str] = []
    page.error.connect(received.append)
    page._enqueue(True)
    assert received and "Analysez" in received[0]


def test_set_media_enables_actions(page):
    assert not page.download_button.isEnabled()
    page.set_media(
        MediaInfo(
            media_id="id",
            title="Titre",
            original_url="https://example.com/watch?v=id",
            platform="YouTube",
            formats=[MediaFormat(format_id="137", height=1080)],
        )
    )
    assert page.download_button.isEnabled()
    assert page.queue_button.isEnabled()
    assert page.platform_pill.text() == "YouTube"
    assert page.media_title.text() == "Titre"
