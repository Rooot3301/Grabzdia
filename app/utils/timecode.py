from __future__ import annotations

import re

_PART = re.compile(r"\d+")
_FORMAT_HINT = "Format attendu : hh:mm:ss, mm:ss ou secondes."


def parse_timecode(text: str) -> int:
    """« 1:02:03 », « 62:03 », « 3723 » → secondes.

    Le premier composant est libre (« 90:00 » = 1 h 30) ; les suivants doivent
    rester sous 60 pour attraper les fautes de frappe (« 1:75 »).
    """
    parts = text.strip().split(":")
    if not 1 <= len(parts) <= 3 or not all(_PART.fullmatch(part) for part in parts):
        raise ValueError(_FORMAT_HINT)
    values = [int(part) for part in parts]
    if any(value >= 60 for value in values[1:]):
        raise ValueError(_FORMAT_HINT)
    seconds = 0
    for value in values:
        seconds = seconds * 60 + value
    return seconds


def format_timecode(seconds: int) -> str:
    hours, rest = divmod(max(0, int(seconds)), 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def filename_stamp(start: int, end: int) -> str:
    """Horodatage d'extrait utilisable dans un nom de fichier Windows (pas de « : »)."""

    def stamp(seconds: int) -> str:
        hours, minutes, secs = format_timecode(seconds).split(":")
        return f"{hours}h{minutes}m{secs}s"

    return f"{stamp(start)}-{stamp(end)}"
