from __future__ import annotations

import os
import shutil
from pathlib import Path

from app.exceptions import InsufficientDiskSpaceError, InvalidDestinationError


class DiskService:
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
