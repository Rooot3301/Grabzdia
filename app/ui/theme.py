from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.utils.paths import light_stylesheet_path, stylesheet_path


def resolve_theme(app: QApplication, theme: str) -> str:
    """Resolve 'system' to 'dark' or 'light' from the OS colour scheme."""
    if theme == "system":
        try:
            if app.styleHints().colorScheme() == Qt.ColorScheme.Light:
                return "light"
        except Exception:
            return "dark"
        return "dark"
    return theme if theme in ("dark", "light") else "dark"


def apply_theme(app: QApplication, theme: str) -> str:
    """Apply the stylesheet for the given theme; returns the resolved theme."""
    resolved = resolve_theme(app, theme)
    path = light_stylesheet_path() if resolved == "light" else stylesheet_path()
    if path.exists():
        app.setStyleSheet(path.read_text(encoding="utf-8"))
    return resolved
