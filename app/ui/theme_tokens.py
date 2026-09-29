"""Palettes de couleurs pour les thèmes alternatifs de Grabzdia.

Le thème « sombre » (par défaut) et le thème « clair » ont chacun leur QSS
complet dans assets/styles/. Les thèmes alternatifs (midnight, sunset,
forest) sont générés au chargement en appliquant des substitutions de
couleurs sur le QSS sombre — c'est pragmatique et évite de dupliquer 275
lignes de style pour chaque variante.

Chaque palette est un dict {couleur_source_hex: couleur_cible_hex}. Les
substitutions sont insensibles à la casse et ne matchent que des tokens
hex complets (#RRGGBB), pas des sous-chaînes arbitraires.
"""
from __future__ import annotations

# Étiquettes affichées dans le sélecteur de thème.
THEME_LABELS: dict[str, str] = {
    "dark": "Sombre",
    "light": "Clair",
    "system": "Système",
    "midnight": "Minuit (bleu profond)",
    "sunset": "Coucher de soleil (orange chaud)",
    "forest": "Forêt (vert émeraude)",
}


# Thème « Minuit » : mêmes fonds sombres qu'en base, accents bleu-électrique.
_MIDNIGHT: dict[str, str] = {
    # accent primaire (sidebar active, eyebrow, CTA)
    "#7B61FF": "#4A9AFF",
    "#7C5CFF": "#4A9AFF",   # gradient start
    "#39C5FF": "#B5D6FF",   # gradient end (bleu très clair)
    "#8A6BFF": "#5FA9FF",   # hover
    "#4FCEFF": "#C7DFFF",
    "#6E4EEB": "#3A87F0",   # pressed
    "#2CB6F0": "#95B8FF",
    "#9B8BFF": "#8FB6FF",   # muted eyebrow
    "#9B8CFF": "#8FB6FF",
    "#B9C0FF": "#B9D6FF",
    "#241F4A": "#1A2542",
    # icônes stats
    "#B9A9FF": "#B9CFFF",
}


# Thème « Coucher de soleil » : chaleur orangée, fond très légèrement bruni.
_SUNSET: dict[str, str] = {
    # accent primaire
    "#7B61FF": "#FF7A4A",
    "#7C5CFF": "#FF7A4A",
    "#39C5FF": "#FFC466",
    "#8A6BFF": "#FF8F5F",
    "#4FCEFF": "#FFD37F",
    "#6E4EEB": "#EB6A3A",
    "#2CB6F0": "#F0A244",
    "#9B8BFF": "#FFB284",
    "#9B8CFF": "#FFB284",
    "#B9C0FF": "#FFD0B4",
    "#241F4A": "#3D1F14",
    "#B9A9FF": "#FFC5A0",
    # léger réchauffement des fonds les plus sombres
    "#0E1218": "#160E10",
    "#10151D": "#1A1214",
    "#141B24": "#1F181B",
    "#171E28": "#241C1F",
    "#0F151E": "#171012",
    # bordures
    "#262E3A": "#3A2A2E",
    "#2A3444": "#432F34",
    "#212A36": "#33262A",
}


# Thème « Forêt » : émeraude sur fond très légèrement verdâtre.
_FOREST: dict[str, str] = {
    # accent primaire
    "#7B61FF": "#4EDC95",
    "#7C5CFF": "#4EDC95",
    "#39C5FF": "#A5F5CF",
    "#8A6BFF": "#5FE6A2",
    "#4FCEFF": "#B8FBDB",
    "#6E4EEB": "#3AC280",
    "#2CB6F0": "#7BE3B3",
    "#9B8BFF": "#8DE5B8",
    "#9B8CFF": "#8DE5B8",
    "#B9C0FF": "#C4EFD4",
    "#241F4A": "#123024",
    "#B9A9FF": "#B4EBD1",
    # léger verdissement des fonds les plus sombres
    "#0E1218": "#0B1410",
    "#10151D": "#0E1B14",
    "#141B24": "#12251A",
    "#171E28": "#152A1E",
    "#0F151E": "#0D1712",
    # bordures
    "#262E3A": "#243A2E",
    "#2A3444": "#2E4437",
    "#212A36": "#1F3226",
}


THEME_SUBSTITUTIONS: dict[str, dict[str, str]] = {
    "midnight": _MIDNIGHT,
    "sunset": _SUNSET,
    "forest": _FOREST,
}


def apply_substitutions(qss: str, theme: str) -> str:
    """Renvoie le QSS avec les couleurs du thème demandé.

    Un thème inconnu, ou 'dark', retourne le texte tel quel.
    Les remplacements sont case-insensitive côté source, la cible garde
    sa casse d'origine dans la palette.
    """
    palette = THEME_SUBSTITUTIONS.get(theme)
    if not palette:
        return qss
    for src, dst in palette.items():
        # Case-insensitive replace via lower/upper variants — simple et
        # suffisant vu que Qt QSS accepte les deux et qu'on écrit tout
        # en majuscules dans dark.qss.
        qss = qss.replace(src, dst).replace(src.lower(), dst)
    return qss
