import logging
import psutil

from .base import SampleResult


class CpuUsageEntity:
    key = "cpu_usage"
    display_name = "CPU usage"
    component = "sensor"
    default_enabled = True
    default_interval_s = 30
    is_event_driven = False

    def discovery_payload(self, ctx) -> dict:
        return {
            "name": self.display_name,
            "unique_id": f"{ctx.device_id}_{self.key}",
            "object_id": f"{ctx.device_id}_{self.key}",
            "state_topic": ctx.state_topic(self.component, self.key),
            "availability_topic": ctx.availability_topic,
            "unit_of_measurement": "%",
            "icon": "mdi:cpu-64-bit",
            "device": ctx.device_block(),
        }

    def sample(self) -> SampleResult:
        try:
            value = float(psutil.cpu_percent(interval=None))
        except Exception as exc:
            logging.debug("cpu_usage sample failed: %s", exc)
            return SampleResult.unavailable(reason=str(exc))
        return SampleResult.available(value=value, unit="%")
