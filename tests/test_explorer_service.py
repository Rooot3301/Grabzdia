from __future__ import annotations

import pytest

from app.services.explorer_service import ExplorerService


@pytest.fixture
def calls(monkeypatch):
    """Remplace les deux effets de bord (sélection native, ouverture de dossier)
    par des enregistreurs : aucun Explorateur ne s'ouvre pendant les tests."""
    recorded: dict[str, list[str]] = {"select": [], "folder": []}

    def fake_select(path):
        recorded["select"].append(str(path))
        return recorded.get("select_ok", True)

    def fake_folder(path):
        recorded["folder"].append(str(path))
        return True

    monkeypatch.setattr(ExplorerService, "_select_file", staticmethod(fake_select))
    monkeypatch.setattr(ExplorerService, "_open_folder", staticmethod(fake_folder))
    return recorded


def test_existing_file_is_selected(tmp_path, calls):
    media = tmp_path / "Ma vidéo, partie 1 [abc123XYZ].mp4"
    media.write_bytes(b"x")

    assert ExplorerService.reveal(str(media), str(tmp_path)) is True
    assert calls["select"] == [str(media)]
    assert calls["folder"] == []


def test_falls_back_to_folder_when_native_selection_fails(tmp_path, calls):
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"x")
    calls["select_ok"] = False

    assert ExplorerService.reveal(str(media), str(tmp_path)) is True
    assert calls["folder"] == [str(tmp_path)]


def test_missing_file_opens_its_folder(tmp_path, calls):
    assert ExplorerService.reveal(str(tmp_path / "supprime.mp4"), "") is True
    assert calls["select"] == []
    assert calls["folder"] == [str(tmp_path)]


def test_renamed_file_is_found_through_destination(tmp_path, calls):
    # final_path pointe ailleurs (ancien chemin corrompu) : on retrouve le
    # fichier dans la destination via le jeton d'id yt-dlp, comme pour « Lire ».
    media = tmp_path / "Titre nettoyé [nWm_OhIKms8].mp4"
    media.write_bytes(b"x")

    assert ExplorerService.reveal("Z:/introuvable/Titre brut [nWm_OhIKms8].mp4", str(tmp_path)) is True
    assert calls["select"] == [str(media)]


def test_without_final_path_opens_destination(tmp_path, calls):
    assert ExplorerService.reveal("", str(tmp_path)) is True
    assert calls["folder"] == [str(tmp_path)]


def test_final_path_that_is_a_folder_opens_it(tmp_path, calls):
    # Les playlists enregistrent parfois un dossier comme chemin final.
    assert ExplorerService.reveal(str(tmp_path), "") is True
    assert calls["select"] == []
    assert calls["folder"] == [str(tmp_path)]


def test_nothing_on_disk_returns_false(tmp_path, calls):
    assert ExplorerService.reveal(str(tmp_path / "a" / "b.mp4"), str(tmp_path / "absent")) is False
    assert calls == {"select": [], "folder": []}


def test_empty_inputs_return_false(calls):
    assert ExplorerService.reveal("", "") is False


def test_native_selection_is_a_noop_off_windows(monkeypatch, tmp_path):
    monkeypatch.setattr("app.services.explorer_service.sys.platform", "linux")
    media = tmp_path / "clip.mp4"
    media.write_bytes(b"x")
    assert ExplorerService._select_file(media) is False


# ---- branchement des boutons « Ouvrir le dossier » ---------------------------


@pytest.fixture
def reveals(monkeypatch):
    seen: list[tuple[str, str]] = []

    def fake_reveal(final_path, destination=""):
        seen.append((final_path, destination))
        return True

    monkeypatch.setattr(ExplorerService, "reveal", staticmethod(fake_reveal))
    return seen


def test_download_card_button_reveals_the_finished_file(window, reveals):
    from app.models.download_job import DownloadJob, DownloadStatus

    job = DownloadJob(url="https://example.com/v", title="v", mode="video", quality="best",
                      output_format="mp4", destination="D:/Vidéos", filename_template="%(title)s.%(ext)s")
    job.status = DownloadStatus.COMPLETED
    job.final_path = "D:/Vidéos/v.mp4"
    window.manager.jobs.append(job)

    window._open_target(job.id)

    assert reveals == [("D:/Vidéos/v.mp4", "D:/Vidéos")]


def test_dashboard_menu_reveals_the_history_file(window, reveals):
    window._open_history_folder({"final_path": "D:/a/clip.mp3", "destination": "D:/a"})
    assert reveals == [("D:/a/clip.mp3", "D:/a")]


def test_history_page_button_reveals_the_selected_entry(qtbot, monkeypatch, reveals):
    from app.services.history_service import HistoryService
    from app.ui.pages.history_page import HistoryPage

    entry = {"id": "1", "title": "Une vidéo", "mode": "video", "quality": "1080p", "output_format": "mp4",
             "status": "completed", "finished_at": "2026-07-27T09:15:32+00:00",
             "destination": "D:/b", "final_path": "D:/b/x.mp4", "error": "", "error_hint": "", "error_output": ""}
    monkeypatch.setattr(HistoryService, "load", lambda self: [entry])
    page = HistoryPage(HistoryService())
    qtbot.addWidget(page)
    page.table.setCurrentCell(0, 0)

    page.open_folder()

    assert reveals == [("D:/b/x.mp4", "D:/b")]
