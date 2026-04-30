import logging

from PySide6.QtWidgets import QWidget

from .config_panel import ConfigPanel
from .health import HealthReport, HealthState
from .health_reporter import HealthReporter
from .user_settings import UserSettings


def _settings_key(cls: type) -> str:
    return f"plugin_enabled_{cls.__name__}"


class BaseWidget(HealthReporter):

    def __init__(self, parent: QWidget | None, is_toggleable: bool = True, is_enabled: bool = True) -> None:
        super().__init__(parent)
        self._is_toggleable = is_toggleable

        settings = UserSettings.instance()
        self._is_enabled = settings.get_bool(_settings_key(self.__class__), is_enabled)

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
