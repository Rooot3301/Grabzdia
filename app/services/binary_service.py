from __future__ import annotations

import shutil
from pathlib import Path

from app.exceptions import BinaryNotFoundError
from app.utils.paths import binary_dir


class BinaryService:
    NAMES = {"yt-dlp": "yt-dlp.exe", "ffmpeg": "ffmpeg.exe", "ffprobe": "ffprobe.exe"}

    def locate(self, name: str) -> Path:
        filename = self.NAMES[name]
        bundled = binary_dir() / filename
        if bundled.is_file(): return bundled
        found = shutil.which(filename) or shutil.which(name)
        if found: return Path(found)
        raise BinaryNotFoundError(f"{filename} est introuvable. Placez-le dans le dossier bin.")

    def status(self) -> dict[str, str]:
        result = {}
        for name in self.NAMES:
            try: result[name] = str(self.locate(name))
            except BinaryNotFoundError: result[name] = "absent"
        return result

