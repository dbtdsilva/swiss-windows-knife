import logging

from PySide6.QtWidgets import QWidget

from .config_panel import ConfigPanel
from .health import HealthReport, HealthState
from .health_reporter import HealthReporter
from .user_settings import UserSettings


def _settings_key(cls: type) -> str:
    return f"plugin_enabled_{cls.__name__}"


def _coerce_bool(value: object, default: bool) -> bool:
    """QSettings on Windows returns booleans as the literal strings 'true'
    or 'false'. Accept either form, falling back to `default` for unknown."""
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


class BaseWidget(HealthReporter):

    def __init__(self, parent: QWidget | None, is_toggleable: bool = True, is_enabled: bool = True) -> None:
        super().__init__(parent)
        self._is_toggleable = is_toggleable

        settings = UserSettings.instance()
        key = _settings_key(self.__class__)
        if settings.has_key(key):
            self._is_enabled = _coerce_bool(settings.get(key), is_enabled)
        else:
            self._is_enabled = is_enabled

    def set_enabled(self, enabled: bool) -> None:
        if self._is_enabled == enabled:
            return
        self._is_enabled = enabled
        UserSettings.instance().set(_settings_key(self.__class__), enabled)
        logging.info(f'Plugin {self.__class__.__name__} is enabled: {enabled}')
        self.status_changed(enabled)
        self.health_changed.emit()

    def is_enabled(self) -> bool:
        return self._is_enabled

    def is_toggleable(self) -> bool:
        return self._is_toggleable

    def retrieve_config_panels(self) -> list[ConfigPanel]:
        return []

    def status_changed(self, status: bool) -> None:
        return None

    def health(self) -> HealthReport:
        if self._is_toggleable and not self._is_enabled:
            return HealthReport(HealthState.DISABLED, "Disabled")
        return super().health()
