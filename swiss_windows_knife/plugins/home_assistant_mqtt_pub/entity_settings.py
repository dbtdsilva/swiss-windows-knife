class EntitySettings:
    def __init__(self, user_settings) -> None:
        self._s = user_settings

    def is_publish_enabled(self, key: str, default: bool) -> bool:
        return self._s.get(f"homeassistant_publish_{key}", bool, default)

    def set_publish_enabled(self, key: str, value: bool) -> None:
        self._s.set(f"homeassistant_publish_{key}", value)

    def interval_s(self, key: str, default: int) -> int:
        return self._s.get(f"homeassistant_interval_{key}", int, default)

    def set_interval_s(self, key: str, seconds: int) -> None:
        self._s.set(f"homeassistant_interval_{key}", int(seconds))

    def is_command_enabled(self, key: str, default: bool) -> bool:
        return self._s.get(f"homeassistant_command_enabled_{key}", bool, default)

    def set_command_enabled(self, key: str, value: bool) -> None:
        self._s.set(f"homeassistant_command_enabled_{key}", value)

    def previous_device_name(self) -> str | None:
        return self._s.get("homeassistant_previous_device_name", str)

    def set_previous_device_name(self, name: str) -> None:
        self._s.set("homeassistant_previous_device_name", name)

    def clear_previous_device_name(self) -> None:
        self._s.set("homeassistant_previous_device_name", "")
