from __future__ import annotations

import pytest

from app.models.application_settings import ApplicationSettings
from app.models.media_info import MediaFormat, MediaInfo

pytest.importorskip("pytestqt")


@pytest.fixture
def window(qtbot, monkeypatch):
    from app.ui.main_window import MainWindow

    # Never hit the network for the startup update check during tests.
    monkeypatch.setattr(MainWindow, "_check_updates", lambda self, silent=True: None, raising=False)
    # auto_update_ytdlp est vrai par défaut : sans mock, chaque construction
    # lance BootstrapWorker qui interroge GitHub et télécharge yt-dlp.exe.
    monkeypatch.setattr(MainWindow, "_update_ytdlp", lambda self, *args, **kwargs: None, raising=False)
    win = MainWindow()
    qtbot.addWidget(win)
    return win


@pytest.fixture
def page(qtbot):
    """A standalone DownloadPage (its error signal is not wired to a dialog)."""
    from app.ui.pages import DownloadPage

    widget = DownloadPage(ApplicationSettings())
    qtbot.addWidget(widget)
    return widget


@pytest.fixture
def settings_page(qtbot):
    """Une SettingsPage isolée, sur des réglages neufs en mémoire."""
    from app.ui.pages import SettingsPage

    widget = SettingsPage(ApplicationSettings())
    qtbot.addWidget(widget)
    return widget


def test_window_has_three_pages(window):
    assert window.stack.count() == 3


def test_navigation_updates_stack(window):
    window.sidebar.navigated.emit(2)
    assert window.stack.currentIndex() == 2


def test_audio_mode_switches_formats(page):
    page.mode_audio.setChecked(True)
    formats = [page.format.itemText(i) for i in range(page.format.count())]
    assert formats == ["MP3", "M4A", "FLAC", "WAV", "Opus"]
    page.mode_video.setChecked(True)
    formats = [page.format.itemText(i) for i in range(page.format.count())]
    assert formats == ["MP4", "MKV", "WebM"]


def test_enqueue_without_media_emits_error(page):
    received: list[str] = []
    page.error.connect(received.append)
    page._enqueue(True)
    assert received and "Analysez" in received[0]


def test_set_media_enables_actions(page):
    assert not page.download_button.isEnabled()
    page.set_media(
        MediaInfo(
            media_id="id",
            title="Titre",
            original_url="https://example.com/watch?v=id",
            platform="YouTube",
            formats=[MediaFormat(format_id="137", height=1080)],
        )
    )
    assert page.download_button.isEnabled()
    assert page.queue_button.isEnabled()
    assert page.platform_pill.text() == "YouTube"
    assert page.media_title.text() == "Titre"


def test_download_selectors_ignore_wheel(page):
    from app.ui.widgets import NoWheelComboBox

    for widget in (page.quality, page.format, page.codec, page.bitrate):
        assert isinstance(widget, NoWheelComboBox)


def test_settings_selectors_ignore_wheel(settings_page):
    from app.ui.widgets import NoWheelComboBox, NoWheelSpinBox

    for widget in (settings_page.organize, settings_page.theme):
        assert isinstance(widget, NoWheelComboBox)
    for widget in (settings_page.parallel, settings_page.history_limit):
        assert isinstance(widget, NoWheelSpinBox)


def test_update_channel_row_is_labelled(settings_page):
    from PySide6.QtWidgets import QLabel

    labels = [widget.text() for widget in settings_page.findChildren(QLabel)]
    assert "Canal de mise à jour" in labels


def test_channel_hint_describes_both_channels(settings_page):
    hint = settings_page.channel_hint.text()
    assert "LIVE" in hint and "EVO" in hint


def test_channel_radio_writes_the_setting(settings_page):
    settings_page.evo_radio.setChecked(True)
    assert settings_page.settings.update_channel == "evo"
    settings_page.live_radio.setChecked(True)
    assert settings_page.settings.update_channel == "live"


def test_sources_hint_is_visible_and_links_out(page):
    from app.constants import SUPPORTED_SITES_URL

    text = page.sources_hint.text()
    assert "YouTube" in text
    assert SUPPORTED_SITES_URL in text
    assert page.sources_hint.openExternalLinks()
    assert not page.sources_hint.isHidden()


def test_sources_hint_survives_the_busy_cycle(page):
    """Le spinner change de texte pendant l'analyse ; les sources non."""
    before = page.sources_hint.text()
    page.set_busy(True)
    assert page.spinner.text() == "Analyse en cours…"
    assert page.sources_hint.text() == before
    page.set_busy(False)
    assert page.sources_hint.text() == before


@pytest.fixture
def restore_app_theme():
    """apply_theme mute la QApplication globale (style sheet + palette) ;
    on restaure l'état d'origine pour ne pas polluer les tests suivants.
    """
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    style_sheet = app.styleSheet()
    palette = app.palette()
    yield app
    app.setStyleSheet(style_sheet)
    app.setPalette(palette)


