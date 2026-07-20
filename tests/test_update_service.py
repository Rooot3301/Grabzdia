from __future__ import annotations

from app.services.update_service import is_newer, parse_version, select_installer_asset


def test_parse_version_strips_prefix_and_splits():
    assert parse_version("v1.2.3") == (1, 2, 3)
    assert parse_version("1.0.0") == (1, 0, 0)


def test_parse_version_handles_noise():
    assert parse_version("v2.0") == (2, 0)
    assert parse_version("") == (0,)


def test_is_newer_true_when_greater():
    assert is_newer("1.1.0", "1.0.0")
    assert is_newer("v2.0.0", "1.9.9")


def test_is_newer_false_when_equal_or_older():
    assert not is_newer("1.0.0", "1.0.0")
    assert not is_newer("v1.0.0", "1.0.0")
    assert not is_newer("0.9.0", "1.0.0")


def test_select_installer_asset_picks_github_exe():
    assets = [
        {"name": "notes.txt", "browser_download_url": "https://github.com/x/y/releases/download/v1/notes.txt"},
        {"name": "MediaGrab-Setup-1.1.0.exe", "browser_download_url": "https://github.com/x/y/releases/download/v1/MediaGrab-Setup-1.1.0.exe"},
    ]
    assert select_installer_asset(assets).endswith("MediaGrab-Setup-1.1.0.exe")


def test_select_installer_asset_none_when_no_exe():
    assert select_installer_asset([{"name": "readme.md", "browser_download_url": "https://github.com/x/y/r.md"}]) is None
    assert select_installer_asset([]) is None


def test_select_installer_asset_rejects_untrusted_host():
    # An .exe served from a non-GitHub host must be ignored (no code execution
    # from an untrusted origin).
    assets = [{"name": "evil.exe", "browser_download_url": "https://evil.example.com/evil.exe"}]
    assert select_installer_asset(assets) is None
    # http (non-TLS) also rejected
    assets = [{"name": "x.exe", "browser_download_url": "http://github.com/x/y/x.exe"}]
    assert select_installer_asset(assets) is None
