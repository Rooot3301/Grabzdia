from __future__ import annotations

APP_NAME = "MediaGrab"
ORGANIZATION = "MediaGrab"
DEFAULT_FILENAME_TEMPLATE = "%(title)s [%(id)s].%(ext)s"
PLAYLIST_FILENAME_TEMPLATE = "%(playlist_index)03d - %(title)s [%(id)s].%(ext)s"
PROGRESS_PREFIX = "MGPROGRESS:"
FINAL_PATH_PREFIX = "MGFILE:"
QUALITY_HEIGHTS = {"360p": 360, "480p": 480, "720p": 720, "1080p": 1080, "1440p": 1440, "2160p": 2160}

# GitHub repository used for in-app update checks.
GITHUB_REPO = "Rooot3301/MediaGrab"
GITHUB_LATEST_RELEASE_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_RELEASES_PAGE = f"https://github.com/{GITHUB_REPO}/releases/latest"

