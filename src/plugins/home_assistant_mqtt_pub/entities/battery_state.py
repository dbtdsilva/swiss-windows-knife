import logging
import psutil

from .base import SampleResult


class BatteryStateEntity:
    key = "battery_state"
    display_name = "On AC power"
    component = "binary_sensor"
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
            "device_class": "plug",
            "payload_on": "ON",
            "payload_off": "OFF",
            "device": ctx.device_block(),
        }

    def sample(self) -> SampleResult:
        try:
            battery = psutil.sensors_battery()
        except Exception as exc:
            logging.debug("battery_state failed: %s", exc)
            return SampleResult.unavailable(reason=str(exc))
        if battery is None:
            return SampleResult.unavailable(reason="no battery (desktop?)")
        return SampleResult.available(value=bool(battery.power_plugged))
