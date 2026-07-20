from __future__ import annotations

import logging
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow
from app.utils.logging_utils import configure_logging
from app.utils.paths import (
    app_icon_path,
    ensure_app_directories,
    logo_path,
    stylesheet_path,
)


def _application_icon() -> QIcon:
    icon = app_icon_path()
    if icon.exists():
        return QIcon(str(icon))
    return QIcon(str(logo_path()))


def main() -> int:
    ensure_app_directories()
    configure_logging()
    logging.info("Démarrage de MediaGrab")
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    application = QApplication(sys.argv)
    application.setApplicationName("MediaGrab")
    application.setOrganizationName("MediaGrab")
    application.setWindowIcon(_application_icon())
    style = stylesheet_path()
    if style.exists():
        application.setStyleSheet(style.read_text(encoding="utf-8"))
    window = MainWindow()
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
