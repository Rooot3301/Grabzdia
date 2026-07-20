from __future__ import annotations

import json
from typing import Any

from app.exceptions import MetadataExtractionError
from app.models.media_info import MediaFormat, MediaInfo


def parse_metadata(payload: str, original_url: str) -> MediaInfo:
    try:
        data: dict[str, Any] = json.loads(payload)
    except (json.JSONDecodeError, TypeError) as error:
        raise MetadataExtractionError("La réponse de yt-dlp est invalide.") from error
    entries = data.get("entries")
    is_playlist = isinstance(entries, list)
    source = (next((e for e in entries if e), {}) if is_playlist else data) or {}
    formats = [MediaFormat(
        format_id=str(item.get("format_id", "")), extension=str(item.get("ext", "")),
        height=item.get("height"), width=item.get("width"), codec=str(item.get("vcodec", "")),
        audio_codec=str(item.get("acodec", "")), file_size=item.get("filesize") or item.get("filesize_approx"), fps=item.get("fps")
    ) for item in source.get("formats", [])]
    thumbs = source.get("thumbnails") or []
    thumbnail = source.get("thumbnail") or (thumbs[-1].get("url", "") if thumbs else "")
    return MediaInfo(
        media_id=str(data.get("id") or source.get("id") or ""), title=str(data.get("title") or source.get("title") or "Sans titre"),
        original_url=original_url, description=str(source.get("description") or ""), platform=str(source.get("extractor_key") or source.get("extractor") or ""),
        author=str(source.get("uploader") or source.get("channel") or ""), thumbnail_url=str(thumbnail), duration=source.get("duration"),
        upload_date=str(source.get("upload_date") or ""), view_count=source.get("view_count"), formats=formats,
        subtitles=sorted(set((source.get("subtitles") or {}).keys()) | set((source.get("automatic_captions") or {}).keys())),
        is_playlist=is_playlist, playlist_count=len(entries) if is_playlist else None,
        estimated_size=max((f.file_size or 0 for f in formats), default=0) or None,
    )

