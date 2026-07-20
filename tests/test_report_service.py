from __future__ import annotations

import zipfile

from app.services.disk_service import DiskService
from app.services.report_service import build_report, issue_url


def test_build_report_redacts_and_zips(tmp_path, monkeypatch):
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "session-1.log").write_text(
        "INFO start\nhttps://example.com/v?token=SECRETVALUE&id=1\n", encoding="utf-8"
    )
    monkeypatch.setattr("app.services.report_service.local_appdata_dir", lambda: tmp_path)

    out = tmp_path / "out"
    zip_path = build_report(out, stamp="fixed")

    assert zip_path.name == "mediagrab-report-fixed.zip"
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
        assert "system.txt" in names
        assert "session-1.log" in names
        content = archive.read("session-1.log").decode("utf-8")
    assert "SECRETVALUE" not in content  # secret redacted
    assert "REDACTED" in content


def test_issue_url_points_to_repo():
    url = issue_url()
    assert url.startswith("https://github.com/Rooot3301/MediaGrab/issues/new?")
    assert "title=" in url and "body=" in url


def test_free_space_and_human_size(tmp_path):
    free = DiskService.free_space(str(tmp_path))
    assert free is None or free > 0
    assert DiskService.human_size(0) == "—"
    assert DiskService.human_size(1500).endswith("Ko")
    assert DiskService.human_size(5 * 1024 * 1024 * 1024).endswith("Go")


def test_free_space_uses_existing_parent(tmp_path):
    # A non-existent nested path should still resolve via its parent.
    assert DiskService.free_space(str(tmp_path / "does" / "not" / "exist")) is not None
