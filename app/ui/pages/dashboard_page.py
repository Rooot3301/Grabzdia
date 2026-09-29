from __future__ import annotations

import os
import random
from datetime import UTC, datetime, timedelta
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.models.download_job import DownloadStatus
from app.services.history_service import HistoryService
from app.ui.widgets import eyebrow_label, format_timestamp
from app.version import __version__


# Quatre créneaux, sans overlap : minuit-4h59 la nuit, puis matin/après-midi/
# soir. Choix français : « après-midi » distinct de « soir » parce que la
# différence entre 14 h et 21 h côté ambiance est vraie.
def _time_slot(now: datetime) -> str:
    hour = now.hour
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 18:
        return "afternoon"
    if 18 <= hour < 23:
        return "evening"
    return "night"


_GREETINGS = {
    "morning": "Bonjour",
    "afternoon": "Bon après-midi",
    "evening": "Bonsoir",
    "night": "Bonne nuit",
}

_SUBTITLES = {
    "morning": [
        "On télécharge quoi aujourd'hui ?",
        "Prêt à démarrer la journée ?",
        "Un lien à récupérer avant le café ?",
    ],
    "afternoon": [
        "On continue sur quoi ?",
        "Une pause média ?",
        "Qu'est-ce qu'on ajoute à la file ?",
    ],
    "evening": [
        "On écoute quoi ce soir ?",
        "Un dernier téléchargement avant de couper ?",
        "Prêt pour la playlist du soir ?",
    ],
    "night": [
        "Encore debout ? Un dernier lien ?",
        "Silencieux et efficace, comme d'habitude.",
        "La file tourne pendant que tu dors.",
    ],
}


def _display_name() -> str:
    """Nom à afficher dans la salutation, ou '' pour tomber sur « Bonjour, »
    sans nom quand l'environnement n'en fournit pas.

    Lit USERNAME (Windows) puis USER (POSIX), rejette les valeurs vides ou
    du genre 'root'/'user' qui feraient sonner faux la salutation.
    """
    raw = (os.environ.get("USERNAME") or os.environ.get("USER") or "").strip()
    if not raw or raw.lower() in {"user", "root", "administrator", "admin"}:
        return ""
    # Windows expose souvent l'identifiant en minuscules ; on capitalise le
    # premier segment pour un affichage propre sans casser un « Jean-Marc ».
    return raw.split()[0].capitalize()


def build_greeting(now: datetime | None = None, name: str | None = None,
                    random_source: random.Random | None = None) -> tuple[str, str]:
    """Salutation (titre, sous-titre) selon l'heure et l'utilisateur.

    Extraite pour tests : l'aléatoire du sous-titre est injectable.
    """
    reference = (now or datetime.now(UTC)).astimezone()
    slot = _time_slot(reference)
    who = name if name is not None else _display_name()
    title = f"{_GREETINGS[slot]}, {who}" if who else _GREETINGS[slot]
    picker = random_source or random.Random()
    subtitle = picker.choice(_SUBTITLES[slot])
    return title, subtitle


def compute_stats(entries: list[dict[str, Any]], now: datetime | None = None) -> dict[str, Any]:
    """Compress the raw history into the five KPI shown on the dashboard.

    Split out from the widget so it's unit-testable without any Qt state.
    An entry with an unparseable finished_at is counted in the totals but
    not in the time-scoped windows — no crash, no silent drop.
    """
    reference = (now or datetime.now(UTC)).astimezone()
    today = reference.date()
    week_cutoff = reference - timedelta(days=7)

    total = len(entries)
    completed_total = 0
    today_count = 0
    week_count = 0
    failed_count = 0
    for entry in entries:
        status = str(entry.get("status", ""))
        if status == DownloadStatus.COMPLETED.value:
            completed_total += 1
        elif status == DownloadStatus.FAILED.value:
            failed_count += 1
        raw = str(entry.get("finished_at", ""))
        try:
            timestamp = datetime.fromisoformat(raw).astimezone()
        except (TypeError, ValueError):
            continue
        if timestamp.date() == today:
            today_count += 1
        if timestamp >= week_cutoff:
            week_count += 1

    success_rate = int(round(100 * completed_total / total)) if total else 0
    return {
        "today": today_count,
        "week": week_count,
        "total": total,
        "success_rate": success_rate,
        "failed": failed_count,
    }


