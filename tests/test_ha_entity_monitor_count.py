from unittest.mock import MagicMock, patch

from swiss_windows_knife.plugins.home_assistant_mqtt_pub.entities.monitor_count import MonitorCountEntity


def test_sample_returns_monitor_count_via_runner():
    e = MonitorCountEntity()

    captured = {}

    class _RunnerSpy:
        def submit(self, fn, *args, **kwargs):
            captured["fn"] = fn
            # Run synchronously for the test.
            fn(*args, **kwargs)

    runner_path = "swiss_windows_knife.plugins.home_assistant_mqtt_pub.entities.monitor_count.runner"
    with patch(runner_path, return_value=_RunnerSpy()), \
         patch("monitorcontrol.get_monitors", return_value=[MagicMock(), MagicMock(), MagicMock()]):
        result = e.sample()
    assert result.is_available is True
    assert result.value == 3
