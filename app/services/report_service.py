"""Build a shareable problem report: recent logs (secrets redacted) + system
info, plus a pre-filled GitHub issue URL.
"""
from __future__ import annotations

import platform
import sys
import urllib.parse
import zipfile
from datetime import datetime
from pathlib import Path

from app.constants import GITHUB_REPO
from app.utils.logging_utils import redact_secrets
from app.utils.paths import local_appdata_dir
from app.version import __version__


def system_summary() -> str:
    return f"MediaGrab {__version__}\nOS: {platform.platform()}\nPython: {sys.version.split()[0]}\n"


def build_report(dest_dir: Path, max_logs: int = 5, stamp: str | None = None) -> Path:
    """Zip the most recent session logs (redacted) and a system summary."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = local_appdata_dir() / "logs"
    logs = sorted(logs_dir.glob("session-*.log"), reverse=True)[:max_logs] if logs_dir.is_dir() else []
    stamp = stamp or datetime.now().strftime("%Y%m%d-%H%M%S")
    zip_path = dest_dir / f"mediagrab-report-{stamp}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("system.txt", system_summary())
        for log in logs:
            try:
                text = log.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            archive.writestr(log.name, redact_secrets(text))
    return zip_path


def issue_url() -> str:
    title = f"[Bug] MediaGrab {__version__} : "
    body = (
        "Décrivez le problème :\n\n\n"
        "Étapes pour reproduire :\n1. \n2. \n\n"
        "Pensez à joindre le fichier mediagrab-report-*.zip (ouvert dans votre dossier Téléchargements).\n\n"
        f"---\n{system_summary()}"
    )
    params = urllib.parse.urlencode({"title": title, "body": body})
    return f"https://github.com/{GITHUB_REPO}/issues/new?{params}"
