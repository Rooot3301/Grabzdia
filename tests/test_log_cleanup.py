from __future__ import annotations

import os
import time
from pathlib import Path

from app.utils.logging_utils import cleanup_old_logs


def _make_log(folder: Path, name: str, age_days: float) -> Path:
    path = folder / name
    path.write_text("log", encoding="utf-8")
    old = time.time() - age_days * 86400
    os.utime(path, (old, old))
    return path


def test_cleanup_removes_only_old_logs(tmp_path: Path):
    recent = _make_log(tmp_path, "session-recent.log", age_days=5)
    old = _make_log(tmp_path, "session-old.log", age_days=45)
    other = tmp_path / "keep.txt"
    other.write_text("x", encoding="utf-8")
    os.utime(other, (time.time() - 90 * 86400, time.time() - 90 * 86400))

    removed = cleanup_old_logs(tmp_path, days=30)

    assert removed == 1
    assert recent.exists()
    assert not old.exists()
    assert other.exists()  # non session-*.log files are untouched


def test_cleanup_missing_folder_is_safe(tmp_path: Path):
    assert cleanup_old_logs(tmp_path / "nope", days=30) == 0
