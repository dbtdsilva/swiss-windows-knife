from unittest.mock import patch

from swiss_windows_knife.plugins.home_assistant_mqtt_pub.entities.uptime import UptimeEntity


def test_sample_returns_seconds_since_boot():
    e = UptimeEntity()
    with patch("time.time", return_value=1_000_000.0), \
         patch("psutil.boot_time", return_value=999_500.0):
        result = e.sample()
    assert result.is_available is True
    assert result.value == 500
    assert result.unit == "s"


def test_default_interval_60s():
    assert UptimeEntity().default_interval_s == 60
