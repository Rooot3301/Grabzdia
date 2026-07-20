from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4


class DownloadStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class DownloadJob:
    url: str
    title: str
    mode: str
    quality: str
    output_format: str
    destination: str
    filename_template: str
    id: str = field(default_factory=lambda: str(uuid4()))
    status: DownloadStatus = DownloadStatus.QUEUED
    progress: float = 0.0
    speed: str = ""
    eta: str = ""
    downloaded: str = ""
    total: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    finished_at: str = ""
    error: str = ""
    final_path: str = ""
    video_codec: str = "auto"
    audio_bitrate: str = "320"
    subtitles: bool = False
    auto_subtitles: bool = False
    embed_subtitles: bool = False
    embed_thumbnail: bool = True
    embed_metadata: bool = True
    playlist: bool = False
    keep_temporary: bool = False
    use_archive: bool = False

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> DownloadJob:
        allowed = cls.__dataclass_fields__.keys()
        kwargs = {key: data[key] for key in allowed if key in data}
        if "status" in kwargs and not isinstance(kwargs["status"], DownloadStatus):
            kwargs["status"] = DownloadStatus(str(kwargs["status"]))
        return cls(**kwargs)
