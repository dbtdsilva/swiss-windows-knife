from unittest.mock import patch

import pytest

from src.base.health import HealthState


@pytest.fixture
def checker(qtbot, fake_user_settings):
    from src.components.update_checker import UpdateChecker
    with patch.object(UpdateChecker, "check_updates"):
        c = UpdateChecker(parent=None)
        qtbot.addWidget(c)
    return c


def test_initial_health_is_ok_checking(checker):
    assert checker.health().state is HealthState.OK
    assert checker.health().message == "Checking…"


def test_health_warning_when_check_returns_none(checker):
    checker._busy = True
    checker._on_check_finished(None)
    assert checker.health().state is HealthState.WARNING
    assert checker.health().message == "Check failed"


def test_health_warning_when_watchdog_fires(checker):
    checker._set_busy(True)
    checker._interactive = False
    checker._check_watchdog()
    assert checker.health().state is HealthState.WARNING
    assert checker.health().message == "Check timed out"


def test_health_ok_up_to_date_when_remote_version_not_newer(checker):
    checker._busy = True
    with patch("src.components.update_checker.APP_INFO") as app_info:
        app_info.APP_VERSION = "1.0.0"
        checker._on_check_finished(("1.0.0", "https://example/installer.exe"))
    assert checker.health().state is HealthState.OK
    assert checker.health().message == "Up to date"


def test_health_ok_update_available_when_remote_newer(qtbot, fake_user_settings):
    from src.components.update_checker import UpdateChecker
    with patch.object(UpdateChecker, "check_updates"):
        c = UpdateChecker(parent=None)
        qtbot.addWidget(c)
    c._busy = True
    with patch("src.components.update_checker.APP_INFO") as app_info, \
         patch.object(c, "_confirm_update", return_value=False):
        app_info.APP_VERSION = "1.0.0"
        c._on_check_finished(("9.9.9", "https://example/installer.exe"))
    assert c.health().state is HealthState.OK
    assert c.health().message == "Update available 9.9.9"
