from __future__ import annotations

import logging
import threading
from enum import Enum
from typing import Any, TypeVar, overload

from PySide6.QtCore import QSettings

from ..app_info import APP_INFO

T = TypeVar("T")


def _coerce_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("true", "1", "yes"):
            return True
        if lowered in ("false", "0", "no"):
            return False
    return None


def _coerce_int(value: object) -> int | None:
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


def _coerce_float(value: object) -> float | None:
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


def _coerce_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text != "" else None


def _coerce_enum(enum_cls: type[Enum], value: object) -> Enum | None:
    if value is None:
        return None
    if isinstance(value, enum_cls):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text == "":
            return None
        # Legacy: settings persisted before the registry-aware serializer
        # came in were written as str(EnumCls.MEMBER) → 'EnumCls.MEMBER'.
        # Strip the class prefix so old registry entries still resolve.
        if "." in text:
            text = text.rsplit(".", 1)[-1]
        try:
            return enum_cls[text]
        except KeyError:
            return None
    return None


def _coerce(type_: type, raw: object) -> object | None:
    if type_ is bool:
        return _coerce_bool(raw)
    if type_ is int:
        return _coerce_int(raw)
    if type_ is float:
        return _coerce_float(raw)
    if type_ is str:
        return _coerce_str(raw)
    if isinstance(type_, type) and issubclass(type_, Enum):
        return _coerce_enum(type_, raw)
    raise TypeError(f"UserSettings.get: no coercer registered for type {type_!r}")


def _serialize(value: object) -> Any:
    # Enums round-trip via member name; primitives + None pass through to QSettings.
    if isinstance(value, Enum):
        return value.name
    return value


class UserSettings:

    _instance: UserSettings | None = None
    _lock = threading.Lock()

    @classmethod
    def instance(cls) -> UserSettings:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        self._settings = QSettings(APP_INFO.APP_NAME, "UserSettings")
        logging.info(f"UserSettings loaded from {self._settings.fileName()}")

    def has_key(self, key: str) -> bool:
        return self._settings.contains(key)

    def set(self, key: str, value: object) -> None:
        logging.info(f"UserSettings key '{key}' changed to {value}")
        self._settings.setValue(key, _serialize(value))

    @overload
    def get(self, key: str, type_: type[T]) -> T | None: ...

    @overload
    def get(self, key: str, type_: type[T], default: T) -> T: ...

    def get(self, key, type_, default=None):
        coerced = _coerce(type_, self._settings.value(key))
        return default if coerced is None else coerced
