import logging
import psutil

from .base import SampleResult


class MemoryUsageEntity:
    key = "memory_usage"
    display_name = "Memory usage"
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
            "icon": "mdi:memory",
            "device": ctx.device_block(),
        }

    def sample(self) -> SampleResult:
        try:
            return SampleResult.available(value=float(psutil.virtual_memory().percent), unit="%")
        except Exception as exc:
            logging.debug("memory_usage failed: %s", exc)
            return SampleResult.unavailable(reason=str(exc))
