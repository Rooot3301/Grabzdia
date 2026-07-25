from __future__ import annotations

from pathlib import Path

import pytest

from tools.set_version import is_prerelease, version_from_tag, write_version


def test_version_from_tag_stable():
    assert version_from_tag("v1.1.0") == "1.1.0"


def test_version_from_tag_evo():
    assert version_from_tag("v1.1.0-evo.2") == "1.1.0-evo.2"


def test_version_from_tag_rejects_garbage():
    with pytest.raises(ValueError):
        version_from_tag("v1.2")


def test_is_prerelease():
    assert is_prerelease("v1.1.0-evo.1") is True
    assert is_prerelease("v1.1.0") is False


def test_write_version_replaces_line(tmp_path: Path):
    target = tmp_path / "version.py"
    target.write_text('from __future__ import annotations\n\n__version__ = "0.0.0"\n', encoding="utf-8")
    write_version(target, "1.1.0-evo.2")
    assert '__version__ = "1.1.0-evo.2"' in target.read_text(encoding="utf-8")


def test_write_version_missing_line_raises(tmp_path: Path):
    target = tmp_path / "version.py"
    target.write_text("# no version here\n", encoding="utf-8")
    with pytest.raises(ValueError):
        write_version(target, "1.0.0")
