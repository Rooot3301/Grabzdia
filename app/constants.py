from __future__ import annotations

APP_NAME = "Grabzdia"
ORGANIZATION = "Grabzdia"
DEFAULT_FILENAME_TEMPLATE = "%(title)s [%(id)s].%(ext)s"
PLAYLIST_FILENAME_TEMPLATE = "%(playlist_index)03d - %(title)s [%(id)s].%(ext)s"
PROGRESS_PREFIX = "GZPROGRESS:"
FINAL_PATH_PREFIX = "GZFILE:"
QUALITY_HEIGHTS = {"360p": 360, "480p": 480, "720p": 720, "1080p": 1080, "1440p": 1440, "2160p": 2160}

# GitHub repository used for in-app update checks.
GITHUB_REPO = "Rooot3301/Grabzdia"
GITHUB_RELEASES_PAGE = f"https://github.com/{GITHUB_REPO}/releases/latest"
GITHUB_RELEASES_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases"

# Page de documentation yt-dlp listant tous les sites extractibles.
SUPPORTED_SITES_URL = "https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md"

# Catégories SponsorBlock retirées quand l’option est active (YouTube uniquement).
SPONSORBLOCK_CATEGORIES = "sponsor,selfpromo,interaction"

