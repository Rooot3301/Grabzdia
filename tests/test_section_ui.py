"""Interface « Extrait uniquement » de la page Télécharger."""
from __future__ import annotations

import pytest

from app.models.application_settings import ApplicationSettings
from app.models.media_info import MediaInfo

EIGHT_HOURS = 8 * 3600


@pytest.fixture
def page(qtbot, tmp_path):
    from app.ui.pages import DownloadPage

    settings = ApplicationSettings()
    settings.default_download_directory = str(tmp_path)
    settings.last_download_directory = str(tmp_path)
    widget = DownloadPage(settings)
    qtbot.addWidget(widget)
    return widget


def _media(**overrides) -> MediaInfo:
    base = {"media_id": "vod", "title": "VOD", "original_url": "https://www.twitch.tv/videos/1", "duration": float(EIGHT_HOURS)}
    base.update(overrides)
    return MediaInfo(**base)


def _jobs(page) -> list:
    jobs: list = []
    page.job_ready.connect(lambda job, _start: jobs.append(job))
    return jobs


def _errors(page) -> list[str]:
    errors: list[str] = []
    page.error.connect(errors.append)
    return errors


def _choose(page, start: str, end: str) -> None:
    page.section_box.setChecked(True)
    page.section_start.setText(start)
    page.section_end.setText(end)


# ---- disponibilité -----------------------------------------------------------

def test_section_is_unavailable_before_analysis(page):
    assert not page.section_box.isEnabled()
    assert not page.section_start.isEnabled()


def test_analysis_prefills_the_whole_media(page):
    page.set_media(_media())
    assert page.section_box.isEnabled()
    assert not page.section_box.isChecked()
    assert page.section_start.text() == "00:00:00"
    assert page.section_end.text() == "08:00:00"
    assert not page.section_start.isEnabled()  # tant que la case n'est pas cochée


def test_checking_the_box_enables_the_fields(page):
    page.set_media(_media())
    page.section_box.setChecked(True)
    assert page.section_start.isEnabled() and page.section_end.isEnabled()


@pytest.mark.parametrize("media", [_media(duration=None), _media(duration=0.0), _media(is_playlist=True)])
def test_section_is_unavailable_without_duration_or_for_playlists(page, media):
    page.set_media(media)
    assert not page.section_box.isEnabled()


def test_ticking_playlist_disables_and_clears_the_section(page):
    page.set_media(_media())
    page.section_box.setChecked(True)
    page.playlist.setChecked(True)
    assert not page.section_box.isEnabled()
    assert not page.section_box.isChecked()


def test_new_analysis_resets_a_previous_range(page):
    page.set_media(_media())
    _choose(page, "1:00", "2:00")
    page.set_media(_media(media_id="autre", duration=600.0))
    assert not page.section_box.isChecked()
    assert (page.section_start.text(), page.section_end.text()) == ("00:00:00", "00:10:00")


# ---- ajout en file -----------------------------------------------------------

def test_enqueue_carries_the_chosen_range(page):
    page.set_media(_media())
    jobs = _jobs(page)
    _choose(page, "2:00:00", "2:15:30")
    page._enqueue(False)
    assert len(jobs) == 1
    assert (jobs[0].section_start, jobs[0].section_end) == (7200, 8130)


def test_unchecked_box_means_full_download(page):
    page.set_media(_media())
    jobs = _jobs(page)
    page.section_start.setText("1:00")  # saisi mais case décochée
    page._enqueue(False)
    assert jobs[0].has_section() is False


def test_whole_range_is_a_full_download(page):
    page.set_media(_media())
    jobs = _jobs(page)
    _choose(page, "0", "8:00:00")
    page._enqueue(False)
    assert jobs[0].has_section() is False


@pytest.mark.parametrize(
    ("start", "end", "message"),
    [
        ("10:00", "5:00", "précéder"),
        ("10:00", "10:00", "précéder"),
        ("0", "9:00:00", "durée"),
        ("abc", "5:00", "hh:mm:ss"),
        ("1:00", "", "hh:mm:ss"),
    ],
)
def test_invalid_range_is_refused(page, start, end, message):
    page.set_media(_media())
    jobs, errors = _jobs(page), _errors(page)
    _choose(page, start, end)
    page._enqueue(False)
    assert jobs == []
    assert errors and message in errors[0]


def test_end_rounding_up_a_fractional_duration_is_accepted(page):
    page.set_media(_media(duration=19.4))
    jobs = _jobs(page)
    _choose(page, "5", "20")
    page._enqueue(False)
    assert jobs and jobs[0].section_end == 20


# ---- taille estimée ----------------------------------------------------------

def test_size_estimate_is_prorated_to_the_range(page):
    hundred_gb = 100 * 1024**3
    page.set_media(_media(formats=[], estimated_size=hundred_gb))
    assert page._effective_estimate() == hundred_gb
    _choose(page, "0", "48:00")  # 1/10 de 8 h
    assert page._effective_estimate() == pytest.approx(hundred_gb / 10)


def test_invalid_range_falls_back_to_the_full_estimate(page):
    page.set_media(_media(estimated_size=1000))
    _choose(page, "zz", "48:00")
    assert page._effective_estimate() == 1000


def test_hint_shows_the_range_length(page):
    page.set_media(_media())
    _choose(page, "1:00:00", "1:45:00")
    assert "00:45:00" in page.section_hint.text()


def test_hint_shows_the_error_while_typing(page):
    page.set_media(_media())
    _choose(page, "2:00", "1:00")
    assert "précéder" in page.section_hint.text()


# ---- carte de file et re-téléchargement --------------------------------------

def test_queue_card_mentions_the_range(qtbot):
    from app.models.download_job import DownloadJob
    from app.ui.download_item_widget import DownloadItemWidget

    job = DownloadJob(url="https://example.com/v", title="v", mode="video", quality="1080p", output_format="mp4",
                      destination=".", filename_template="%(title)s.%(ext)s", section_start=300, section_end=600)
    item = DownloadItemWidget(job)
    qtbot.addWidget(item)
    assert "Extrait 00:05:00 → 00:10:00" in item.details.text()


def test_redownload_from_history_keeps_the_range(window, monkeypatch):
    queued: list = []
    monkeypatch.setattr(window.manager, "enqueue", lambda job, start=True: queued.append(job))
    window._redownload({"url": "https://example.com/v", "title": "v", "section_start": 300, "section_end": 600})
    assert (queued[0].section_start, queued[0].section_end) == (300, 600)
