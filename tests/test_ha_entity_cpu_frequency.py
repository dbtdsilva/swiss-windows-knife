from unittest.mock import patch

from src.plugins.home_assistant_mqtt_pub.device_context import DeviceContext
from src.plugins.home_assistant_mqtt_pub.entities.cpu_frequency import CpuFrequencyEntity


class _Freq:
    def __init__(self, current):
        self.current = current


def test_metadata():
    e = CpuFrequencyEntity()
    assert e.key == "cpu_frequency"
    assert e.default_interval_s == 30


def test_sample_returns_mhz():
    e = CpuFrequencyEntity()
    with patch("psutil.cpu_freq", return_value=_Freq(current=3600.0)):
        result = e.sample()
    assert result.is_available is True
    assert result.value == 3600.0
    assert result.unit == "MHz"


def test_sample_unavailable_when_psutil_returns_none():
    e = CpuFrequencyEntity()
    with patch("psutil.cpu_freq", return_value=None):
        result = e.sample()
    assert result.is_available is False


def test_discovery_payload_has_frequency_unit():
    payload = CpuFrequencyEntity().discovery_payload(DeviceContext(name="pc"))
    assert payload["unit_of_measurement"] == "MHz"
