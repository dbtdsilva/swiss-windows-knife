from unittest.mock import MagicMock, patch

from src.plugins.home_assistant_mqtt_pub.entities.memory_usage import MemoryUsageEntity


def test_sample_returns_percent():
    e = MemoryUsageEntity()
    fake = MagicMock(percent=42.0)
    with patch("psutil.virtual_memory", return_value=fake):
        result = e.sample()
    assert result.is_available is True
    assert result.value == 42.0
    assert result.unit == "%"
