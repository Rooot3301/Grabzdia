from __future__ import annotations

import os
import shutil
from pathlib import Path

from app.exceptions import InsufficientDiskSpaceError, InvalidDestinationError


class DiskService:
    @staticmethod
    def free_space(value: str) -> int | None:
        """Free bytes on the volume holding `value`, or None if unknown.

        Falls back to the nearest existing parent so it works before the folder
        is created.
        """
        path = Path(value).expanduser()
        while not path.exists() and path != path.parent:
            path = path.parent
        try:
            return shutil.disk_usage(path).free
        except OSError:
            return None

    @staticmethod
    def resolve_media_path(final_path: str, destination: str = "") -> str | None:
        """Return an existing file path for playback.

        Falls back to destination/<filename> when the recorded final_path is
        missing or points nowhere (e.g. a legacy path corrupted by encoding).
        """
        if final_path and Path(final_path).is_file():
            return final_path
        if final_path and destination:
            candidate = Path(destination) / Path(final_path.replace("\\", "/")).name
            if candidate.is_file():
                return str(candidate)
        return None

    @staticmethod
    def human_size(num: int | None) -> str:
        if not num or num < 0:
            return "—"
        size = float(num)
        for unit in ("o", "Ko", "Mo", "Go", "To"):
            if size < 1024 or unit == "To":
                return f"{size:.0f} {unit}" if unit in ("o", "Ko") else f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} To"

    @staticmethod
    def validate_destination(value: str, expected_size: int | None = None) -> Path:
        path = Path(value).expanduser()
        if "\x00" in value: raise InvalidDestinationError("Le chemin contient un caractère invalide.")
        try: path.mkdir(parents=True, exist_ok=True)
        except OSError as error: raise InvalidDestinationError("Impossible de créer le dossier de destination.") from error
        if not path.is_dir(): raise InvalidDestinationError("La destination n’est pas un dossier.")
        try:
            probe = path / f".mediagrab-write-{os.getpid()}"
            probe.touch(exist_ok=False); probe.unlink()
        except OSError as error: raise InvalidDestinationError("Le dossier n’est pas accessible en écriture.") from error
        if expected_size and shutil.disk_usage(path).free < int(expected_size * 1.1):
            raise InsufficientDiskSpaceError("L’espace disque disponible semble insuffisant.")
        return path.resolve()

    @staticmethod
    def organized_destination(base: Path, mode: str, media_type: str, playlist_name: str = "") -> Path:
        if mode == "separate": target = base / ("Audio" if media_type == "audio" else "Videos")
        elif mode == "playlist" and playlist_name: target = base / "Playlists" / playlist_name
        else: target = base
        target.mkdir(parents=True, exist_ok=True)
        return target
