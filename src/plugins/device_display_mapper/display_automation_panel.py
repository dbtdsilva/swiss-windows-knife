from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ...base.config_panel import ConfigPanel
from ...base.user_settings import UserSettings


class DisplayAutomationConfigPanel(ConfigPanel):

    title = "Display automation"

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        list_monitors: Callable[[], list[Any]] | None = None,
        list_usb_devices: Callable[[], list[Any]] | None = None,
        schedule_discovery: Callable[[Callable[[], None]], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._user_settings = UserSettings.instance()
        self._list_monitors = list_monitors
        self._list_usb_devices = list_usb_devices
        self._schedule = schedule_discovery or (lambda fn: fn())

        self._monitors: list[Any] = []
        self._usb_devices: list[Any] = []

        self._layout = QVBoxLayout(self)
        self._placeholder = QLabel("Reading monitor capabilities…", self)
        self._layout.addWidget(self._placeholder)

        self._monitor_groups: dict[str, dict] = {}
        self._usb_combo = None

        if list_monitors is not None or list_usb_devices is not None:
            self._schedule(self._populate)

    def _populate(self) -> None:
        self._monitors = list(self._list_monitors()) if self._list_monitors else []
        self._usb_devices = list(self._list_usb_devices()) if self._list_usb_devices else []
        # Widgets are added in Task 5; for now the placeholder stays.

    def apply(self) -> bool:
        return True
