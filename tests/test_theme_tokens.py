from __future__ import annotations

from app.ui.theme_tokens import THEME_SUBSTITUTIONS, apply_substitutions


def test_unknown_theme_returns_qss_untouched():
    """dark et les valeurs inconnues laissent le QSS tel quel."""
    qss = "QWidget { color: #7B61FF; }"
    assert apply_substitutions(qss, "dark") == qss
    assert apply_substitutions(qss, "n'importe-quoi") == qss


def test_sunset_replaces_the_violet_accent_with_orange():
    """Le thème sunset doit remplacer l'accent violet par un orange."""
    qss = "QLabel#eyebrow { color: #7B61FF; }"
    out = apply_substitutions(qss, "sunset")
    assert "#7B61FF" not in out
    assert THEME_SUBSTITUTIONS["sunset"]["#7B61FF"] in out


def test_forest_replaces_the_violet_accent_with_green():
    qss = "QLabel#eyebrow { color: #7B61FF; }"
    out = apply_substitutions(qss, "forest")
    assert THEME_SUBSTITUTIONS["forest"]["#7B61FF"] in out


def test_midnight_replaces_the_gradient_stops():
    """Le CTA passe d'un dégradé violet→cyan à bleu-électrique."""
    qss = "stop:0 #7C5CFF, stop:1 #39C5FF"
    out = apply_substitutions(qss, "midnight")
    assert "#7C5CFF" not in out
    assert "#39C5FF" not in out
    assert THEME_SUBSTITUTIONS["midnight"]["#7C5CFF"] in out


def test_substitutions_are_case_insensitive_on_source():
    """Le QSS peut contenir #7c5cff en minuscules — la substitution matche."""
    qss = "QWidget { color: #7c5cff; }"
    out = apply_substitutions(qss, "sunset")
    assert "#7c5cff" not in out.lower() or THEME_SUBSTITUTIONS["sunset"]["#7C5CFF"].lower() in out.lower()


def test_all_theme_palettes_target_valid_hex_colours():
    """Un ancien copier-coller cassé (couleur cible malformée) serait détecté
    ici avant d'atteindre Qt qui l'ignorerait silencieusement."""
    import re
    hex_re = re.compile(r"^#[0-9A-Fa-f]{6}$")
    for theme, palette in THEME_SUBSTITUTIONS.items():
        for src, dst in palette.items():
            assert hex_re.match(src), f"{theme}: source malformée {src}"
            assert hex_re.match(dst), f"{theme}: cible malformée {dst}"
