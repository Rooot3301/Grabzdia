from __future__ import annotations

import contextlib
import os
import random
from datetime import UTC, datetime, timedelta
from typing import Any

from PySide6.QtCore import QRectF, QSize, Qt, QUrl, Signal
from PySide6.QtGui import QAction, QPainter, QPainterPath, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
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

from app.models.application_settings import ApplicationSettings
from app.models.download_job import DownloadStatus
from app.services.history_service import HistoryService
from app.ui.widgets import MODE_LABELS, STATUS_LABELS, CircleGauge, eyebrow_label, format_timestamp, load_icon
from app.utils.url_host import infer_thumbnail_url, source_label

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


# Salutations par créneau — mix de tonalités : classique, familier, taquin,
# rassurant. Le placeholder {name} est remplacé quand un nom est disponible,
# sinon la phrase est utilisée telle quelle (les templates sans placeholder
# marchent dans les deux cas).
_TITLES = {
    "morning": [
        "Bonjour {name}", "Salut {name}", "Bien dormi, {name}",
        "Hello {name}", "Coucou {name}", "Prêt {name} ?",
        "Debout {name}", "Bonjour", "Salut", "Bien réveillé ?",
        "Yo {name}", "Un café, {name} ?", "Content de te revoir, {name}",
    ],
    "afternoon": [
        "Bon après-midi {name}", "Rebonjour {name}", "Salut {name}",
        "Hello {name}", "Yo {name}", "Content de te revoir, {name}",
        "Toujours là, {name} ?", "Bon après-midi", "Salut",
        "Ça bosse dur, {name} ?", "On continue, {name}",
    ],
    "evening": [
        "Bonsoir {name}", "Salut {name}", "Hello {name}",
        "Bienvenue {name}", "Content de te revoir, {name}",
        "Bonsoir", "Salut", "Hey {name}", "On se détend, {name} ?",
        "La soirée commence, {name}", "Yo {name}",
    ],
    "night": [
        "Bonne nuit {name}", "Toujours debout, {name} ?",
        "Insomnie, {name} ?", "Hey {name}, tard ce soir",
        "La nuit, ce silence propice", "Bonne nuit",
        "Silencieux comme toi, {name}", "Yo {name}, respect pour l'heure",
    ],
}

_SUBTITLES = {
    "morning": [
        "On télécharge quoi aujourd'hui ?",
        "Prêt à démarrer la journée ?",
        "Un lien à récupérer avant le café ?",
        "La file t'attend, calme et prête.",
        "De quoi occuper la matinée ?",
        "Une idée en tête pour aujourd'hui ?",
        "Que veux-tu capturer ce matin ?",
    ],
    "afternoon": [
        "On continue sur quoi ?",
        "Une pause média ?",
        "Qu'est-ce qu'on ajoute à la file ?",
        "L'après-midi est propice au binge, non ?",
        "Une petite envie de découverte ?",
        "Que veux-tu attraper avant ce soir ?",
        "La suite de la matinée ?",
    ],
    "evening": [
        "On écoute quoi ce soir ?",
        "Un dernier téléchargement avant de couper ?",
        "Prêt pour la playlist du soir ?",
        "L'ambiance du soir se prépare.",
        "Une trouvaille à sauvegarder ?",
        "Le canapé, un thé, et un bon fichier ?",
        "Que veux-tu emporter pour la soirée ?",
    ],
    "night": [
        "Encore debout ? Un dernier lien ?",
        "Silencieux et efficace, comme d'habitude.",
        "La file tourne pendant que tu dors.",
        "Le calme de la nuit pour bosser.",
        "Un dernier téléchargement avant de dormir ?",
        "Personne pour te déranger à cette heure.",
        "La nuit porte conseil, et bande passante.",
    ],
}


def _display_name() -> str:
    """Nom par défaut inféré depuis Windows/POSIX, filtre les identifiants
    génériques (user, root, admin, vide). Retourne '' si rien d'utilisable."""
    raw = (os.environ.get("USERNAME") or os.environ.get("USER") or "").strip()
    if not raw or raw.lower() in {"user", "root", "administrator", "admin"}:
        return ""
    return raw.split()[0].capitalize()