def test_apply_theme_sets_the_link_palette_colour(qtbot, restore_app_theme):
    """Qt ne propage pas les règles QSS aux ancres d'un QLabel enrichi ;
    apply_theme doit donc positionner la couleur via le rôle Link de la
    palette pour que le lien de sources_hint ne s'affiche pas en bleu Qt.
    """
    from PySide6.QtGui import QColor, QPalette

    from app.ui.theme import LINK_COLORS, apply_theme

    app = restore_app_theme
    for theme in ("dark", "light"):
        resolved = apply_theme(app, theme)
        assert app.palette().color(QPalette.ColorRole.Link) == QColor(LINK_COLORS[resolved])


def test_ytdlp_output_reaches_the_log_panel(window):
    """Le panneau Ctrl+L doit montrer la sortie de yt-dlp, pas rester vide."""
    window.manager.job_output.emit("[download] Destination: piste.mp3")

    assert "[download] Destination: piste.mp3" in window.download_page.logs.toPlainText()


def test_ytdlp_output_is_written_to_the_session_log(window, caplog):
    """Sans cette ligne dans le fichier, « Signaler un problème » n'emporte rien."""
    import logging

    with caplog.at_level(logging.INFO):
        window.manager.job_output.emit("ERROR: Video unavailable")

    assert "ERROR: Video unavailable" in caplog.text


def test_logged_ytdlp_output_redacts_url_secrets(window, caplog):
    """Le rapport part sur un ticket public : les URL signées doivent être masquées."""
    import logging

    with caplog.at_level(logging.INFO):
        window.manager.job_output.emit("[download] https://r1.googlevideo.com/videoplayback?expire=1&signature=deadbeef")

    # redact_secrets remplace la valeur par "[REDACTED]" avant que urlencode ne
    # ré-échappe les crochets en %5BREDACTED%5D — les deux formes sont sûres,
    # le mot REDACTED reste lisible pour un humain qui parcourt le rapport.
    assert "deadbeef" not in caplog.text
    assert "REDACTED" in caplog.text


def test_maybe_auto_update_asks_for_silent_ytdlp_update(window, monkeypatch):
    """L'auto-update au démarrage passe silent=True (pas de modale si offline)."""
    calls: list[dict] = []
    monkeypatch.setattr(window, "_update_ytdlp", lambda **kwargs: calls.append(kwargs))
    monkeypatch.setattr(window.binaries, "missing", lambda: [])
    window.settings.auto_update_ytdlp = True

    window._maybe_auto_update()

    assert calls == [{"silent": True}]


def test_silent_ytdlp_failure_does_not_show_a_modal(window, monkeypatch):
    """Une màj échouée au démarrage ne doit pas ouvrir de QMessageBox — juste écrire dans les paramètres."""
    errors: list[str] = []
    monkeypatch.setattr(window, "_error", errors.append)
    window._ytdlp_update_silent = True

    window._ytdlp_updated(False, "Échec réseau : vérifiez votre connexion Internet, puis réessayez.")

    assert errors == []


def test_manual_ytdlp_failure_still_shows_a_modal(window, monkeypatch):
    """Le clic manuel « Mettre à jour yt-dlp » doit toujours signaler l'échec."""
    errors: list[str] = []
    monkeypatch.setattr(window, "_error", errors.append)
    window._ytdlp_update_silent = False

    window._ytdlp_updated(False, "Échec du téléchargement : ...")

    assert errors == ["Échec du téléchargement : ..."]


def test_default_settings_enable_auto_ytdlp_update():
    """Par défaut yt-dlp doit se mettre à jour tout seul, sinon l'utilisateur reste
    coincé sur une version cassée par YouTube tant qu'il n'ouvre pas les paramètres."""
    from app.models.application_settings import ApplicationSettings

    assert ApplicationSettings().auto_update_ytdlp is True


def test_txt_playlist_file_expands_to_its_contained_urls(tmp_path):
    """Un .txt de liens doit être expansé, pas traité comme une URL à télécharger."""
    from app.ui.main_window import _read_url_list_from_txt

    playlist = tmp_path / "liens.txt"
    playlist.write_text(
        "\n".join([
            "https://example.com/a",
            "  ",  # ligne vide après strip
            "# commentaire à ignorer",
            "https://example.com/b",
            "",
            "https://example.com/c",
        ]),
        encoding="utf-8",
    )

    assert _read_url_list_from_txt(playlist) == [
        "https://example.com/a",
        "https://example.com/b",
        "https://example.com/c",
    ]


def test_txt_playlist_missing_file_returns_empty(tmp_path):
    """Un chemin qui n'existe plus ne doit pas faire crasher le drop."""
    from app.ui.main_window import _read_url_list_from_txt

    assert _read_url_list_from_txt(tmp_path / "manquant.txt") == []
