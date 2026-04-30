from unittest.mock import MagicMock, patch

from swiss_windows_knife.plugins.home_assistant_mqtt_pub.entities.battery_state import BatteryStateEntity


def test_sample_on_ac():
    e = BatteryStateEntity()
    fake = MagicMock(power_plugged=True)
    with patch("psutil.sensors_battery", return_value=fake):
        result = e.sample()
    assert result.is_available is True
    assert result.value is True


def test_sample_on_battery():
    e = BatteryStateEntity()
    fake = MagicMock(power_plugged=False)
    with patch("psutil.sensors_battery", return_value=fake):
        result = e.sample()
    assert result.value is False


def test_sample_none_on_desktop():
    e = BatteryStateEntity()
    with patch("psutil.sensors_battery", return_value=None):
        result = e.sample()
    assert result.is_available is False


def test_metadata_is_binary_sensor_with_plug_class():
    from swiss_windows_knife.plugins.home_assistant_mqtt_pub.device_context import DeviceContext
    e = BatteryStateEntity()
    assert e.component == "binary_sensor"
    payload = e.discovery_payload(DeviceContext(name="pc"))
    assert payload["device_class"] == "plug"
    assert payload["payload_on"] == "ON" and payload["payload_off"] == "OFF"
