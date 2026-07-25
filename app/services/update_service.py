"""Check GitHub Releases for a newer version of Grabzdia.

The pure helpers (version parsing/comparison, asset selection) are unit-tested;
the worker performs the network call off the UI thread.
"""
from __future__ import annotations

import json
import urllib.request
from typing import Any
from urllib.parse import urlsplit

from PySide6.QtCore import QObject, Signal

from app.constants import GITHUB_RELEASES_API


def _is_trusted_asset(url: str) -> bool:
    """Only trust HTTPS release assets served from GitHub."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    return parts.scheme == "https" and (host == "github.com" or host.endswith(".githubusercontent.com"))


def version_key(text: str) -> tuple[int, int, int, int, int]:
    """Clé ordonnable gérant les pré-releases -evo.

    Stable X.Y.Z -> (X, Y, Z, 1, 0) ; beta X.Y.Z-evo.N -> (X, Y, Z, 0, N).
    Ainsi une beta est classée juste avant sa stable. Tag malformé -> (0,0,0,1,0).
    """
    cleaned = text.strip().lstrip("vV")
    base, rank, evo = cleaned, 1, 0
    if "-evo" in cleaned.lower():
        base, _, suffix = cleaned.partition("-evo")
        digits = "".join(c for c in suffix if c.isdigit())
        rank, evo = 0, int(digits) if digits else 0
    nums: list[int] = []
    for chunk in base.split("."):
        d = "".join(c for c in chunk if c.isdigit())
        nums.append(int(d) if d else 0)
    nums = (nums + [0, 0, 0])[:3]
    return (nums[0], nums[1], nums[2], rank, evo)


def is_prerelease(text: str) -> bool:
    """True pour une version/tag de pré-release EVO."""
    return "-evo" in text.lower()


def is_newer(latest: str, current: str) -> bool:
    """True quand `latest` est strictement plus récent que `current`."""
    return version_key(latest) > version_key(current)


def choose_update(channel: str, current: str, releases: list[dict]) -> dict | None:
    """Choisit la release à proposer selon le canal, ou None.

    LIVE : dernière stable ; proposée si plus récente, ou en retour à la stable
    lorsque l'on tourne sur une beta. EVO : la plus récente toutes catégories.
    Le dict renvoyé est la release cible enrichie de `return_to_stable`.
    """
    usable = [r for r in releases if r.get("version")]
    if not usable:
        return None
    current_key = version_key(current)
    if channel == "evo":
        target = max(usable, key=lambda r: version_key(r["version"]))
        if version_key(target["version"]) > current_key:
            return {**target, "return_to_stable": False}
        return None
    stables = [r for r in usable if not r.get("prerelease")]
    if not stables:
        return None
    target = max(stables, key=lambda r: version_key(r["version"]))
    if version_key(target["version"]) > current_key:
        return {**target, "return_to_stable": False}
    if is_prerelease(current) and target["version"] != current:
        return {**target, "return_to_stable": True}
    return None


def select_installer_asset(assets: list[dict[str, Any]]) -> str | None:
    """Return the download URL of the first .exe asset served from GitHub."""
    for asset in assets:
        name = str(asset.get("name", "")).lower()
        url = str(asset.get("browser_download_url", ""))
        if name.endswith(".exe") and _is_trusted_asset(url):
            return url
    return None


def _parse_release(data: dict) -> dict:
    return {
        "version": str(data.get("tag_name", "")),
        "prerelease": bool(data.get("prerelease", False)),
        "page": str(data.get("html_url", "")),
        "notes": str(data.get("body", "")),
        "asset": select_installer_asset(data.get("assets", []) or []),
    }


class UpdateCheckWorker(QObject):
    """Récupère la liste des releases GitHub hors du thread UI."""

    finished = Signal(object, str)  # list[dict] (ou None), message d'erreur

    def run(self) -> None:
        try:
            request = urllib.request.Request(
                GITHUB_RELEASES_API,
                headers={"User-Agent": "Grabzdia", "Accept": "application/vnd.github+json"},
            )
            with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310 (fixed https host)
                data = json.load(response)
            releases = [_parse_release(entry) for entry in data] if isinstance(data, list) else []
            self.finished.emit(releases, "")
        except Exception as error:  # noqa: BLE001 (report any failure to the UI)
            self.finished.emit(None, str(error))
