from unittest.mock import patch

from src.plugins.home_assistant_mqtt_pub.device_context import DeviceContext
from src.plugins.home_assistant_mqtt_pub.entities.cpu_usage import CpuUsageEntity


def test_metadata():
    e = CpuUsageEntity()
    assert e.key == "cpu_usage"
    assert e.component == "sensor"
    assert e.default_enabled is True
    assert e.default_interval_s == 30
    assert e.is_event_driven is False


def test_sample_returns_psutil_value_as_percent():
    e = CpuUsageEntity()
    with patch("psutil.cpu_percent", return_value=12.5):
        result = e.sample()
    assert result.is_available is True
    assert result.value == 12.5
    assert result.unit == "%"


def test_sample_marks_unavailable_when_psutil_raises():
    e = CpuUsageEntity()
    with patch("psutil.cpu_percent", side_effect=OSError("nope")):
        result = e.sample()
    assert result.is_available is False


def test_discovery_payload_shape():
    e = CpuUsageEntity()
    ctx = DeviceContext(name="pc")
    payload = e.discovery_payload(ctx)
    assert payload["name"] == "CPU usage"
    assert payload["unique_id"] == "swk_pc_cpu_usage"
    assert payload["object_id"] == "swk_pc_cpu_usage"
    assert payload["state_topic"] == "homeassistant/sensor/swk_pc/cpu_usage/state"
    assert payload["availability_topic"] == "homeassistant/swk_pc/availability"
    assert payload["unit_of_measurement"] == "%"
    assert payload["device"] == ctx.device_block()


def test_registered_in_entity_list():
    from src.plugins.home_assistant_mqtt_pub.entities import build_entity_registry
    reg = build_entity_registry()
    keys = [e.key for e in reg]
    assert "cpu_usage" in keys
