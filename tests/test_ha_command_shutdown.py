from unittest.mock import MagicMock, patch

from src.plugins.home_assistant_mqtt_pub.commands.shutdown import ShutdownCommand


def test_is_available_when_privilege_can_be_acquired():
    c = ShutdownCommand()
    with patch.object(ShutdownCommand, "_can_acquire_shutdown_privilege", return_value=True):
        assert c.is_available() is True


def test_is_unavailable_when_privilege_missing():
    c = ShutdownCommand()
    with patch.object(ShutdownCommand, "_can_acquire_shutdown_privilege", return_value=False):
        assert c.is_available() is False


def test_run_calls_exit_windows_ex():
    c = ShutdownCommand()
    fake_user32 = MagicMock()
    fake_user32.ExitWindowsEx.return_value = 1
    with patch.object(c, "_acquire_shutdown_privilege"), \
         patch("ctypes.windll", MagicMock(user32=fake_user32)):
        c.run()
    fake_user32.ExitWindowsEx.assert_called_once()
