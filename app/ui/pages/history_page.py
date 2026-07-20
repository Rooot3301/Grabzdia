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

from app.services.history_service import HistoryService
from app.ui.widgets import page_header


class HistoryPage(QWidget):
    redownload_requested = Signal(object)  # the history entry dict

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
        self.count = QLabel()
        self.count.setObjectName("mutedText")
        search_row = QHBoxLayout()
        search_row.addWidget(self.search, 1)
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
        for column in range(1, 6):
            self.table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.table.doubleClicked.connect(self.open_folder)
        self.table.itemSelectionChanged.connect(self._update_buttons)

        self.redownload_button = QPushButton("Re-télécharger")
        self.redownload_button.setObjectName("primaryButton")
        self.redownload_button.clicked.connect(self._redownload)
        open_button = QPushButton("Ouvrir le dossier")
        clear_button = QPushButton("Vider l’historique")
        clear_button.setObjectName("dangerButton")
        open_button.clicked.connect(self.open_folder)
        clear_button.clicked.connect(self.clear)

        actions = QHBoxLayout()
        actions.addStretch()
        actions.addWidget(self.redownload_button)
        actions.addWidget(open_button)
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
        if not query:
            return list(self._entries)
        return [entry for entry in self._entries if query in str(entry.get("title", "")).lower()]

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
            for column, key in enumerate(("title", "mode", "quality", "output_format", "status", "finished_at")):
                item = QTableWidgetItem(str(entry.get(key, "")))
                alignment = Qt.AlignmentFlag.AlignLeft if column == 0 else Qt.AlignmentFlag.AlignCenter
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | alignment)
                self.table.setItem(row, column, item)
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, entry.get("final_path") or entry.get("destination", ""))
        self._update_buttons()

    def _update_buttons(self) -> None:
        has_selection = self.table.currentRow() >= 0 and self.table.rowCount() > 0
        self.redownload_button.setEnabled(has_selection)

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
