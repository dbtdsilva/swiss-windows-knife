import logging

import psutil

from .base import SampleResult


class CpuFrequencyEntity:
    key = "cpu_frequency"
    display_name = "CPU frequency"
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
            "unit_of_measurement": "MHz",
            "icon": "mdi:speedometer",
            "device": ctx.device_block(),
        }

    def sample(self) -> SampleResult:
        try:
            freq = psutil.cpu_freq()
        except Exception as exc:
            logging.debug("cpu_frequency failed: %s", exc)
            return SampleResult.unavailable(reason=str(exc))
        if freq is None or freq.current in (None, 0):
            return SampleResult.unavailable(reason="psutil returned no frequency")
        return SampleResult.available(value=float(freq.current), unit="MHz")
