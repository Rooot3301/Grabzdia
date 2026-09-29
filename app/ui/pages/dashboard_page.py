from __future__ import annotations

import os
import random
from datetime import UTC, datetime, timedelta
from typing import Any

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.models.download_job import DownloadStatus
from app.services.history_service import HistoryService
from app.ui.widgets import MODE_LABELS, STATUS_LABELS, CircleGauge, eyebrow_label, format_timestamp, load_icon
from app.utils.url_host import source_label


# ---------- Salutation dynamique (dépendance : heure + username) --------------

def _time_slot(now: datetime) -> str:
    hour = now.hour
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 18:
        return "afternoon"
    if 18 <= hour < 23:
        return "evening"
    return "night"


_GREETINGS = {"morning": "Bonjour", "afternoon": "Bon après-midi",
              "evening": "Bonsoir", "night": "Bonne nuit"}

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
    raw = (os.environ.get("USERNAME") or os.environ.get("USER") or "").strip()
    if not raw or raw.lower() in {"user", "root", "administrator", "admin"}:
        return ""
    return raw.split()[0].capitalize()


def build_greeting(now: datetime | None = None, name: str | None = None,
                    random_source: random.Random | None = None) -> tuple[str, str]:
    reference = (now or datetime.now(UTC)).astimezone()
    slot = _time_slot(reference)
    who = name if name is not None else _display_name()
    title = f"{_GREETINGS[slot]}, {who}" if who else _GREETINGS[slot]
    picker = random_source or random.Random()
    subtitle = picker.choice(_SUBTITLES[slot])
    return title, subtitle


# ---------- KPI (dépendance : historique brut) --------------------------------

def compute_stats(entries: list[dict[str, Any]], now: datetime | None = None) -> dict[str, Any]:
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


def _pluralize(count: int, singular: str) -> str:
    return singular if count <= 1 else singular + "s"


# ---------- Page --------------------------------------------------------------

