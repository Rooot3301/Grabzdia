from __future__ import annotations

from app.models.download_job import DownloadJob
from app.utils.atomic_json import read_json, write_json_atomic
from app.utils.paths import queue_path


class QueueService:
    """Persists the pending download queue so it survives a restart."""

    def load(self) -> list[dict]:
        value = read_json(queue_path(), [])
        return value if isinstance(value, list) else []

    def save(self, jobs: list[DownloadJob]) -> None:
        write_json_atomic(queue_path(), [job.to_dict() for job in jobs])

    def clear(self) -> None:
        write_json_atomic(queue_path(), [])
