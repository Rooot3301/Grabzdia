from __future__ import annotations

import logging
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.services.binary_service import BinaryService
from app.services.bootstrap_service import components_for
from app.services.settings_service import SettingsService
from app.ui.first_run_dialog import FirstRunDialog
from app.ui.main_window import MainWindow
from app.ui.theme import apply_theme
from app.utils.logging_utils import configure_logging
from app.utils.paths import (
    app_icon_path,
    ensure_app_directories,
    logo_path,
)


def _application_icon() -> QIcon:
    icon = app_icon_path()
    if icon.exists():
        return QIcon(str(icon))
    return QIcon(str(logo_path()))


def _run_first_run_if_needed() -> None:
    missing = BinaryService().missing()
    if not missing:
        return
    logging.info("Composants manquants au démarrage : %s", ", ".join(missing))
    FirstRunDialog(components_for(missing)).exec()


def main() -> int:
    ensure_app_directories()
    configure_logging()
    logging.info("Démarrage de MediaGrab")
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    application = QApplication(sys.argv)
    application.setApplicationName("MediaGrab")
    application.setOrganizationName("MediaGrab")
    application.setWindowIcon(_application_icon())
    apply_theme(application, SettingsService().load().theme)
    _run_first_run_if_needed()
    window = MainWindow()
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
