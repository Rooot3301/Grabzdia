import os
import tempfile

import pytest

# Qt must run headless during tests. Set before any Qt import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Sandbox all app data: tests construct real services/MainWindow, which would
# otherwise read and WRITE the user's real %APPDATA%/%LOCALAPPDATA% (settings,
# history, queue, logs). Redirect them to a throwaway directory.
_sandbox = tempfile.mkdtemp(prefix="grabzdia-tests-")
os.environ["APPDATA"] = _sandbox
os.environ["LOCALAPPDATA"] = _sandbox

# QSystemTrayIcon on Windows 11 backs its toasts with WinRT ToastNotificationManager,
# which pre-spawns msedgewebview2.exe workers when the tray icon is shown. When
# pytest exits, those workers get re-parented and survive: a handful of runs of
# the `window` fixture pile up 2+ GB of orphaned WebView2 hosts and saturate the
# machine. Reporting "no tray" makes NotificationService skip the icon entirely.
# Set before any test module imports MainWindow (which imports NotificationService).
from PySide6.QtWidgets import QSystemTrayIcon  # noqa: E402

QSystemTrayIcon.isSystemTrayAvailable = staticmethod(lambda: False)


@pytest.fixture
def window(qtbot, monkeypatch):
    """Shared MainWindow fixture — moved out of test_main_window so it's usable
    from any test file (test_dashboard_page.py depends on it)."""
    from app.ui.main_window import MainWindow

    # Never hit the network for the startup update check during tests.
    monkeypatch.setattr(MainWindow, "_check_updates", lambda self, silent=True: None, raising=False)
    # auto_update_ytdlp est vrai par défaut : sans mock, chaque construction
    # lance BootstrapWorker qui interroge GitHub et télécharge yt-dlp.exe.
    monkeypatch.setattr(MainWindow, "_update_ytdlp", lambda self, *args, **kwargs: None, raising=False)
    # Onboarding_completed=False par défaut → sans mock, chaque MainWindow
    # planifie une modale bloquante 200 ms après construction.
    monkeypatch.setattr(MainWindow, "_maybe_show_onboarding", lambda self: None, raising=False)
    win = MainWindow()
    qtbot.addWidget(win)
    return win
