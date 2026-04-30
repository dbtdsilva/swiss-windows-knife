from unittest.mock import MagicMock, patch

from swiss_windows_knife.plugins.home_assistant_mqtt_pub.commands.lock import LockCommand
from swiss_windows_knife.plugins.home_assistant_mqtt_pub.device_context import DeviceContext


def test_metadata():
    c = LockCommand()
    assert c.key == "lock"
    assert c.default_enabled is True
    assert c.is_available() is True


def test_run_calls_lockworkstation():
    c = LockCommand()
    fake = MagicMock()
    with patch("ctypes.windll", MagicMock(user32=fake)):
        c.run()
    fake.LockWorkStation.assert_called_once()


def test_discovery_payload_is_button():
    c = LockCommand()
    payload = c.discovery_payload(DeviceContext(name="pc"))
    assert payload["command_topic"] == "homeassistant/button/swk_pc/lock/set"
    assert payload["unique_id"] == "swk_pc_lock"
    assert payload["device"]["identifiers"] == ["swk_pc"]