class DashboardPage(QWidget):
    """Accueil : salutation, KPI, actions rapides, derniers téléchargements.

    Refonte v1.2.0-evo.5 : header 2 colonnes avec CTA gradient, cartes de
    stats avec icône et sous-titre pluralisé, jauge circulaire pour le taux
    de succès, liste des dernières entrées avec placeholder miniature,
    badge de statut coloré, kebab menu.
    """

    navigate_download = Signal()
    navigate_history = Signal()
    navigate_settings = Signal()
    # Kebab menu → remonte à MainWindow qui a déjà les handlers.
    redownload_requested = Signal(object)
    delete_entry_requested = Signal(str)
    open_folder_requested = Signal(object)
    copy_url_requested = Signal(str)

    def __init__(self, history: HistoryService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.history = history

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(20)

        root.addWidget(self._build_header())
        root.addLayout(self._build_stats_grid())
        root.addWidget(self._build_recent_card(), 1)

        self.refresh()

    # ---- header --------------------------------------------------------
    def _build_header(self) -> QWidget:
        header = QWidget()
        row = QHBoxLayout(header)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(16)

        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(4)
        left.addWidget(eyebrow_label("Accueil"))
        self._greeting_title = QLabel()
        self._greeting_title.setObjectName("pageTitle")
        left.addWidget(self._greeting_title)
        self._greeting_subtitle = QLabel()
        self._greeting_subtitle.setObjectName("pageSubtitle")
        self._greeting_subtitle.setWordWrap(True)
        left.addWidget(self._greeting_subtitle)
        row.addLayout(left, 1)

        self.cta = QPushButton("  Nouveau téléchargement")
        self.cta.setObjectName("ctaButton")
        self.cta.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cta.setIcon(load_icon("plus.svg"))
        self.cta.setIconSize(QSize(18, 18))
        self.cta.setMinimumHeight(46)
        self.cta.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.cta.clicked.connect(self.navigate_download)
        cta_wrap = QVBoxLayout()
        cta_wrap.addWidget(self.cta)
        cta_wrap.addStretch()
        row.addLayout(cta_wrap)
        return header

    # ---- stats ---------------------------------------------------------
    def _build_stats_grid(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(14)
        # (key, label, icon, unit-singular)
        keys = [
            ("today", "Aujourd'hui", "calendar.svg", "téléchargement"),
            ("week", "Cette semaine", "clipboard.svg", "téléchargement"),
            ("total", "Total", "database.svg", "téléchargement"),
        ]
        self._stat_values: dict[str, QLabel] = {}
        self._stat_units: dict[str, QLabel] = {}
        for index, (key, label, icon_name, unit) in enumerate(keys):
            card = self._stat_card(label, icon_name)
            self._stat_values[key] = card.findChild(QLabel, "statValue")
            self._stat_units[key] = card.findChild(QLabel, "statUnit")
            self._stat_units[key].setText(unit)
            grid.addWidget(card, 0, index)
        grid.addWidget(self._build_success_card(), 0, 3)
        for i in range(4):
            grid.setColumnStretch(i, 1)
        return grid

    def _stat_card(self, label: str, icon_name: str) -> QFrame:
        card = QFrame()
        card.setObjectName("statCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(6)

        # Ligne « icône + eyebrow » alignée en haut.
        head = QHBoxLayout()
        head.setSpacing(10)
        icon_box = QLabel()
        icon_box.setObjectName("statIcon")
        icon_box.setFixedSize(30, 30)
        icon_box.setPixmap(load_icon(icon_name).pixmap(18, 18))
        icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        head.addWidget(icon_box)
        head.addWidget(eyebrow_label(label), 1)
        layout.addLayout(head)

        value = QLabel("—")
        value.setObjectName("statValue")
        layout.addWidget(value)
        unit = QLabel("")
        unit.setObjectName("statUnit")
        layout.addWidget(unit)
        layout.addStretch()
        return card

    def _build_success_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("statCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(6)

        head = QHBoxLayout()
        head.setSpacing(10)
        icon_box = QLabel()
        icon_box.setObjectName("statIcon")
        icon_box.setFixedSize(30, 30)
        icon_box.setPixmap(load_icon("check-circle.svg").pixmap(18, 18))
        icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        head.addWidget(icon_box)
        head.addWidget(eyebrow_label("Taux de réussite"), 1)
        layout.addLayout(head)

        row = QHBoxLayout()
        row.setSpacing(14)
        value_wrap = QVBoxLayout()
        value_wrap.setSpacing(0)
        self._success_value = QLabel("—")
        self._success_value.setObjectName("statValue")
        value_wrap.addWidget(self._success_value)
        hint = QLabel("des téléchargements")
        hint.setObjectName("statUnit")
        value_wrap.addWidget(hint)
        row.addLayout(value_wrap, 1)
        self._success_gauge = CircleGauge()
        row.addWidget(self._success_gauge, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(row)
        layout.addStretch()
        return card

    # ---- recent list ---------------------------------------------------
    def _build_recent_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(24, 22, 24, 24)
        layout.setSpacing(16)

        head = QHBoxLayout()
        head.setSpacing(12)
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title = QLabel("Derniers téléchargements")
        title.setObjectName("sectionTitle")
        title_col.addWidget(title)
        subtitle = QLabel("Vos 5 téléchargements les plus récents.")
        subtitle.setObjectName("mutedText")
        title_col.addWidget(subtitle)
        head.addLayout(title_col, 1)

        see_all = QPushButton("Voir tout")
        see_all.setObjectName("ghostButton")
        see_all.setCursor(Qt.CursorShape.PointingHandCursor)
        see_all.setIcon(load_icon("arrow-right.svg"))
        see_all.setIconSize(QSize(14, 14))
        see_all.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        see_all.clicked.connect(self.navigate_history)
        head.addWidget(see_all)
        layout.addLayout(head)

        self._recent_container = QWidget()
        self._recent_container_layout = QVBoxLayout(self._recent_container)
        self._recent_container_layout.setContentsMargins(0, 0, 0, 0)
        self._recent_container_layout.setSpacing(10)
        layout.addWidget(self._recent_container)

        self._recent_empty = QLabel("Aucun téléchargement pour le moment.")
        self._recent_empty.setObjectName("mutedText")
        layout.addWidget(self._recent_empty)
        layout.addStretch()
        return card

    # ---- refresh -------------------------------------------------------
    def refresh(self) -> None:
        title, subtitle = build_greeting()
        # 👋 glissé dans le titre pour la note humaine (unicode direct, pas
        # d'asset), retiré si le titre est vide (edge case défensif).
        self._greeting_title.setText(f"{title}  👋" if title else "")
        self._greeting_subtitle.setText(subtitle)

        entries = self.history.load()
        stats = compute_stats(entries)
        for key in ("today", "week", "total"):
            self._stat_values[key].setText(str(stats[key]))
            self._stat_units[key].setText(_pluralize(stats[key], "téléchargement"))
        self._success_value.setText(f"{stats['success_rate']}%")
        self._success_gauge.set_value(stats["success_rate"])

        while self._recent_container_layout.count():
            item = self._recent_container_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        recent = entries[:5]
        self._recent_empty.setVisible(not recent)
        for entry in recent:
            self._recent_container_layout.addWidget(self._recent_row(entry))

    # ---- recent row ----------------------------------------------------
    def _recent_row(self, entry: dict[str, Any]) -> QWidget:
        row = QFrame()
        row.setObjectName("recentRow")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(14)

        thumb = QLabel()
        thumb.setObjectName("recentThumb")
        thumb.setFixedSize(60, 40)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb.setPixmap(load_icon("film.svg").pixmap(22, 22))
        layout.addWidget(thumb)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        title = QLabel(str(entry.get("title", "")) or "(sans titre)")
        title.setObjectName("recentTitle")
        title.setWordWrap(False)
        title.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        text_col.addWidget(title)
        meta = QLabel(self._recent_meta(entry))
        meta.setObjectName("mutedText")
        text_col.addWidget(meta)
        layout.addLayout(text_col, 1)

        status_text, state = self._status_pill(entry)
        pill = QLabel(status_text)
        pill.setObjectName("statusPill")
        pill.setProperty("state", state)
        layout.addWidget(pill)

        when = QLabel(format_timestamp(str(entry.get("finished_at", ""))))
        when.setObjectName("mutedText")
        layout.addWidget(when)

        kebab = QToolButton()
        kebab.setObjectName("kebabButton")
        kebab.setIcon(load_icon("more.svg"))
        kebab.setIconSize(QSize(16, 16))
        kebab.setCursor(Qt.CursorShape.PointingHandCursor)
        kebab.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        kebab.setMenu(self._kebab_menu(entry, kebab))
        layout.addWidget(kebab)
        return row

    @staticmethod
    def _recent_meta(entry: dict[str, Any]) -> str:
        parts = []
        source = source_label(str(entry.get("url", "")))
        if source:
            parts.append(source)
        mode = str(entry.get("mode", ""))
        if mode:
            parts.append(MODE_LABELS.get(mode, mode))
        quality = str(entry.get("quality", "")).strip()
        if quality and quality != "auto":
            parts.append(quality)
        fmt = str(entry.get("output_format", "")).strip().upper()
        if fmt:
            parts.append(fmt)
        return " · ".join(parts) if parts else "—"

    @staticmethod
    def _status_pill(entry: dict[str, Any]) -> tuple[str, str]:
        raw = str(entry.get("status", ""))
        try:
            status = DownloadStatus(raw)
        except ValueError:
            return raw or "—", ""
        return STATUS_LABELS[status], status.value

    def _kebab_menu(self, entry: dict[str, Any], parent: QWidget) -> QMenu:
        menu = QMenu(parent)
        url = str(entry.get("url", ""))
        entry_id = str(entry.get("id", ""))

        redownload = QAction("Relancer le téléchargement", menu)
        redownload.setEnabled(bool(url))
        redownload.triggered.connect(lambda _=False, e=entry: self.redownload_requested.emit(e))
        menu.addAction(redownload)

        open_folder = QAction("Ouvrir le dossier", menu)
        open_folder.setEnabled(bool(entry.get("destination") or entry.get("final_path")))
        open_folder.triggered.connect(lambda _=False, e=entry: self.open_folder_requested.emit(e))
        menu.addAction(open_folder)

        copy_url = QAction("Copier l'URL", menu)
        copy_url.setEnabled(bool(url))
        copy_url.triggered.connect(lambda _=False, u=url: self.copy_url_requested.emit(u))
        menu.addAction(copy_url)

        menu.addSeparator()
        delete = QAction("Supprimer de l'historique", menu)
        delete.setEnabled(bool(entry_id))
        delete.triggered.connect(lambda _=False, i=entry_id: self.delete_entry_requested.emit(i))
        menu.addAction(delete)
        return menu
