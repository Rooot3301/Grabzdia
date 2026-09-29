from __future__ import annotations

import pytest

from app.utils.url_host import source_label


@pytest.mark.parametrize("url,expected", [
    ("https://www.youtube.com/watch?v=abc", "YouTube"),
    ("https://youtu.be/abc", "YouTube"),
    ("https://m.youtube.com/watch?v=abc", "YouTube"),
    ("https://www.twitch.tv/foo", "Twitch"),
    ("https://vimeo.com/12345", "Vimeo"),
    ("https://www.tiktok.com/@user/video/1", "TikTok"),
    ("https://fr.tiktok.com/@user/video/1", "TikTok"),
    ("https://x.com/user/status/1", "X"),
    ("https://twitter.com/user/status/1", "X"),
    ("https://soundcloud.com/artist/song", "SoundCloud"),
])
def test_source_label_recognises_known_platforms(url: str, expected: str) -> None:
    assert source_label(url) == expected


def test_source_label_falls_back_to_capitalised_domain() -> None:
    """Un hôte non listé retombe sur le domaine principal capitalisé."""
    assert source_label("https://www.example.com/video") == "Example"


def test_source_label_empty_for_invalid_input() -> None:
    assert source_label("") == ""
    assert source_label("pas-une-url") == ""
