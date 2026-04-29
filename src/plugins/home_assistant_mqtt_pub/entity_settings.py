from typing import Any


def _coerce_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("1", "true", "yes")
    return bool(value)


def _coerce_int(value: Any, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class EntitySettings:
    def __init__(self, user_settings) -> None:
        self._s = user_settings

    def is_publish_enabled(self, key: str, default: bool) -> bool:
        return _coerce_bool(self._s.get(f"homeassistant_publish_{key}"), default)

    def set_publish_enabled(self, key: str, value: bool) -> None:
        self._s.set(f"homeassistant_publish_{key}", value)

    def interval_s(self, key: str, default: int) -> int:
        return _coerce_int(self._s.get(f"homeassistant_interval_{key}"), default)

    def set_interval_s(self, key: str, seconds: int) -> None:
        self._s.set(f"homeassistant_interval_{key}", int(seconds))

    def is_command_enabled(self, key: str, default: bool) -> bool:
        return _coerce_bool(self._s.get(f"homeassistant_command_enabled_{key}"), default)

    def set_command_enabled(self, key: str, value: bool) -> None:
        self._s.set(f"homeassistant_command_enabled_{key}", value)

    def previous_device_name(self) -> str | None:
        value = self._s.get("homeassistant_previous_device_name")
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        return str(value)

    def set_previous_device_name(self, name: str) -> None:
        self._s.set("homeassistant_previous_device_name", name)

    def clear_previous_device_name(self) -> None:
        self._s.set("homeassistant_previous_device_name", "")
