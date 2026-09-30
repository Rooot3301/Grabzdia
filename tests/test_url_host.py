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


# ---- infer_thumbnail_url : reconstruction pour historique migré ----------

@pytest.mark.parametrize("url", [
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "https://youtu.be/dQw4w9WgXcQ",
    "https://m.youtube.com/watch?v=dQw4w9WgXcQ&t=42s",
    "https://www.youtube.com/shorts/dQw4w9WgXcQ",
    "https://www.youtube.com/embed/dQw4w9WgXcQ",
])
def test_infer_thumbnail_url_covers_common_youtube_forms(url: str) -> None:
    from app.utils.url_host import infer_thumbnail_url
    assert infer_thumbnail_url(url) == "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg"


def test_infer_thumbnail_url_rejects_malformed_id() -> None:
    """Un ID qui ne fait pas 11 caractères base64 URL-safe est refusé."""
    from app.utils.url_host import infer_thumbnail_url
    assert infer_thumbnail_url("https://youtu.be/tropcourt") == ""
    assert infer_thumbnail_url("https://youtu.be/beaucoup_trop_long_pour_youtube") == ""


def test_infer_thumbnail_url_empty_for_other_platforms() -> None:
    from app.utils.url_host import infer_thumbnail_url
    assert infer_thumbnail_url("https://vimeo.com/12345") == ""
    assert infer_thumbnail_url("https://twitch.tv/foo") == ""
    assert infer_thumbnail_url("") == ""
