"""Check GitHub Releases for a newer version of MediaGrab.

The pure helpers (version parsing/comparison, asset selection) are unit-tested;
the worker performs the network call off the UI thread.
"""
from __future__ import annotations

import json
import urllib.request
from typing import Any
from urllib.parse import urlsplit

from PySide6.QtCore import QObject, Signal

from app.constants import GITHUB_LATEST_RELEASE_API


def _is_trusted_asset(url: str) -> bool:
    """Only trust HTTPS release assets served from GitHub."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    return parts.scheme == "https" and (host == "github.com" or host.endswith(".githubusercontent.com"))


def parse_version(text: str) -> tuple[int, ...]:
    """Turn a version string like 'v1.2.3' into a comparable tuple (1, 2, 3)."""
    cleaned = text.strip().lstrip("vV")
    parts: list[int] = []
    for chunk in cleaned.split("."):
        digits = "".join(character for character in chunk if character.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts) or (0,)


def is_newer(latest: str, current: str) -> bool:
    """True when the latest version is strictly greater than the current one."""
    return parse_version(latest) > parse_version(current)


def select_installer_asset(assets: list[dict[str, Any]]) -> str | None:
    """Return the download URL of the first .exe asset served from GitHub."""
    for asset in assets:
        name = str(asset.get("name", "")).lower()
        url = str(asset.get("browser_download_url", ""))
        if name.endswith(".exe") and _is_trusted_asset(url):
            return url
    return None


class UpdateCheckWorker(QObject):
    """Fetches the latest release metadata from GitHub off the UI thread."""

    finished = Signal(object, str)  # release info dict (or None), error message

    def run(self) -> None:
        try:
            request = urllib.request.Request(
                GITHUB_LATEST_RELEASE_API,
                headers={"User-Agent": "MediaGrab", "Accept": "application/vnd.github+json"},
            )
            with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310 (fixed https host)
                data = json.load(response)
            info = {
                "version": str(data.get("tag_name", "")),
                "page": str(data.get("html_url", "")),
                "notes": str(data.get("body", "")),
                "asset": select_installer_asset(data.get("assets", []) or []),
            }
            self.finished.emit(info, "")
        except Exception as error:  # noqa: BLE001 (report any failure to the UI)
            self.finished.emit(None, str(error))
