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
    # Do not launch a real yt-dlp process: verify the job is built and enqueued.
    monkeypatch.setattr(win.manager, "start_available", lambda: None)
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


def test_runner_keeps_the_last_output_lines_only():
    from app.models.download_job import DownloadJob
    from app.services.download_service import TAIL_LINES, DownloadRunner

    job = DownloadJob(
        url="https://example.com/v", title="t", mode="video", quality="1080p",
        output_format="mp4", destination=".", filename_template="%(title)s.%(ext)s",
    )
    runner = DownloadRunner(job, binaries=None)
    for index in range(TAIL_LINES + 20):
        runner.tail.append(f"ligne {index}")
    assert len(runner.tail) == TAIL_LINES
    assert runner.tail[-1] == f"ligne {TAIL_LINES + 19}"


def test_failed_download_records_reason_hint_and_output():
    """La sortie retenue doit produire un motif, pas la phrase générique."""
    from app.models.download_job import DownloadJob
    from app.services.download_service import DownloadRunner

    job = DownloadJob(
        url="https://example.com/v", title="t", mode="video", quality="1080p",
        output_format="mp4", destination=".", filename_template="%(title)s.%(ext)s",
    )
    runner = DownloadRunner(job, binaries=None)
    runner.tail.append("ERROR: Video unavailable")
    received: list[tuple[str, str]] = []
    runner.failed.connect(lambda job_id, message: received.append((job_id, message)))

    runner._done(1, None)

    assert received and received[0][1] == "Vidéo indisponible"
    assert job.error_hint
    assert "Video unavailable" in job.error_output


def test_error_dialog_hides_an_empty_hint(qtbot):
    from app.ui.error_dialog import ErrorDialog

    with_hint = ErrorDialog("Titre", "Motif", "Un conseil", "ERROR: brut")
    without_hint = ErrorDialog("Titre", "Motif", "", "ERROR: brut")
    qtbot.addWidget(with_hint)
    qtbot.addWidget(without_hint)
    assert not with_hint.hint.isHidden()
    assert without_hint.hint.isHidden()


def test_error_dialog_copy_text_carries_everything(qtbot):
    from app.ui.error_dialog import ErrorDialog

    dialog = ErrorDialog("Ma vidéo", "Vidéo indisponible", "Elle a été supprimée.", "ERROR: Video unavailable")
    qtbot.addWidget(dialog)
    text = dialog.copy_text()
    assert "Vidéo indisponible" in text
    assert "Elle a été supprimée." in text
    assert "ERROR: Video unavailable" in text


def test_queue_item_shows_details_only_on_a_failed_job(qtbot):
    from app.models.download_job import DownloadJob, DownloadStatus
    from app.ui.download_item_widget import DownloadItemWidget

    job = DownloadJob(
        url="https://example.com/v", title="t", mode="video", quality="1080p",
        output_format="mp4", destination=".", filename_template="%(title)s.%(ext)s",
    )
    widget = DownloadItemWidget(job)
    qtbot.addWidget(widget)
    assert widget.details_button.isHidden()

    job.status = DownloadStatus.FAILED
    job.error = "Vidéo indisponible"
    widget.update_job(job)
    assert not widget.details_button.isHidden()


def test_queue_item_details_button_emits_the_job_id(qtbot):
    from app.models.download_job import DownloadJob, DownloadStatus
    from app.ui.download_item_widget import DownloadItemWidget

    job = DownloadJob(
        url="https://example.com/v", title="t", mode="video", quality="1080p",
        output_format="mp4", destination=".", filename_template="%(title)s.%(ext)s",
    )
    job.status = DownloadStatus.FAILED
    job.error = "Vidéo indisponible"
    widget = DownloadItemWidget(job)
    qtbot.addWidget(widget)
    received: list[str] = []
    widget.details_requested.connect(received.append)
    widget.details_button.click()
    assert received == [job.id]


def test_format_timestamp_renders_a_readable_date():
    from app.ui.widgets import format_timestamp

    assert format_timestamp("2026-07-27T09:15:32+00:00").count("/") == 2


