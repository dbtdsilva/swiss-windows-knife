import logging
import threading

from PySide6.QtCore import QSettings

from ..app_info import APP_INFO


def _coerce_bool(value: object, default: bool) -> bool:
    """QSettings on Windows round-trips booleans as the literal strings
    'true' / 'false'. Accept either form, falling back to `default` for
    absent keys."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("true", "1", "yes"):
            return True
        if lowered in ("false", "0", "no"):
            return False
    if value is None:
        return default
    return bool(value)


def _coerce_optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if text == "":
            return None
        try:
            return int(text)
        except ValueError:
            try:
                return int(float(text))
            except ValueError:
                return None
    return None


def _coerce_optional_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if text == "":
            return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


class UserSettings:

    _instance: 'UserSettings | None' = None
    _lock = threading.Lock()

    @classmethod
    def instance(cls) -> 'UserSettings':
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        self._settings = QSettings(APP_INFO.APP_NAME, 'UserSettings')
        logging.info(f"UserSettings loaded from {self._settings.fileName()}")

    def has_key(self, key) -> bool:
        return self._settings.contains(key)

    def set(self, key, value) -> None:
        logging.info(f"UserSettings key '{key}' changed to {value}")
        self._settings.setValue(key, value)

    def get_bool(self, key: str, default: bool) -> bool:
        return _coerce_bool(self._settings.value(key), default)

    def get_int(self, key: str, default: int) -> int:
        out = _coerce_optional_int(self._settings.value(key))
        return default if out is None else out

    def get_optional_int(self, key: str) -> int | None:
        return _coerce_optional_int(self._settings.value(key))

    def get_float(self, key: str, default: float) -> float:
        out = _coerce_optional_float(self._settings.value(key))
        return default if out is None else out

    def get_optional_float(self, key: str) -> float | None:
        return _coerce_optional_float(self._settings.value(key))

    def get_str(self, key: str, default: str = "") -> str:
        value = self._settings.value(key)
        if value is None:
            return default
        return str(value)

    def get_optional_str(self, key: str) -> str | None:
        """Like `get_str` but returns `None` for missing or empty values,
        so callers can keep `if x is not None` semantics."""
        value = self._settings.value(key)
        if value is None:
            return None
        text = str(value)
        return text if text != "" else None
