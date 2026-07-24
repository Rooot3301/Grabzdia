"""Dérive la version d'application depuis un tag git et l'écrit dans version.py.

Utilisé par le workflow de release : le tag est l'unique source de version,
ce qui évite tout décalage entre le tag publié et `app/version.py`.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(-evo\.\d+)?$")


def version_from_tag(tag: str) -> str:
    """'v1.1.0' -> '1.1.0', 'v1.1.0-evo.2' -> '1.1.0-evo.2'. ValueError si invalide."""
    cleaned = tag.strip()
    if cleaned[:1] in ("v", "V"):
        cleaned = cleaned[1:]
    if not _VERSION_RE.match(cleaned):
        raise ValueError(f"Tag invalide : {tag!r} (attendu vX.Y.Z ou vX.Y.Z-evo.N)")
    return cleaned


def is_prerelease(tag: str) -> bool:
    """True pour les betas EVO (tags portant un suffixe -evo)."""
    return "-evo" in tag


def write_version(path: Path, version: str) -> None:
    """Réécrit la ligne __version__ = "..." dans un fichier de type version.py."""
    text = path.read_text(encoding="utf-8")
    new_text, count = re.subn(r'__version__\s*=\s*"[^"]*"', f'__version__ = "{version}"', text)
    if count != 1:
        raise ValueError(f"Impossible de localiser __version__ dans {path}")
    path.write_text(new_text, encoding="utf-8")


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: set_version.py <tag>", file=sys.stderr)
        return 2
    version = version_from_tag(argv[1])
    write_version(Path("app/version.py"), version)
    print(version)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
