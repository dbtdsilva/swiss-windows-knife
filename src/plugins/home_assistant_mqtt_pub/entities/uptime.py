import logging
import time

import psutil

from .base import SampleResult


class UptimeEntity:
    key = "uptime"
    display_name = "Uptime"
    component = "sensor"
    default_enabled = True
    default_interval_s = 60
    is_event_driven = False

    def discovery_payload(self, ctx) -> dict:
        return {
            "name": self.display_name,
            "unique_id": f"{ctx.device_id}_{self.key}",
            "object_id": f"{ctx.device_id}_{self.key}",
            "state_topic": ctx.state_topic(self.component, self.key),
            "availability_topic": ctx.availability_topic,
            "unit_of_measurement": "s",
            "icon": "mdi:timer-outline",
            "device": ctx.device_block(),
        }

    def sample(self) -> SampleResult:
        try:
            seconds = int(time.time() - psutil.boot_time())
        except Exception as exc:
            logging.debug("uptime failed: %s", exc)
            return SampleResult.unavailable(reason=str(exc))
        return SampleResult.available(value=seconds, unit="s")