def test_format_timestamp_passes_through_unparseable_values():
    """L’historique contient des entrées écrites par des versions antérieures."""
    from app.ui.widgets import format_timestamp

    assert format_timestamp("pas une date") == "pas une date"
    assert format_timestamp("") == ""


def test_status_labels_accept_raw_history_strings():
    """DownloadStatus est un StrEnum : ses membres s’indexent avec la chaîne brute."""
    from app.ui.widgets import STATUS_LABELS

    assert STATUS_LABELS["completed"] == "Terminé"
    assert STATUS_LABELS["failed"] == "Échec"


def test_unknown_status_falls_back_to_its_raw_value(qtbot, monkeypatch):
    """Une entrée écrite par une version future ne doit pas afficher une case vide."""
    page = _history_page(qtbot, monkeypatch, [_entry(status="quelque_chose")])
    assert page.table.item(0, 4).text() == "quelque_chose"


def _history_page(qtbot, monkeypatch, entries):
    from app.services.history_service import HistoryService
    from app.ui.pages.history_page import HistoryPage

    monkeypatch.setattr(HistoryService, "load", lambda self: list(entries))
    page = HistoryPage(HistoryService())
    qtbot.addWidget(page)
    return page


def _entry(**overrides):
    base = {
        "id": "1", "title": "Une vidéo", "mode": "video", "quality": "1080p",
        "output_format": "mp4", "status": "completed", "finished_at": "2026-07-27T09:15:32+00:00",
        "destination": ".", "final_path": "", "error": "", "error_hint": "", "error_output": "",
    }
    base.update(overrides)
    return base


def test_history_status_filter_isolates_failures(qtbot, monkeypatch):
    entries = [
        _entry(id="1", status="completed"),
        _entry(id="2", status="failed", error="Vidéo indisponible"),
    ]
    page = _history_page(qtbot, monkeypatch, entries)
    assert page.table.rowCount() == 2
    page.status_filter.setCurrentIndex(page.status_filter.findData("failed"))
    assert page.table.rowCount() == 1
    assert page._rendered[0]["id"] == "2"


def test_history_type_filter_combines_with_search(qtbot, monkeypatch):
    entries = [
        _entry(id="1", title="Concert", mode="audio"),
        _entry(id="2", title="Concert", mode="video"),
        _entry(id="3", title="Autre", mode="audio"),
    ]
    page = _history_page(qtbot, monkeypatch, entries)
    page.type_filter.setCurrentIndex(page.type_filter.findData("audio"))
    page.search.setText("concert")
    assert [entry["id"] for entry in page._rendered] == ["1"]


def test_history_shows_the_failure_reason_in_the_status_cell(qtbot, monkeypatch):
    entries = [_entry(id="1", status="failed", error="Vidéo indisponible")]
    page = _history_page(qtbot, monkeypatch, entries)
    assert "Échec" in page.table.item(0, 4).text()
    assert "Vidéo indisponible" in page.table.item(0, 4).text()


def test_history_translates_status_and_mode(qtbot, monkeypatch):
    page = _history_page(qtbot, monkeypatch, [_entry(mode="audio", status="completed")])
    assert page.table.item(0, 1).text() == "Audio"
    assert page.table.item(0, 4).text() == "Terminé"


def test_history_delete_removes_the_selected_entry(qtbot, monkeypatch):
    from app.services.history_service import HistoryService

    removed: list[str] = []
    monkeypatch.setattr(HistoryService, "remove", lambda self, job_id: removed.append(job_id))
    page = _history_page(qtbot, monkeypatch, [_entry(id="42")])
    page.table.selectRow(0)
    page.delete_entry(confirm=False)
    assert removed == ["42"]


def test_history_details_button_needs_a_failed_entry(qtbot, monkeypatch):
    entries = [_entry(id="1", status="completed"), _entry(id="2", status="failed", error="Vidéo indisponible")]
    page = _history_page(qtbot, monkeypatch, entries)
    page.table.selectRow(0)
    assert not page.details_button.isEnabled()
    page.table.selectRow(1)
    assert page.details_button.isEnabled()
