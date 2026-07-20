import json
from pathlib import Path

from app.parsers.metadata_parser import parse_metadata


def test_video_fixture():
    payload = Path("tests/fixtures/video.json").read_text(encoding="utf-8")
    media = parse_metadata(payload, "https://example.com/watch/abc")
    assert media.title == "Example video" and media.best_height == 1080 and "fr" in media.subtitles

def test_playlist():
    media = parse_metadata(json.dumps({"id":"p", "title":"List", "entries":[{"id":"a", "title":"A"}, {"id":"b", "title":"B"}]}), "https://example.com/list")
    assert media.is_playlist and media.playlist_count == 2
