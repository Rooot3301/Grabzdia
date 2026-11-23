"""Miniature de la page Télécharger : URL de repli et pas d'aperçu périmé.

Bug evo.2 : pour https://youtu.be/MM15R4SY0T8, yt-dlp désigne comme miniature
une variante localisée (`vi_lc/…/maxresdefault_en-US.jpg`) qui répond 404 ;
l'aperçu gardait alors l'image de la vidéo analysée juste avant.
"""
from __future__ import annotations

import json

import pytest
from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QColor, QPixmap

from app.models.media_info import MediaInfo
from app.parsers.metadata_parser import parse_metadata

LOCALIZED = "https://i.ytimg.com/vi_lc/MM15R4SY0T8/maxresdefault_en-US.jpg"
WEBP = "https://i.ytimg.com/vi_webp/MM15R4SY0T8/maxresdefault.webp"
JPG = "https://i.ytimg.com/vi/MM15R4SY0T8/maxresdefault.jpg"


# ---- candidats issus des métadonnées -------------------------------------------

def test_candidates_start_with_the_chosen_thumbnail_then_best_preference_first():
    payload = json.dumps({
        "id": "MM15R4SY0T8", "title": "t", "thumbnail": LOCALIZED,
        "thumbnails": [{"url": "https://i.ytimg.com/vi/MM15R4SY0T8/default.jpg"}, {"url": JPG},
                       {"url": LOCALIZED}, {"url": WEBP}],
    })
    media = parse_metadata(payload, "https://youtu.be/MM15R4SY0T8")
    assert media.thumbnail_url == LOCALIZED
    assert media.thumbnail_candidates[:3] == [LOCALIZED, WEBP, JPG]


def test_candidates_skip_non_http_and_are_capped():
    thumbs = [{"url": f"https://example.com/{i}.jpg"} for i in range(20)] + [{"url": "file:///C:/x.jpg"}]
    media = parse_metadata(json.dumps({"id": "a", "title": "t", "thumbnails": thumbs}), "https://example.com/a")
    assert all(url.startswith("https://") for url in media.thumbnail_candidates)
    assert 1 <= len(media.thumbnail_candidates) <= 6


def test_no_thumbnail_gives_no_candidates():
    media = parse_metadata(json.dumps({"id": "a", "title": "t"}), "https://example.com/a")
    assert media.thumbnail_candidates == []


# ---- page : pas d'aperçu périmé --------------------------------------------------

def _pixmap() -> QPixmap:
    pixmap = QPixmap(16, 9)
    pixmap.fill(QColor("red"))
    return pixmap


def test_new_analysis_clears_the_previous_preview(qtbot):
    from app.models.application_settings import ApplicationSettings
    from app.ui.pages import DownloadPage

    page = DownloadPage(ApplicationSettings())
    qtbot.addWidget(page)
    page.set_media(MediaInfo(media_id="a", title="A", original_url="https://example.com/a"))
    page.set_thumbnail(_pixmap())
    page.set_media(MediaInfo(media_id="b", title="B", original_url="https://example.com/b"))
    assert page.thumbnail.pixmap().isNull()
    assert page.thumbnail.text() == "Aperçu"


# ---- fenêtre : repli et réponses obsolètes --------------------------------------

def _png_bytes() -> bytes:
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    _pixmap().save(buffer, "PNG")
    return bytes(data)


class FakeReply:
    def __init__(self, data: bytes) -> None:
        self.data = data

    def readAll(self) -> bytes:  # noqa: N802 (API Qt)
        return self.data

    def deleteLater(self) -> None:  # noqa: N802 (API Qt)
        pass


@pytest.fixture
def requests(window, monkeypatch):
    """Intercepte les requêtes de miniature : (url, callback) par appel."""
    calls: list = []
    monkeypatch.setattr(window, "_request_thumbnail", lambda url, on_done: calls.append((url, on_done)))
    shown: list = []
    monkeypatch.setattr(window.download_page, "set_thumbnail", shown.append)
    return calls, shown


def _media(media_id: str, *urls: str) -> MediaInfo:
    return MediaInfo(media_id=media_id, title=media_id, original_url=f"https://example.com/{media_id}",
                     thumbnail_url=urls[0] if urls else "", thumbnail_candidates=list(urls))


def test_failed_thumbnail_falls_back_to_the_next_candidate(window, requests):
    calls, shown = requests
    media = _media("v", LOCALIZED, WEBP, JPG)
    window._metadata_ready(media)
    assert [url for url, _ in calls] == [LOCALIZED]
    calls[0][1](FakeReply(b"<html>404</html>"))
    assert [url for url, _ in calls] == [LOCALIZED, WEBP]
    calls[1][1](FakeReply(_png_bytes()))
    assert len(shown) == 1
    # L'URL qui marche est retenue : l'historique et l'Accueil en profiteront.
    assert media.thumbnail_url == WEBP


def test_stale_reply_from_a_previous_analysis_is_ignored(window, requests):
    calls, shown = requests
    window._metadata_ready(_media("first", "https://example.com/first.jpg"))
    window._metadata_ready(_media("second", "https://example.com/second.jpg"))
    first_callback = calls[0][1]
    first_callback(FakeReply(_png_bytes()))  # arrive après la seconde analyse
    assert shown == []
    calls[1][1](FakeReply(_png_bytes()))
    assert len(shown) == 1


def test_all_candidates_failing_leaves_the_placeholder(window, requests):
    calls, shown = requests
    media = _media("v", LOCALIZED, JPG)
    window._metadata_ready(media)
    calls[0][1](FakeReply(b""))
    calls[1][1](FakeReply(b""))
    assert len(calls) == 2 and shown == []
