from __future__ import annotations

import logging
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow
from app.utils.logging_utils import configure_logging
from app.utils.paths import ensure_app_directories, resource_root


def main() -> int:
    ensure_app_directories(); configure_logging(); logging.info("Démarrage de MediaGrab")
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    application = QApplication(sys.argv); application.setApplicationName("MediaGrab"); application.setOrganizationName("MediaGrab")
    style = resource_root() / "assets" / "styles" / "dark.qss"
    if style.exists(): application.setStyleSheet(style.read_text(encoding="utf-8"))
    window = MainWindow(); window.show(); return application.exec()


if __name__ == "__main__": raise SystemExit(main())
