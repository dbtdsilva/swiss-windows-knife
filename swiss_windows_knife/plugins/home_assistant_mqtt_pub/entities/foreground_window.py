import logging

from .base import SampleResult


class ForegroundWindowEntity:
    key = "foreground_window"
    display_name = "Foreground window"
    component = "sensor"
    default_enabled = False  # privacy
    default_interval_s = 30
    is_event_driven = False

    def discovery_payload(self, ctx) -> dict:
        return {
            "name": self.display_name,
            "unique_id": f"{ctx.device_id}_{self.key}",
            "object_id": f"{ctx.device_id}_{self.key}",
            "state_topic": ctx.state_topic(self.component, self.key),
            "availability_topic": ctx.availability_topic,
            "icon": "mdi:window-maximize",
            "device": ctx.device_block(),
        }

    def sample(self) -> SampleResult:
        try:
            import win32gui
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return SampleResult.unavailable(reason="no foreground window")
            title = win32gui.GetWindowText(hwnd)
        except Exception as exc:
            logging.debug("foreground_window failed: %s", exc)
            return SampleResult.unavailable(reason=str(exc))
        if not title:
            return SampleResult.unavailable(reason="empty title")
        return SampleResult.available(value=title)
