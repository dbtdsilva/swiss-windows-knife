import re

from ...app_info import APP_INFO


_STRIP_RE = re.compile(r"[^a-z0-9\s\-_]")
_SEP_RE = re.compile(r"[\s\-_]+")


def slugify(value: str) -> str:
    lowered = value.strip().lower()
    stripped = _STRIP_RE.sub("", lowered)
    cleaned = _SEP_RE.sub("_", stripped).strip("_")
    if not cleaned:
        raise ValueError("slugify produced an empty string")
    return cleaned


class DeviceContext:
    def __init__(self, name: str) -> None:
        self.name = name.strip()
        self.device_id = f"swk_{slugify(name)}"

    def state_topic(self, component: str, entity_key: str) -> str:
        return f"homeassistant/{component}/{self.device_id}/{entity_key}/state"

    def discovery_topic(self, component: str, entity_key: str) -> str:
        return f"homeassistant/{component}/{self.device_id}/{entity_key}/config"

    @property
    def availability_topic(self) -> str:
        return f"homeassistant/{self.device_id}/availability"

    def command_topic(self, command_key: str) -> str:
        return f"homeassistant/button/{self.device_id}/{command_key}/set"

    def device_block(self) -> dict:
        return {
            "identifiers": [self.device_id],
            "name": self.name,
            "manufacturer": f"Swiss Windows Knife by {APP_INFO.APP_AUTHOR}",
            "model": "Windows host",
            "sw_version": APP_INFO.APP_VERSION,
        }
