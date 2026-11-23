from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class MediaFormat:
    format_id: str
    extension: str = ""
    height: int | None = None
    width: int | None = None
    codec: str = ""
    audio_codec: str = ""
    file_size: int | None = None
    fps: float | None = None


@dataclass(slots=True)
class MediaInfo:
    media_id: str
    title: str
    original_url: str
    description: str = ""
    platform: str = ""
    author: str = ""
    thumbnail_url: str = ""
    # URL http(s) de miniature à essayer dans l'ordre : la variante désignée par
    # yt-dlp peut répondre 404 (ex. miniatures localisées YouTube `vi_lc/…`).
    thumbnail_candidates: list[str] = field(default_factory=list)
    duration: float | None = None
    upload_date: str = ""
    view_count: int | None = None
    formats: list[MediaFormat] = field(default_factory=list)
    subtitles: list[str] = field(default_factory=list)
    is_playlist: bool = False
    playlist_count: int | None = None
    estimated_size: int | None = None

    @property
    def best_height(self) -> int | None:
        heights = [item.height for item in self.formats if item.height]
        return max(heights) if heights else None

