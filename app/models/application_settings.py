from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.utils.paths import default_download_dir


@dataclass(slots=True)
class ApplicationSettings:
    default_download_directory: str = ""
    last_download_directory: str = ""
    theme: str = "dark"
    parallel_downloads: int = 2
    history_limit: int = 500
    organize_mode: str = "all"
    use_download_archive: bool = False
    notifications: bool = True
    filename_template: str = "%(title)s [%(id)s].%(ext)s"

    def __post_init__(self) -> None:
        default = str(default_download_dir())
        self.default_download_directory = self.default_download_directory or default
        self.last_download_directory = self.last_download_directory or self.default_download_directory
        self.parallel_downloads = min(4, max(1, int(self.parallel_downloads)))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ApplicationSettings:
        allowed = cls.__dataclass_fields__.keys()
        return cls(**{key: value[key] for key in allowed if key in value})
