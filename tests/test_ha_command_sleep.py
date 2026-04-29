from unittest.mock import MagicMock, patch

from src.plugins.home_assistant_mqtt_pub.commands.sleep_cmd import SleepCommand


def test_metadata():
    c = SleepCommand()
    assert c.key == "sleep"
    assert c.default_enabled is True


def test_run_calls_setsuspendstate():
    c = SleepCommand()
    fake = MagicMock()
    with patch("ctypes.windll", MagicMock(PowrProf=fake)):
        c.run()
    fake.SetSuspendState.assert_called_once_with(0, 0, 0)
