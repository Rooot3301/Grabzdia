from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
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
    def __init__(self, service: HistoryService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service

        header = page_header(
            "Historique",
            "Retrouvez les téléchargements terminés, annulés ou en erreur.",
            eyebrow="Journal",
        )
        self.count = QLabel()
        self.count.setObjectName("mutedText")

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

        open_button = QPushButton("Ouvrir le dossier")
        clear_button = QPushButton("Vider l’historique")
        clear_button.setObjectName("dangerButton")
        open_button.clicked.connect(self.open_folder)
        clear_button.clicked.connect(self.clear)

        row = QHBoxLayout()
        row.addWidget(self.count)
        row.addStretch()
        row.addWidget(open_button)
        row.addWidget(clear_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(36, 30, 36, 30)
        layout.setSpacing(16)
        layout.addWidget(header)
        layout.addLayout(row)
        layout.addWidget(self.table, 1)
        self.refresh()

    def refresh(self) -> None:
        entries = self.service.load()
        self.count.setText(f"{len(entries)} élément{'s' if len(entries) != 1 else ''}")
        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            for column, key in enumerate(("title", "mode", "quality", "output_format", "status", "finished_at")):
                item = QTableWidgetItem(str(entry.get(key, "")))
                alignment = Qt.AlignmentFlag.AlignLeft if column == 0 else Qt.AlignmentFlag.AlignCenter
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | alignment)
                self.table.setItem(row, column, item)
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, entry.get("final_path") or entry.get("destination", ""))

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