def build_greeting(now: datetime | None = None, name: str | None = None,
                    random_source: random.Random | None = None) -> tuple[str, str]:
    """Retourne (titre, sous-titre) selon l'heure et le nom fourni.

    `name=None` → auto-détection env (Windows/POSIX). `name=""` explicite →
    on force l'absence de nom (permet à un utilisateur qui a « skip »
    l'onboarding de ne jamais voir son login système apparaître).

    Chaque tirage produit un titre parmi ~10-13 templates par créneau,
    dont certains incluent {name} et d'autres pas — quand le nom est vide,
    les templates avec {name} sont écartés (fallback sur les autres).
    """
    reference = (now or datetime.now(UTC)).astimezone()
    slot = _time_slot(reference)
    who = _display_name() if name is None else name
    picker = random_source or random.Random()

    candidates = _TITLES[slot]
    if not who:
        candidates = [t for t in candidates if "{name}" not in t]
    title = picker.choice(candidates).format(name=who).strip()
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

    def __init__(self, history: HistoryService, settings: ApplicationSettings,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.history = history
        self.settings = settings
        # Cache local des miniatures téléchargées pendant la session.
        # Une entrée = un pixmap prêt à peindre, indexé par URL. On ne
        # persiste pas sur disque : les 5 miniatures visibles pèsent peu
        # et sont re-fetchées au lancement suivant (miniatures YouTube
        # servies par ytimg.com, très rapides).
        self._thumb_cache: dict[str, QPixmap] = {}
        self._thumb_manager = QNetworkAccessManager(self)

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
        # Priorité :
        # 1. display_name renseigné → on l'utilise.
        # 2. Onboarding déjà passé (l'utilisateur a vu la modale et a sciemment
        #    laissé le champ vide, ou cliqué « Plus tard ») → PAS de nom du
        #    tout, on ne veut pas ré-injecter l'USERNAME du PC.
        # 3. Onboarding pas encore fait → fallback détection env (accueil
        #    déjà personnalisé au tout premier lancement, avant l'écran).
        stored = self.settings.display_name.strip()
        if stored:
            name = stored
        elif self.settings.onboarding_completed:
            name = ""  # explicit skip → aucune personnalisation
        else:
            name = None  # pre-onboarding → build_greeting va sonder l'env
        title, subtitle = build_greeting(name=name)
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
        thumb.setFixedSize(72, 48)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb.setScaledContents(False)
        # État par défaut : placeholder film (icône), servira si la vidéo
        # n'a pas d'URL de miniature ou si le fetch réseau échoue.
        thumb.setPixmap(load_icon("film.svg").pixmap(24, 24))
        # 1) URL stockée (jobs analysés à partir de v1.2.0-evo.5).
        # 2) Sinon, tentative de reconstruction depuis l'URL de la vidéo
        #    (YouTube : i.ytimg.com/vi/<id>/hqdefault.jpg). Ça couvre les
        #    vieilles entrées d'historique sans ré-appeler yt-dlp.
        thumbnail = str(entry.get("thumbnail_url", "")).strip()
        if not thumbnail:
            thumbnail = infer_thumbnail_url(str(entry.get("url", "")))
        self._start_thumbnail_fetch(thumb, thumbnail)
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

    # ---- thumbnail fetch -----------------------------------------------
    def _start_thumbnail_fetch(self, thumb: QLabel, url: str) -> None:
        """Tente le fetch d'une miniature ; laisse le placeholder si l'URL
        est vide ou d'un schéma non-http(s).

        Cache hit → paint immédiat, aucune requête réseau. Cache miss → GET
        asynchrone, le pixmap est appliqué à la fin. Le widget peut avoir
        été détruit entre-temps (refresh() de la liste), auquel cas on
        ignore silencieusement."""
        clean = url.strip()
        if not clean:
            return
        if clean in self._thumb_cache:
            self._apply_thumbnail_pixmap(thumb, self._thumb_cache[clean])
            return
        parsed = QUrl(clean)
        if parsed.scheme().lower() not in ("http", "https"):
            return
        reply = self._thumb_manager.get(QNetworkRequest(parsed))
        reply.finished.connect(lambda r=reply, t=thumb, u=clean: self._on_thumbnail_ready(r, t, u))

    def _on_thumbnail_ready(self, reply: QNetworkReply, thumb: QLabel, url: str) -> None:
        pixmap = QPixmap()
        loaded = pixmap.loadFromData(reply.readAll())
        reply.deleteLater()
        if not loaded or pixmap.isNull():
            return
        self._thumb_cache[url] = pixmap
        # Si la liste a été rebâtie entre le GET et la réponse, le QLabel a
        # été détruit côté C++ (via deleteLater dans le refresh précédent)
        # et l'accès à setPixmap lève RuntimeError sur le wrapper Python —
        # c'est attendu, on abandonne la miniature en silence.
        with contextlib.suppress(RuntimeError):
            self._apply_thumbnail_pixmap(thumb, pixmap)

    @staticmethod
    def _apply_thumbnail_pixmap(thumb: QLabel, pixmap: QPixmap) -> None:
        """Peint la miniature en couvrant le cadre 72×48, coins arrondis
        clippés à la main (QSS border-radius sur QLabel ne masque pas
        le pixmap sous Qt6)."""
        target = QPixmap(72, 48)
        target.fill(Qt.GlobalColor.transparent)
        painter = QPainter(target)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, 72, 48), 6, 6)
        painter.setClipPath(path)
        scaled = pixmap.scaled(
            72, 48,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        # Centrage : si l'image est plus large que 72 après scale, on décale.
        x = (72 - scaled.width()) // 2
        y = (48 - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)
        painter.end()
        thumb.setPixmap(target)

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
