from __future__ import annotations

from typing import Any

from app.utils.atomic_json import read_json, write_json_atomic
from app.utils.paths import history_path


class HistoryService:
    def load(self) -> list[dict[str, Any]]:
        value = read_json(history_path(), [])
        return value if isinstance(value, list) else []

    def add(self, entry: dict[str, Any], limit: int = 500) -> None:
        entries = self.load()
        entries.insert(0, entry)
        write_json_atomic(history_path(), entries[:limit])

    def remove(self, job_id: str) -> None:
        write_json_atomic(history_path(), [e for e in self.load() if e.get("id") != job_id])

    def clear(self) -> None:
        write_json_atomic(history_path(), [])
