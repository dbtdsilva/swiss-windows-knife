from swiss_windows_knife.components.update_checker import _releases_above


def _exe(v):
    return {"name": f"Installer-{v}.exe",
            "browser_download_url": f"https://example/{v}.exe"}


def test_releases_above_filters_drafts_and_prereleases():
    releases = [
        {"tag_name": "2.0.0", "draft": True, "assets": [_exe("2.0.0")]},
        {"tag_name": "1.5.0", "prerelease": True, "assets": [_exe("1.5.0")]},
        {"tag_name": "1.4.0", "body": "notes", "assets": [_exe("1.4.0")]},
    ]
    target, url, changelog = _releases_above(releases, "1.0.0")
    assert target == "1.4.0"
    assert url == "https://example/1.4.0.exe"
    assert [t for t, _ in changelog] == ["1.4.0"]


def test_releases_above_lists_all_versions_above_current_newest_first():
    releases = [
        {"tag_name": "1.4.0", "body": "c", "assets": [_exe("1.4.0")]},
        {"tag_name": "1.2.0", "body": "a", "assets": []},
        {"tag_name": "1.3.0", "body": "b", "assets": []},
    ]
    target, url, changelog = _releases_above(releases, "1.1.0")
    assert target == "1.4.0"
    assert changelog == [("1.4.0", "c"), ("1.3.0", "b"), ("1.2.0", "a")]


def test_releases_above_excludes_current_and_older():
    releases = [
        {"tag_name": "1.1.0", "body": "x", "assets": [_exe("1.1.0")]},
        {"tag_name": "1.0.0", "body": "old", "assets": []},
    ]
    target, url, changelog = _releases_above(releases, "1.1.0")
    assert target == "1.1.0"
    assert changelog == []


def test_releases_above_none_when_target_has_no_installer():
    releases = [{"tag_name": "2.0.0", "assets": [{"name": "notes.txt"}]}]
    assert _releases_above(releases, "1.0.0") == (None, None, [])


def test_releases_above_none_when_empty():
    assert _releases_above([], "1.0.0") == (None, None, [])
