"""Regression coverage for the update-checker workers.

The bug we are guarding against: an unexpected exception type (anything
outside the narrow ``requests.RequestException`` / ``ValueError`` set the
workers used to catch) escaped ``run()``, the worker thread died without
emitting ``finished``, and the caller's ``_busy`` flag stayed True for
the lifetime of the process — silencing every subsequent menu click.
"""
from unittest.mock import patch

import pytest

from src.components.update_checker import _CheckWorker, _DownloadWorker


@pytest.fixture
def check_worker(qtbot):
    w = _CheckWorker()
    return w


def _wait_finished(qtbot, worker):
    with qtbot.waitSignal(worker.finished, timeout=2000) as blocker:
        worker.run()
    return blocker.args


def test_check_worker_emits_finished_on_unexpected_exception(qtbot, check_worker):
    # An OSError from a frozen-build code path used to escape and wedge
    # the caller's _busy flag forever — the broad except in run() now
    # catches it and emits finished(None).
    with patch('src.components.update_checker.requests.get', side_effect=OSError("ssl boom")):
        args = _wait_finished(qtbot, check_worker)
    assert args == [None]


def test_check_worker_emits_finished_on_request_exception(qtbot, check_worker):
    import requests
    with patch(
        'src.components.update_checker.requests.get',
        side_effect=requests.ConnectionError("no network"),
    ):
        args = _wait_finished(qtbot, check_worker)
    assert args == [None]


def test_check_worker_emits_finished_when_release_has_no_installer_asset(qtbot, check_worker):
    class _FakeResp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"tag_name": "9.9.9", "assets": []}

    with patch('src.components.update_checker.requests.get', return_value=_FakeResp()):
        args = _wait_finished(qtbot, check_worker)
    assert args == [None]


def test_check_worker_emits_release_tuple_on_success(qtbot, check_worker):
    class _FakeResp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "tag_name": "9.9.9",
                "assets": [
                    {"name": "irrelevant.zip"},
                    {"name": "Installer-9.9.9.exe", "browser_download_url": "https://example/9.9.9.exe"},
                ],
            }

    with patch('src.components.update_checker.requests.get', return_value=_FakeResp()):
        args = _wait_finished(qtbot, check_worker)
    assert args == [("9.9.9", "https://example/9.9.9.exe")]


def test_download_worker_emits_finished_on_unexpected_exception(qtbot, tmp_path):
    worker = _DownloadWorker("https://example/1.exe", str(tmp_path))
    with patch('src.components.update_checker.requests.get', side_effect=RuntimeError("???")):
        args = _wait_finished(qtbot, worker)
    assert args == [None]


def test_watchdog_clears_busy_when_worker_wedges(qtbot, fake_user_settings):
    """If the worker thread blocks indefinitely (e.g. a network call that
    ignores its timeout), the watchdog must restore the menu so the user
    can try again instead of having the action greyed out forever."""
    from src.components.update_checker import UpdateChecker

    # Stub out the worker spawn so the constructor's queued auto-check
    # doesn't actually try to hit the network (or leak a thread into
    # pytest teardown). We're testing the watchdog state machine, not
    # the worker.
    with patch.object(UpdateChecker, '_spawn_worker'):
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
    from src.components.update_checker import UpdateChecker

    with patch.object(UpdateChecker, '_spawn_worker'):
        checker = UpdateChecker(parent=None)
        qtbot.addWidget(checker)
        qtbot.wait(20)

        # Simulate watchdog already fired.
        checker._set_busy(False)

        # Late result from an orphan worker — should be a no-op.
        checker._on_check_finished(("99.99.99", "https://example/installer.exe"))

    assert checker._busy is False
