"""Regression coverage for the update-checker worker threads."""
from unittest.mock import patch

import pytest

from swiss_windows_knife.components.update_checker import _CheckThread, _DownloadThread


def _wait_result(qtbot, thread):
    with qtbot.waitSignal(thread.result_ready, timeout=2000) as blocker:
        thread.run()  # call run() directly on the test thread; we want the
        # exception/branch behavior, not the Qt threading mechanics.
    return blocker.args


@pytest.fixture
def check_thread(qtbot):
    return _CheckThread()


def test_check_thread_emits_none_on_unexpected_exception(qtbot, check_thread):
    with patch('swiss_windows_knife.components.update_checker.requests.get', side_effect=OSError("ssl boom")):
        args = _wait_result(qtbot, check_thread)
    assert args == [None]


def test_check_thread_emits_none_on_request_exception(qtbot, check_thread):
    import requests
    with patch(
        'swiss_windows_knife.components.update_checker.requests.get',
        side_effect=requests.ConnectionError("no network"),
    ):
        args = _wait_result(qtbot, check_thread)
    assert args == [None]


def test_check_thread_emits_none_when_release_has_no_installer_asset(qtbot, check_thread):
    class _FakeResp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return [{"tag_name": "9.9.9", "assets": []}]

    with patch('swiss_windows_knife.components.update_checker.requests.get', return_value=_FakeResp()):
        args = _wait_result(qtbot, check_thread)
    assert args == [None]


def test_check_thread_emits_release_tuple_on_success(qtbot, check_thread):
    class _FakeResp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return [{
                "tag_name": "9.9.9",
                "body": "shiny notes",
                "assets": [
                    {"name": "irrelevant.zip"},
                    {"name": "Installer-9.9.9.exe",
                     "browser_download_url": "https://example/9.9.9.exe"},
                ],
            }]

    with patch('swiss_windows_knife.components.update_checker.requests.get', return_value=_FakeResp()):
        args = _wait_result(qtbot, check_thread)
    assert args == [("9.9.9", "https://example/9.9.9.exe", [("9.9.9", "shiny notes")])]


def test_download_thread_emits_none_on_unexpected_exception(qtbot, tmp_path):
    thread = _DownloadThread("https://example/1.exe", str(tmp_path))
    with patch('swiss_windows_knife.components.update_checker.requests.get', side_effect=RuntimeError("???")):
        args = _wait_result(qtbot, thread)
    assert args == [None]


def test_watchdog_clears_busy_when_worker_wedges(qtbot, fake_user_settings):
    """If the worker thread blocks indefinitely, the watchdog must restore
    the menu so the user can try again instead of having the action greyed
    out forever."""
    from swiss_windows_knife.components.update_checker import UpdateChecker

    with patch.object(UpdateChecker, 'check_updates'):
        checker = UpdateChecker(parent=None)
        qtbot.addWidget(checker)
        qtbot.wait(20)

    checker._set_busy(True)
    checker._interactive = False
    checker._check_watchdog()
    assert checker._busy is False


def test_stale_result_after_watchdog_is_ignored(qtbot, fake_user_settings):
    """A late-returning worker after the watchdog cleared busy must not
    pop a misleading 'Update available' modal."""
    from swiss_windows_knife.components.update_checker import UpdateChecker

    with patch.object(UpdateChecker, 'check_updates'):
        checker = UpdateChecker(parent=None)
        qtbot.addWidget(checker)
        qtbot.wait(20)

    checker._set_busy(False)
    checker._on_check_finished(("99.99.99", "https://example/installer.exe", []))
    assert checker._busy is False


def test_new_check_can_start_after_watchdog_fires(qtbot, fake_user_settings):
    """After the watchdog forces recovery, the user must be able to start a
    fresh check — the menu cannot stay greyed out forever."""
    from swiss_windows_knife.components.update_checker import UpdateChecker

    with patch.object(UpdateChecker, 'check_updates'):
        checker = UpdateChecker(parent=None)
        qtbot.addWidget(checker)
        qtbot.wait(20)

    checker._set_busy(True)
    checker._interactive = False
    checker._check_watchdog()
    assert checker._busy is False

    with patch('swiss_windows_knife.components.update_checker._CheckThread') as MockThread:
        checker.check_updates(interactive=True)

    assert MockThread.called
    assert checker._busy is True
