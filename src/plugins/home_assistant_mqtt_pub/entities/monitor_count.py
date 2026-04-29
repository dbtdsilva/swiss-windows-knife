import logging
import threading

from src.base.monitor_runner import runner

from .base import SampleResult


class MonitorCountEntity:
    key = "monitor_count"
    display_name = "Monitor count"
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
            "icon": "mdi:monitor-multiple",
            "device": ctx.device_block(),
        }

    def sample(self) -> SampleResult:
        # Honor the CLAUDE.md rule: monitorcontrol calls go through monitor_runner.
        done = threading.Event()
        result_box: list = []

        def _do():
            try:
                import monitorcontrol
                result_box.append(len(list(monitorcontrol.get_monitors())))
            except Exception as exc:
                result_box.append(exc)
            finally:
                done.set()

        runner().submit(_do)
        if not done.wait(timeout=5.0):
            return SampleResult.unavailable(reason="monitor_runner timeout")
        value = result_box[0]
        if isinstance(value, Exception):
            logging.debug("monitor_count failed: %s", value)
            return SampleResult.unavailable(reason=str(value))
        return SampleResult.available(value=int(value))
