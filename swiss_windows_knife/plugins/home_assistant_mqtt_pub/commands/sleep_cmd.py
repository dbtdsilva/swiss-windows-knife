import logging


class SleepCommand:
    key = "sleep"
    display_name = "Sleep"
    default_enabled = True

    def is_available(self) -> bool:
        return True

    def discovery_payload(self, ctx) -> dict:
        return {
            "name": self.display_name,
            "unique_id": f"{ctx.device_id}_{self.key}",
            "object_id": f"{ctx.device_id}_{self.key}",
            "command_topic": ctx.command_topic(self.key),
            "availability_topic": ctx.availability_topic,
            "icon": "mdi:power-sleep",
            "device": ctx.device_block(),
        }

    def run(self) -> None:
        try:
            import ctypes
            ctypes.windll.PowrProf.SetSuspendState(0, 0, 0)
        except Exception:
            logging.exception("SetSuspendState failed")
