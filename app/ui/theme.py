from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from app.ui.theme_tokens import THEME_SUBSTITUTIONS, apply_substitutions
from app.utils.paths import light_stylesheet_path, stylesheet_path

# Qt does not cascade QSS rules into a QLabel's rich-text anchors: their
# colour comes from the palette's Link role, set here per theme.
LINK_COLORS = {
    "dark": "#9B8CFF",
    "light": "#5B44E0",
    "midnight": "#8FB6FF",
    "sunset": "#FFB284",
    "forest": "#8DE5B8",
}

# Thèmes reconnus, dans l'ordre où on veut les proposer.
KNOWN_THEMES: tuple[str, ...] = ("dark", "light", "system", "midnight", "sunset", "forest")


def resolve_theme(app: QApplication, theme: str) -> str:
    """Resolve 'system' à 'dark' ou 'light' selon le schéma OS. Les autres
    thèmes (midnight, sunset, forest) sont laissés tels quels. Toute
    valeur inconnue tombe sur 'dark'."""
    if theme == "system":
        try:
            if app.styleHints().colorScheme() == Qt.ColorScheme.Light:
                return "light"
        except Exception:
            return "dark"
        return "dark"
    return theme if theme in KNOWN_THEMES else "dark"


def apply_theme(app: QApplication, theme: str) -> str:
    """Apply the stylesheet for the given theme; returns the resolved theme."""
    resolved = resolve_theme(app, theme)
    if resolved == "light":
        path = light_stylesheet_path()
        qss = path.read_text(encoding="utf-8") if path.exists() else ""
    else:
        # dark + variantes dérivées : on part du QSS sombre puis on applique
        # les substitutions de couleurs du thème s'il est dans le catalogue.
        path = stylesheet_path()
        qss = path.read_text(encoding="utf-8") if path.exists() else ""
        if resolved in THEME_SUBSTITUTIONS:
            qss = apply_substitutions(qss, resolved)
    if qss:
        app.setStyleSheet(qss)
    palette = app.palette()
    palette.setColor(QPalette.ColorRole.Link, QColor(LINK_COLORS.get(resolved, LINK_COLORS["dark"])))
    app.setPalette(palette)
    return resolved
