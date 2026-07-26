from unittest.mock import MagicMock, patch

import pytest

from swiss_windows_knife.base.health import HealthState


@pytest.fixture
def checker(qtbot, fake_user_settings):
    from swiss_windows_knife.components.update_checker import UpdateChecker
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
    from unittest.mock import MagicMock
    checker._set_busy(True)
    checker._interactive = False
    fake_thread = MagicMock()
    fake_thread.isFinished.return_value = False
    checker._check_watchdog(fake_thread)
    assert checker.health().state is HealthState.WARNING
    assert checker.health().message == "Check timed out"


def test_health_ok_up_to_date_when_remote_version_not_newer(checker):
    checker._busy = True
    with patch("swiss_windows_knife.components.update_checker.APP_INFO") as app_info:
        app_info.APP_VERSION = "1.0.0"
        checker._on_check_finished(("1.0.0", "https://example/installer.exe", []))
    assert checker.health().state is HealthState.OK
    assert checker.health().message == "Up to date"


def test_health_ok_update_available_when_remote_newer(qtbot, fake_user_settings):
    from swiss_windows_knife.components.update_checker import UpdateChecker
    with patch.object(UpdateChecker, "check_updates"):
        c = UpdateChecker(parent=None)
        qtbot.addWidget(c)
    c._busy = True
    with patch("swiss_windows_knife.components.update_checker.APP_INFO") as app_info, \
         patch.object(c, "_confirm_update", return_value=False):
        app_info.APP_VERSION = "1.0.0"
        c._on_check_finished(("9.9.9", "https://example/installer.exe", [("9.9.9", "notes")]))
    assert c.health().state is HealthState.OK
    assert c.health().message == "Update available 9.9.9"


def test_auto_mode_skips_dialog_and_downloads(qtbot, fake_user_settings):
    from swiss_windows_knife.components.update_checker import UpdateChecker
    fake_user_settings.set('update_automatic', True)
    with patch.object(UpdateChecker, "check_updates"):
        c = UpdateChecker(parent=None)
        qtbot.addWidget(c)
    c._busy = True
    with patch("swiss_windows_knife.components.update_checker.APP_INFO") as app_info, \
         patch.object(c, "_confirm_update") as confirm, \
         patch.object(c, "_start_download") as start_dl:
        app_info.APP_NAME = "SWK"
        app_info.APP_VERSION = "1.0.0"
        with qtbot.waitSignal(c.notification_requested, timeout=500):
            c._on_check_finished(
                ("2.0.0", "https://example/2.0.0.exe", [("2.0.0", "notes")]))
    confirm.assert_not_called()
    start_dl.assert_called_once_with("https://example/2.0.0.exe")


def test_auto_mode_ignores_skip_version(qtbot, fake_user_settings):
    from swiss_windows_knife.components.update_checker import UpdateChecker
    fake_user_settings.set('update_automatic', True)
    fake_user_settings.set('update_skip_version', "2.0.0")
    with patch.object(UpdateChecker, "check_updates"):
        c = UpdateChecker(parent=None)
        qtbot.addWidget(c)
    c._busy = True
    with patch("swiss_windows_knife.components.update_checker.APP_INFO") as app_info, \
         patch.object(c, "_start_download") as start_dl:
        app_info.APP_NAME = "SWK"
        app_info.APP_VERSION = "1.0.0"
        c._on_check_finished(("2.0.0", "https://example/2.0.0.exe", []))
    start_dl.assert_called_once_with("https://example/2.0.0.exe")


def test_manual_mode_calls_dialog_and_downloads_on_accept(qtbot, fake_user_settings):
    from swiss_windows_knife.components.update_checker import UpdateChecker
    with patch.object(UpdateChecker, "check_updates"):
        c = UpdateChecker(parent=None)
        qtbot.addWidget(c)
    c._busy = True
    with patch("swiss_windows_knife.components.update_checker.APP_INFO") as app_info, \
         patch.object(c, "_confirm_update", return_value=True) as confirm, \
         patch.object(c, "_start_download") as start_dl:
        app_info.APP_VERSION = "1.0.0"
        c._on_check_finished(
            ("2.0.0", "https://example/2.0.0.exe", [("2.0.0", "n")]))
    confirm.assert_called_once_with("2.0.0", [("2.0.0", "n")])
    start_dl.assert_called_once_with("https://example/2.0.0.exe")


def test_confirm_update_skips_prompt_when_version_skipped(qtbot, fake_user_settings):
    from swiss_windows_knife.components.update_checker import UpdateChecker
    with patch.object(UpdateChecker, "check_updates"):
        c = UpdateChecker(parent=None)
        qtbot.addWidget(c)
    fake_user_settings.set('update_skip_version', "2.0.0")
    with patch("swiss_windows_knife.components.update_checker.UpdatePromptDialog") as D:
        result = c._confirm_update("2.0.0", [])
    assert result is False
    D.assert_not_called()


def test_confirm_update_stores_skip_on_decline_with_checkbox(qtbot, fake_user_settings):
    from PySide6.QtWidgets import QDialog

    from swiss_windows_knife.components.update_checker import UpdateChecker
    with patch.object(UpdateChecker, "check_updates"):
        c = UpdateChecker(parent=None)
        qtbot.addWidget(c)
    fake_dialog = MagicMock()
    fake_dialog.exec.return_value = QDialog.DialogCode.Rejected
    fake_dialog.skip_checked.return_value = True
    with patch("swiss_windows_knife.components.update_checker.UpdatePromptDialog",
               return_value=fake_dialog):
        result = c._confirm_update("2.0.0", [])
    assert result is False
    assert fake_user_settings.get('update_skip_version', str, "") == "2.0.0"
