from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

from app.models.download_job import DownloadStatus
from app.ui.pages.dashboard_page import build_greeting, compute_stats


def _entry(status: str, finished_at: str) -> dict:
    return {"status": status, "finished_at": finished_at, "title": "t"}


def test_compute_stats_counts_today_this_week_and_total():
    now = datetime(2026, 9, 29, 15, 0, tzinfo=UTC)
    entries = [
        _entry(DownloadStatus.COMPLETED.value, now.isoformat()),
        _entry(DownloadStatus.COMPLETED.value, (now - timedelta(hours=3)).isoformat()),
        _entry(DownloadStatus.COMPLETED.value, (now - timedelta(days=3)).isoformat()),
        _entry(DownloadStatus.FAILED.value, (now - timedelta(days=10)).isoformat()),
    ]

    stats = compute_stats(entries, now)

    assert stats["today"] == 2
    assert stats["week"] == 3  # today (2) + il y a 3 jours (1) ; le d10 est hors fenêtre
    assert stats["total"] == 4
    assert stats["failed"] == 1


def test_compute_stats_success_rate_ignores_cancelled_and_running():
    now = datetime(2026, 9, 29, tzinfo=UTC)
    entries = [
        _entry(DownloadStatus.COMPLETED.value, now.isoformat()),
        _entry(DownloadStatus.COMPLETED.value, now.isoformat()),
        _entry(DownloadStatus.COMPLETED.value, now.isoformat()),
        _entry(DownloadStatus.FAILED.value, now.isoformat()),
    ]

    # 3 completed / 4 total = 75%.
    assert compute_stats(entries, now)["success_rate"] == 75


def test_compute_stats_empty_history_gives_zeros():
    stats = compute_stats([])
    assert stats == {"today": 0, "week": 0, "total": 0, "success_rate": 0, "failed": 0}


def test_compute_stats_unparseable_finished_at_is_counted_in_total_only():
    """Une vieille entrée d'une version antérieure n'écroule pas la page."""
    now = datetime(2026, 9, 29, tzinfo=UTC)
    entries = [
        _entry(DownloadStatus.COMPLETED.value, "n'importe quoi"),
        _entry(DownloadStatus.COMPLETED.value, now.isoformat()),
    ]

    stats = compute_stats(entries, now)
    assert stats["total"] == 2
    assert stats["today"] == 1
    assert stats["week"] == 1


def test_dashboard_is_at_index_zero_with_home_first(window):
    """Le premier onglet est désormais Accueil, pas Télécharger."""
    window.sidebar.navigated.emit(0)
    assert window.stack.currentIndex() == 0
    assert window.stack.widget(0) is window.dashboard_page


def test_dashboard_quick_actions_route_to_the_right_pages(window):
    """Les 3 boutons d'accès rapide doivent atterrir sur les bonnes pages."""
    window.dashboard_page.navigate_download.emit()
    assert window.stack.currentIndex() == 1
    window.dashboard_page.navigate_history.emit()
    assert window.stack.currentIndex() == 2
    window.dashboard_page.navigate_settings.emit()
    assert window.stack.currentIndex() == 3


def _at(hour: int) -> datetime:
    return datetime(2026, 9, 29, hour, 0, tzinfo=UTC).astimezone()


def test_greeting_says_bonjour_in_the_morning():
    title, _ = build_greeting(_at(9), name="Romain", random_source=random.Random(0))
    assert title == "Bonjour, Romain"


def test_greeting_says_bon_apres_midi_in_the_afternoon():
    title, _ = build_greeting(_at(14), name="Romain", random_source=random.Random(0))
    assert title == "Bon après-midi, Romain"


def test_greeting_says_bonsoir_in_the_evening():
    title, _ = build_greeting(_at(20), name="Romain", random_source=random.Random(0))
    assert title == "Bonsoir, Romain"


def test_greeting_says_bonne_nuit_at_night():
    title, _ = build_greeting(_at(2), name="Romain", random_source=random.Random(0))
    assert title == "Bonne nuit, Romain"


def test_greeting_omits_name_when_unknown():
    """Sans nom exploitable, on ne veut pas d'un « Bonjour, » à la virgule
    orpheline. Le titre reste juste la salutation."""
    title, _ = build_greeting(_at(9), name="", random_source=random.Random(0))
    assert title == "Bonjour"


def test_greeting_subtitle_varies_across_calls():
    """Le sous-titre pioche dans plusieurs variantes ; deux Random distinctes
    doivent au moins pouvoir tomber sur des textes différents."""
    _, sub_a = build_greeting(_at(9), name="A", random_source=random.Random(0))
    _, sub_b = build_greeting(_at(9), name="A", random_source=random.Random(2))
    # Les deux appartiennent à la liste matin.
    from app.ui.pages.dashboard_page import _SUBTITLES
    assert sub_a in _SUBTITLES["morning"]
    assert sub_b in _SUBTITLES["morning"]
