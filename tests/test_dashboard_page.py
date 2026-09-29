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


def _all_titles_at(hour: int, name: str) -> set[str]:
    """Passe en revue plusieurs seeds pour observer la diversité des tirages."""
    out: set[str] = set()
    for seed in range(50):
        title, _ = build_greeting(_at(hour), name=name, random_source=random.Random(seed))
        out.add(title)
    return out


def test_greeting_titles_include_the_name_when_provided_morning():
    """Sur 50 tirages du matin avec un nom, tous les titres qui contiennent
    « Romain » sont valides et au moins un tirage sans nom (« Bonjour »
    tout court) est possible parmi le mix."""
    titles = _all_titles_at(9, "Romain")
    # Au moins une variante nommée est présente.
    assert any("Romain" in t for t in titles)
    # Plusieurs variantes distinctes sont bien piochées.
    assert len(titles) >= 4


def test_greeting_uses_morning_vocabulary_only_in_the_morning():
    """Les tranches horaires sont exclusives — pas de « Bonsoir » à 9h."""
    titles = _all_titles_at(9, "Alex")
    joined = " ".join(titles).lower()
    assert "bonsoir" not in joined
    assert "bonne nuit" not in joined


def test_greeting_uses_evening_vocabulary_only_in_the_evening():
    titles = _all_titles_at(20, "Alex")
    joined = " ".join(titles).lower()
    assert "bonjour" not in joined
    assert "bonne nuit" not in joined


def test_greeting_uses_night_vocabulary_only_at_night():
    titles = _all_titles_at(2, "Alex")
    joined = " ".join(titles).lower()
    assert "bon après-midi" not in joined
    assert "bonsoir" not in joined


def test_greeting_omits_name_and_never_leaves_a_dangling_placeholder():
    """Sans nom, aucun titre ne doit contenir la marque {name} ni finir
    par une virgule orpheline (le filtre écarte tous les templates avec
    {name}, il ne reste que ceux qui marchent sans)."""
    titles = _all_titles_at(9, "")
    assert titles
    for title in titles:
        assert "{name}" not in title
        assert not title.rstrip().endswith(",")


def test_greeting_subtitle_stays_within_the_matching_slot():
    """Le sous-titre pioche parmi ~7 variantes par créneau ; il doit
    appartenir au bon créneau, pas déborder sur un autre."""
    from app.ui.pages.dashboard_page import _SUBTITLES
    _, sub = build_greeting(_at(9), name="A", random_source=random.Random(0))
    assert sub in _SUBTITLES["morning"]


def test_cta_button_navigates_to_download(window):
    """Le CTA « Nouveau téléchargement » doit ouvrir la page Télécharger."""
    window.dashboard_page.cta.click()
    assert window.stack.currentIndex() == 1


def test_kebab_copy_url_uses_clipboard_and_reports_in_statusbar(window):
    """Le menu kebab de la page Accueil doit émettre copy_url_requested,
    handler qui met l'URL dans le presse-papier et loggue en statusbar."""
    from PySide6.QtWidgets import QApplication

    received: list[str] = []
    window.dashboard_page.copy_url_requested.connect(received.append)

    window.dashboard_page.copy_url_requested.emit("https://example.com/x")

    assert received == ["https://example.com/x"]
    # Handler MainWindow doit avoir écrit dans le presse-papier :
    assert QApplication.clipboard().text() == "https://example.com/x"


def test_kebab_delete_removes_from_history(window, tmp_path, monkeypatch):
    """Suppression d'une entrée via le kebab : l'historique perd la ligne
    et le dashboard se re-render (le compteur Total baisse)."""
    from app.services.history_service import HistoryService

    fake_history = HistoryService()
    monkeypatch.setattr(fake_history, "load", lambda: [
        {"id": "abc", "title": "t", "url": "u", "status": "completed",
         "finished_at": "2026-09-29T15:00:00+00:00"},
    ])
    removed: list[str] = []
    monkeypatch.setattr(fake_history, "remove", removed.append)
    window.history_service = fake_history
    window.dashboard_page.history = fake_history

    window.dashboard_page.delete_entry_requested.emit("abc")

    assert removed == ["abc"]
