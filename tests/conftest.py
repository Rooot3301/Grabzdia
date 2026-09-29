import os
import tempfile

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
