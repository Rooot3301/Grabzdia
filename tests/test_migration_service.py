from __future__ import annotations

from pathlib import Path

from app.services.migration_service import migrate_legacy_data, should_migrate


def test_should_migrate_true_when_legacy_present_and_new_absent(tmp_path: Path):
    legacy = tmp_path / "MediaGrab"; legacy.mkdir()
    new = tmp_path / "Grabzdia"
    assert should_migrate(new, legacy) is True


def test_should_migrate_false_when_new_exists(tmp_path: Path):
    legacy = tmp_path / "MediaGrab"; legacy.mkdir()
    new = tmp_path / "Grabzdia"; new.mkdir()
    assert should_migrate(new, legacy) is False


def test_should_migrate_false_when_no_legacy(tmp_path: Path):
    assert should_migrate(tmp_path / "Grabzdia", tmp_path / "MediaGrab") is False


def test_migrate_copies_files(tmp_path: Path):
    legacy_roaming = tmp_path / "Roaming" / "MediaGrab"
    legacy_roaming.mkdir(parents=True)
    (legacy_roaming / "settings.json").write_text('{"theme":"dark"}', encoding="utf-8")
    legacy_local = tmp_path / "Local" / "MediaGrab" / "bin"
    legacy_local.mkdir(parents=True)
    (legacy_local / "yt-dlp.exe").write_bytes(b"binary")
    new_roaming = tmp_path / "Roaming" / "Grabzdia"
    new_local = tmp_path / "Local" / "Grabzdia"

    did = migrate_legacy_data(new_roaming, new_local, legacy_roaming, legacy_local.parent)

    assert did is True
    assert (new_roaming / "settings.json").read_text(encoding="utf-8") == '{"theme":"dark"}'
    assert (new_local / "bin" / "yt-dlp.exe").read_bytes() == b"binary"


def test_migrate_idempotent_when_new_exists(tmp_path: Path):
    legacy_roaming = tmp_path / "Roaming" / "MediaGrab"; legacy_roaming.mkdir(parents=True)
    (legacy_roaming / "settings.json").write_text("old", encoding="utf-8")
    new_roaming = tmp_path / "Roaming" / "Grabzdia"; new_roaming.mkdir(parents=True)
    (new_roaming / "settings.json").write_text("current", encoding="utf-8")
    new_local = tmp_path / "Local" / "Grabzdia"
    legacy_local = tmp_path / "Local" / "MediaGrab"

    did = migrate_legacy_data(new_roaming, new_local, legacy_roaming, legacy_local)

    assert did is False
    assert (new_roaming / "settings.json").read_text(encoding="utf-8") == "current"
