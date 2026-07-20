from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QSystemTrayIcon


class NotificationService(QObject):
    """Native completion toasts backed by a system tray icon.

    Degrades gracefully to a no-op when no system tray is available.
    """

    activated = Signal()  # emitted when the user clicks the tray icon or a toast

    def __init__(self, icon: QIcon, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.enabled = True
        self.tray: QSystemTrayIcon | None = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QSystemTrayIcon(icon, parent)
            self.tray.setToolTip("MediaGrab")
            self.tray.activated.connect(lambda _reason: self.activated.emit())
            self.tray.messageClicked.connect(self.activated)
            self.tray.show()

    def notify(self, title: str, message: str, success: bool = True) -> None:
        if not self.enabled or self.tray is None:
            return
        icon = QSystemTrayIcon.MessageIcon.Information if success else QSystemTrayIcon.MessageIcon.Warning
        self.tray.showMessage(title, message, icon, 5000)

    def shutdown(self) -> None:
        if self.tray is not None:
            self.tray.hide()