class DashboardPage(QWidget):
    """Home page: KPI at a glance + quick access to the main actions.

    Refreshed on every navigation to it (see refresh()) so it reflects the
    current state of the history, not a stale snapshot from window open.
    """

    navigate_download = Signal()
    navigate_history = Signal()
    navigate_settings = Signal()

    def __init__(self, history: HistoryService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.history = history

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 30, 36, 30)
        root.setSpacing(16)

        # En-tête construit à la main (au lieu de page_header) pour que la
        # salutation puisse changer à chaque refresh() sans reconstruire.
        header = QWidget()
        header.setObjectName("plainContainer")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)
        header_layout.addWidget(eyebrow_label("Accueil"))
        self._greeting_title = QLabel()
        self._greeting_title.setObjectName("pageTitle")
        header_layout.addWidget(self._greeting_title)
        self._greeting_subtitle = QLabel()
        self._greeting_subtitle.setObjectName("pageSubtitle")
        self._greeting_subtitle.setWordWrap(True)
        header_layout.addWidget(self._greeting_subtitle)
        self._version_hint = QLabel(f"Grabzdia {__version__}")
        self._version_hint.setObjectName("mutedText")
        header_layout.addWidget(self._version_hint)
        root.addWidget(header)

        # ---- KPI grid ------------------------------------------------------
        self._stats_grid = QGridLayout()
        self._stats_grid.setHorizontalSpacing(14)
        self._stats_grid.setVerticalSpacing(14)
        self._stat_cards: dict[str, QFrame] = {}
        self._stat_values: dict[str, QLabel] = {}
        # Ordered so a smaller window still shows the two most useful first.
        keys = [
            ("today", "Aujourd'hui"),
            ("week", "Cette semaine"),
            ("total", "Total"),
            ("success_rate", "Taux de succès"),
        ]
        for index, (key, label) in enumerate(keys):
            card = QFrame()
            card.setObjectName("statCard")
            layout = QVBoxLayout(card)
            layout.setContentsMargins(18, 16, 18, 16)
            layout.setSpacing(4)
            layout.addWidget(eyebrow_label(label))
            value = QLabel("—")
            value.setObjectName("statValue")
            layout.addWidget(value)
            layout.addStretch()
            self._stat_cards[key] = card
            self._stat_values[key] = value
            self._stats_grid.addWidget(card, 0, index)
        root.addLayout(self._stats_grid)

        # ---- Quick actions -------------------------------------------------
        actions_card = QFrame()
        actions_card.setObjectName("card")
        actions_layout = QVBoxLayout(actions_card)
        actions_layout.setContentsMargins(20, 18, 20, 18)
        actions_layout.setSpacing(10)
        actions_layout.addWidget(eyebrow_label("Actions rapides"))
        row = QHBoxLayout()
        row.setSpacing(10)
        new_download = QPushButton("Nouveau téléchargement")
        new_download.setObjectName("primaryButton")
        new_download.setCursor(Qt.CursorShape.PointingHandCursor)
        new_download.clicked.connect(self.navigate_download)
        open_history = QPushButton("Voir l'historique")
        open_history.setObjectName("ghostButton")
        open_history.setCursor(Qt.CursorShape.PointingHandCursor)
        open_history.clicked.connect(self.navigate_history)
        open_settings = QPushButton("Paramètres")
        open_settings.setObjectName("ghostButton")
        open_settings.setCursor(Qt.CursorShape.PointingHandCursor)
        open_settings.clicked.connect(self.navigate_settings)
        row.addWidget(new_download)
        row.addWidget(open_history)
        row.addWidget(open_settings)
        row.addStretch()
        actions_layout.addLayout(row)
        root.addWidget(actions_card)

        # ---- Recent entries -----------------------------------------------
        recent_card = QFrame()
        recent_card.setObjectName("card")
        recent_layout = QVBoxLayout(recent_card)
        # Plus d'air : marges + interligne + eyebrow séparée du contenu.
        recent_layout.setContentsMargins(24, 22, 24, 24)
        recent_layout.setSpacing(14)
        recent_layout.addWidget(eyebrow_label("Derniers téléchargements"))
        self._recent_container = QWidget()
        self._recent_container_layout = QVBoxLayout(self._recent_container)
        self._recent_container_layout.setContentsMargins(0, 0, 0, 0)
        self._recent_container_layout.setSpacing(12)
        recent_layout.addWidget(self._recent_container)
        self._recent_empty = QLabel("Aucun téléchargement pour le moment.")
        self._recent_empty.setObjectName("mutedText")
        recent_layout.addWidget(self._recent_empty)
        root.addWidget(recent_card)

        root.addStretch(1)

        self.refresh()

    def refresh(self) -> None:
        # Re-pioche la salutation à chaque visite pour qu'elle change
        # dans la journée (matin -> après-midi -> soir) et varie le
        # sous-titre au fil des allers-retours.
        title, subtitle = build_greeting()
        self._greeting_title.setText(title)
        self._greeting_subtitle.setText(subtitle)

        entries = self.history.load()
        stats = compute_stats(entries)
        self._stat_values["today"].setText(str(stats["today"]))
        self._stat_values["week"].setText(str(stats["week"]))
        self._stat_values["total"].setText(str(stats["total"]))
        self._stat_values["success_rate"].setText(f"{stats['success_rate']}%")

        # Wipe the recent list before re-rendering to avoid stacking widgets.
        while self._recent_container_layout.count():
            item = self._recent_container_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        recent = entries[:5]
        self._recent_empty.setVisible(not recent)
        for entry in recent:
            self._recent_container_layout.addWidget(self._recent_row(entry))

    @staticmethod
    def _recent_row(entry: dict[str, Any]) -> QWidget:
        row = QFrame()
        row.setObjectName("recentRow")
        layout = QHBoxLayout(row)
        # Padding généreux : la carte doit respirer plutôt que compresser.
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(14)
        title = QLabel(str(entry.get("title", "")) or "(sans titre)")
        title.setObjectName("recentTitle")
        title.setWordWrap(False)
        title.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        meta = QLabel(format_timestamp(str(entry.get("finished_at", ""))))
        meta.setObjectName("mutedText")
        layout.addWidget(title, 1)
        layout.addWidget(meta)
        return row
