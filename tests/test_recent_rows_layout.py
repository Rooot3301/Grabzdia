"""Mise en page des lignes « Derniers téléchargements » (page Accueil).

Bug evo.2 : pastilles « Terminé » et dates désalignées d'une ligne à l'autre
(poussées par la longueur du titre), titres coupés net sans « … », pastille
étirée sur toute la hauteur de la ligne.
"""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QLabel

from app.models.application_settings import ApplicationSettings
from app.services.history_service import HistoryService

LONG = "Hans Zimmer - No Time For Caution (Interstellar Soundtrack) [Official Audio] Extended Version 2026"
SHORT = "Monox"
ROW_WIDTH = 720


@pytest.fixture
def dashboard(qtbot, monkeypatch):
    from app.ui.pages.dashboard_page import DashboardPage

    monkeypatch.setattr(HistoryService, "load", lambda self: [])
    page = DashboardPage(HistoryService(), ApplicationSettings())
    qtbot.addWidget(page)
    # Aucun accès réseau pour les miniatures pendant les tests.
    monkeypatch.setattr(page, "_start_thumbnail_fetch", lambda *_args: None)
    return page


def _row(dashboard, qtbot, title: str):
    entry = {"id": title, "title": title, "url": "", "mode": "audio", "quality": "best",
             "output_format": "mp3", "status": "completed", "finished_at": "2026-11-07T14:49:00+00:00"}
    row = dashboard._recent_row(entry)
    qtbot.addWidget(row)
    row.resize(ROW_WIDTH, row.sizeHint().height())
    row.show()
    qtbot.waitExposed(row)
    return row


def _child(row, name: str) -> QLabel:
    return row.findChild(QLabel, name)


def test_status_and_date_columns_align_across_rows(dashboard, qtbot):
    long_row, short_row = _row(dashboard, qtbot, LONG), _row(dashboard, qtbot, SHORT)
    for name in ("statusPill", "recentDate"):
        assert _child(long_row, name).geometry().x() == _child(short_row, name).geometry().x(), name


def test_long_title_is_elided_with_full_text_in_tooltip(dashboard, qtbot):
    row = _row(dashboard, qtbot, LONG)
    title = _child(row, "recentTitle")
    assert title.text().endswith("…") and len(title.text()) < len(LONG)
    assert title.toolTip() == LONG


def test_short_title_is_untouched(dashboard, qtbot):
    row = _row(dashboard, qtbot, SHORT)
    title = _child(row, "recentTitle")
    assert title.text() == SHORT


def test_status_pill_is_compact_not_full_row_height(dashboard, qtbot):
    row = _row(dashboard, qtbot, SHORT)
    pill = _child(row, "statusPill")
    assert pill.height() <= pill.sizeHint().height() + 2
    assert pill.height() < row.height() / 2
