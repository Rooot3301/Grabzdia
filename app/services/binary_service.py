from __future__ import annotations

import shutil
from pathlib import Path

from app.exceptions import BinaryNotFoundError
from app.utils.paths import binary_dir, managed_binary_dir


class BinaryService:
    NAMES = {"yt-dlp": "yt-dlp.exe", "ffmpeg": "ffmpeg.exe", "ffprobe": "ffprobe.exe"}

    def locate(self, name: str) -> Path:
        filename = self.NAMES[name]
        # Search order: downloaded (writable) dir, bundled dir, then PATH.
        for directory in (managed_binary_dir(), binary_dir()):
            candidate = directory / filename
            if candidate.is_file():
                return candidate
        found = shutil.which(filename) or shutil.which(name)
        if found:
            return Path(found)
        raise BinaryNotFoundError(f"{filename} est introuvable. Ouvrez MediaGrab pour télécharger les composants.")

    def status(self) -> dict[str, str]:
        result = {}
        for name in self.NAMES:
            try:
                result[name] = str(self.locate(name))
            except BinaryNotFoundError:
                result[name] = "absent"
        return result

    def missing(self) -> list[str]:
        """Names of binaries that cannot be located anywhere."""
        return [name for name, value in self.status().items() if value == "absent"]
