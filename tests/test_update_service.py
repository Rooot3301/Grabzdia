from __future__ import annotations

from app.services.update_service import (
    choose_update,
    is_newer,
    is_prerelease,
    select_installer_asset,
    version_key,
)


def test_version_key_strips_prefix_and_splits():
    assert version_key("v1.2.3") == (1, 2, 3, 1, 0)
    assert version_key("1.0.0") == (1, 0, 0, 1, 0)


def test_version_key_handles_noise():
    assert version_key("v2.0") == (2, 0, 0, 1, 0)
    assert version_key("") == (0, 0, 0, 1, 0)


def test_version_key_orders_beta_below_stable():
    assert version_key("1.1.0-evo.2") < version_key("1.1.0")


def test_version_key_orders_evo_numbers():
    assert version_key("1.1.0-evo.1") < version_key("1.1.0-evo.2")


def test_version_key_cross_minor():
    assert version_key("1.0.9") < version_key("1.1.0-evo.3")


def test_version_key_malformed_defaults():
    assert version_key("not-a-version") == (0, 0, 0, 1, 0)


def test_is_prerelease():
    assert is_prerelease("v1.1.0-evo.1") is True
    assert is_prerelease("1.1.0") is False


def test_is_newer_true_when_greater():
    assert is_newer("1.1.0", "1.0.0")
    assert is_newer("v2.0.0", "1.9.9")


def test_is_newer_false_when_equal_or_older():
    assert not is_newer("1.0.0", "1.0.0")
    assert not is_newer("v1.0.0", "1.0.0")
    assert not is_newer("0.9.0", "1.0.0")


def _rel(tag, prerelease):
    return {"version": tag, "prerelease": prerelease, "page": "", "notes": "", "asset": "x.exe"}


def test_choose_live_offers_newer_stable():
    rels = [_rel("1.2.0", False), _rel("1.1.0", False)]
    result = choose_update("live", "1.1.0", rels)
    assert result["version"] == "1.2.0" and result["return_to_stable"] is False


def test_choose_live_return_to_stable_from_beta():
    rels = [_rel("1.0.9", False), _rel("1.1.0-evo.3", True)]
    result = choose_update("live", "1.1.0-evo.3", rels)
    assert result["version"] == "1.0.9" and result["return_to_stable"] is True


def test_choose_live_up_to_date_returns_none():
    rels = [_rel("1.1.0", False)]
    assert choose_update("live", "1.1.0", rels) is None


def test_choose_evo_offers_newer_beta():
    rels = [_rel("1.1.0-evo.2", True), _rel("1.0.9", False)]
    result = choose_update("evo", "1.1.0-evo.1", rels)
    assert result["version"] == "1.1.0-evo.2" and result["return_to_stable"] is False


def test_choose_evo_prefers_newer_stable_over_older_beta():
    rels = [_rel("1.1.0", False), _rel("1.1.0-evo.2", True)]
    result = choose_update("evo", "1.1.0-evo.2", rels)
    assert result["version"] == "1.1.0"


def test_choose_empty_returns_none():
    assert choose_update("evo", "1.0.0", []) is None


def test_select_installer_asset_picks_github_exe():
    assets = [
        {"name": "notes.txt", "browser_download_url": "https://github.com/x/y/releases/download/v1/notes.txt"},
        {"name": "Grabzdia-Setup-1.1.0.exe", "browser_download_url": "https://github.com/x/y/releases/download/v1/Grabzdia-Setup-1.1.0.exe"},
    ]
    assert select_installer_asset(assets).endswith("Grabzdia-Setup-1.1.0.exe")


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
