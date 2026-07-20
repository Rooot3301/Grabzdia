from __future__ import annotations

import os
import sys
from pathlib import Path


def appdata_dir() -> Path:
    return Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming")) / "MediaGrab"


def local_appdata_dir() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "MediaGrab"


def managed_binary_dir() -> Path:
    """Writable location for binaries downloaded on first run.

    Program Files is read-only for normal users, so downloaded executables live
    under LOCALAPPDATA instead of next to the installed application.
    """
    return local_appdata_dir() / "bin"


def default_download_dir() -> Path:
    return Path.home() / "Downloads" / "MediaGrab"


def resource_root() -> Path:
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))


def binary_dir() -> Path:
    return resource_root() / "bin"


def assets_dir() -> Path:
    return resource_root() / "assets"


def icon_path(name: str) -> Path:
    return assets_dir() / "icons" / name


def logo_path() -> Path:
    return assets_dir() / "logo.svg"


def stylesheet_path() -> Path:
    return assets_dir() / "styles" / "dark.qss"


def light_stylesheet_path() -> Path:
    return assets_dir() / "styles" / "light.qss"


def app_icon_path() -> Path:
    return assets_dir() / "MediaGrab.ico"


def ensure_app_directories() -> None:
    for path in (appdata_dir(), local_appdata_dir() / "logs", managed_binary_dir(), default_download_dir()):
        path.mkdir(parents=True, exist_ok=True)


def settings_path() -> Path: return appdata_dir() / "settings.json"
def history_path() -> Path: return appdata_dir() / "history.json"
def queue_path() -> Path: return appdata_dir() / "queue.json"
def archive_path() -> Path: return appdata_dir() / "download_archive.txt"

