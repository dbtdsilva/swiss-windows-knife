from unittest.mock import MagicMock, patch

from src.plugins.home_assistant_mqtt_pub.device_context import DeviceContext
from src.plugins.home_assistant_mqtt_pub.entities.cpu_temperature import CpuTemperatureEntity


def _zone(kelvin_tenths):
    z = MagicMock()
    z.CurrentTemperature = kelvin_tenths
    return z


def test_metadata():
    e = CpuTemperatureEntity()
    assert e.key == "cpu_temperature"
    assert e.component == "sensor"
    assert e.default_enabled is True
    assert e.default_interval_s == 30


def test_sample_converts_acpi_kelvin_tenths_to_celsius():
    e = CpuTemperatureEntity()
    fake = MagicMock()
    fake.MSAcpi_ThermalZoneTemperature.return_value = [_zone(3132)]  # 313.2K = 40.05C
    with patch("wmi.WMI", return_value=fake):
        result = e.sample()
    assert result.is_available is True
    assert round(result.value, 1) == 40.1
    assert result.unit == "°C"


def test_sample_unavailable_when_no_zones():
    e = CpuTemperatureEntity()
    fake = MagicMock()
    fake.MSAcpi_ThermalZoneTemperature.return_value = []
    with patch("wmi.WMI", return_value=fake):
        result = e.sample()
    assert result.is_available is False


def test_sample_unavailable_when_wmi_raises():
    e = CpuTemperatureEntity()
    with patch("wmi.WMI", side_effect=OSError("nope")):
        result = e.sample()
    assert result.is_available is False


def test_discovery_payload_has_temperature_class():
    e = CpuTemperatureEntity()
    payload = e.discovery_payload(DeviceContext(name="pc"))
    assert payload["device_class"] == "temperature"
    assert payload["unit_of_measurement"] == "°C"
