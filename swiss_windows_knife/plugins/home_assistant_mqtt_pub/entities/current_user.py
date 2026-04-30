import getpass
import logging

from .base import SampleResult


class CurrentUserEntity:
    key = "current_user"
    display_name = "Current user"
    component = "sensor"
    default_enabled = False  # privacy
    default_interval_s = 300
    is_event_driven = False

    def discovery_payload(self, ctx) -> dict:
        return {
            "name": self.display_name,
            "unique_id": f"{ctx.device_id}_{self.key}",
            "object_id": f"{ctx.device_id}_{self.key}",
            "state_topic": ctx.state_topic(self.component, self.key),
            "availability_topic": ctx.availability_topic,
            "icon": "mdi:account",
            "device": ctx.device_block(),
        }

    def sample(self) -> SampleResult:
        try:
            return SampleResult.available(value=getpass.getuser())
        except Exception as exc:
            logging.debug("current_user failed: %s", exc)
            return SampleResult.unavailable(reason=str(exc))
