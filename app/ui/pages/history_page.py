from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.models.download_job import DownloadStatus
from app.services.disk_service import DiskService
from app.services.history_service import HistoryService
from app.ui.widgets import MODE_LABELS, STATUS_LABELS, NoWheelComboBox, format_timestamp, page_header


class HistoryPage(QWidget):
    redownload_requested = Signal(object)  # the history entry dict
    play_requested = Signal(str)  # local file path
    entry_details_requested = Signal(object)  # l’entrée d’historique

    def __init__(self, service: HistoryService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self._entries: list[dict[str, Any]] = []
        self._rendered: list[dict[str, Any]] = []

        header = page_header(
            "Historique",
            "Retrouvez les téléchargements terminés, annulés ou en erreur.",
            eyebrow="Journal",
        )

        self.search = QLineEdit()
        self.search.setPlaceholderText("Rechercher par titre…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._render)
        self.status_filter = NoWheelComboBox()
        self.status_filter.addItem("Tous les statuts", "")
        self.status_filter.addItem("Terminés", "completed")
        self.status_filter.addItem("Échecs", "failed")
        self.status_filter.addItem("Annulés", "cancelled")
        self.status_filter.currentIndexChanged.connect(self._render)
        self.type_filter = NoWheelComboBox()
        self.type_filter.addItem("Tous les types", "")
        self.type_filter.addItem("Vidéo", "video")
        self.type_filter.addItem("Audio", "audio")
        self.type_filter.currentIndexChanged.connect(self._render)
        self.count = QLabel()
        self.count.setObjectName("mutedText")
        search_row = QHBoxLayout()
        search_row.addWidget(self.search, 1)
        search_row.addWidget(self.status_filter)
        search_row.addWidget(self.type_filter)
        search_row.addWidget(self.count)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Titre", "Type", "Qualité", "Format", "Statut", "Date"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setHighlightSections(False)
        for column in (1, 2, 3, 5):
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(4, 220)
        self.table.doubleClicked.connect(self.open_folder)
        self.table.itemSelectionChanged.connect(self._update_buttons)

        self.play_button = QPushButton("Lire")
        self.play_button.clicked.connect(self._play)
        self.redownload_button = QPushButton("Re-télécharger")
        self.redownload_button.setObjectName("primaryButton")
        self.redownload_button.clicked.connect(self._redownload)
        self.details_button = QPushButton("Détails")
        self.details_button.clicked.connect(self._details)
        open_button = QPushButton("Ouvrir le dossier")
        delete_button = QPushButton("Supprimer")
        delete_button.clicked.connect(lambda: self.delete_entry())
        clear_button = QPushButton("Vider l’historique")
        clear_button.setObjectName("dangerButton")
        open_button.clicked.connect(self.open_folder)
        clear_button.clicked.connect(self.clear)

        actions = QHBoxLayout()
        actions.addStretch()
        actions.addWidget(self.details_button)
        actions.addWidget(self.play_button)
        actions.addWidget(self.redownload_button)
        actions.addWidget(open_button)
        actions.addWidget(delete_button)
        actions.addWidget(clear_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 30, 36, 30)
        layout.setSpacing(14)
        layout.addWidget(header)
        layout.addLayout(search_row)
        layout.addWidget(self.table, 1)
        layout.addLayout(actions)
        self.refresh()

    def refresh(self) -> None:
        self._entries = self.service.load()
        self._render()

    def _filtered(self) -> list[dict[str, Any]]:
        query = self.search.text().strip().lower()
        status = self.status_filter.currentData()
        mode = self.type_filter.currentData()
        entries = self._entries
        if query:
            entries = [entry for entry in entries if query in str(entry.get("title", "")).lower()]
        if status:
            entries = [entry for entry in entries if str(entry.get("status", "")) == status]
        if mode:
            entries = [entry for entry in entries if str(entry.get("mode", "")) == mode]
        return list(entries)

    def _render(self) -> None:
        self._rendered = self._filtered()
        total = len(self._entries)
        shown = len(self._rendered)
        if shown == total:
            self.count.setText(f"{total} élément{'s' if total != 1 else ''}")
        else:
            self.count.setText(f"{shown} sur {total}")
        self.table.setRowCount(shown)
        for row, entry in enumerate(self._rendered):
            values = (
                str(entry.get("title", "")),
                MODE_LABELS.get(str(entry.get("mode", "")), str(entry.get("mode", ""))),
                str(entry.get("quality", "")),
                str(entry.get("output_format", "")).upper(),
                self._status_text(entry),
                format_timestamp(str(entry.get("finished_at", ""))),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                alignment = Qt.AlignmentFlag.AlignLeft if column == 0 else Qt.AlignmentFlag.AlignCenter
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | alignment)
                if column == 4:
                    item.setToolTip(self._status_tooltip(entry))
                self.table.setItem(row, column, item)
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, entry.get("final_path") or entry.get("destination", ""))
        self._update_buttons()

    @staticmethod
    def _status_text(entry: dict[str, Any]) -> str:
        """« Échec — <motif> ». La colonne est bornée en pixels (voir __init__) : Qt
        ellipse tout seul si besoin, donc le motif n’est pas tronqué ici."""
        raw = str(entry.get("status", ""))
        label = STATUS_LABELS.get(raw, raw)
        reason = str(entry.get("error", "")).strip()
        if raw != DownloadStatus.FAILED or not reason:
            return label
        return f"{label} — {reason}"

    @staticmethod
    def _status_tooltip(entry: dict[str, Any]) -> str:
        parts = [str(entry.get("error", "")).strip(), str(entry.get("error_hint", "")).strip()]
        return "\n".join(part for part in parts if part)

    def _details(self) -> None:
        entry = self._current_entry()
        if entry and str(entry.get("error", "")).strip():
            self.entry_details_requested.emit(entry)

    def _update_buttons(self) -> None:
        has_selection = self.table.currentRow() >= 0 and self.table.rowCount() > 0
        self.redownload_button.setEnabled(has_selection)
        self.play_button.setEnabled(has_selection and self._playable_path() is not None)
        entry = self._current_entry()
        self.details_button.setEnabled(bool(entry and str(entry.get("error", "")).strip()))

    def _playable_path(self) -> str | None:
        entry = self._current_entry()
        if not entry:
            return None
        return DiskService.resolve_media_path(str(entry.get("final_path", "")), str(entry.get("destination", "")))

    def _play(self) -> None:
        path = self._playable_path()
        if path:
            self.play_requested.emit(path)

    def _current_entry(self) -> dict[str, Any] | None:
        row = self.table.currentRow()
        if 0 <= row < len(self._rendered):
            return self._rendered[row]
        return None

    def _redownload(self) -> None:
        entry = self._current_entry()
        if entry:
            self.redownload_requested.emit(entry)

    def open_folder(self, *_args) -> None:
        item = self.table.item(self.table.currentRow(), 0) if self.table.currentRow() >= 0 else None
        if item:
            value = Path(item.data(Qt.ItemDataRole.UserRole))
            folder = value if value.is_dir() else value.parent
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def clear(self) -> None:
        if self.table.rowCount() == 0:
            return
        answer = QMessageBox.question(self, "Vider l’historique", "Supprimer tout l’historique local ?")
        if answer == QMessageBox.StandardButton.Yes:
            self.service.clear()
            self.refresh()

    def delete_entry(self, confirm: bool = True) -> None:
        """Supprime l’entrée sélectionnée. `confirm=False` saute la boîte de dialogue (tests)."""
        entry = self._current_entry()
        if not entry:
            return
        if confirm:
            answer = QMessageBox.question(self, "Supprimer l’entrée", "Retirer cette ligne de l’historique ?")
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.service.remove(str(entry.get("id", "")))
        self.refresh()
