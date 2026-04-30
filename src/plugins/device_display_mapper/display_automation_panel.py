from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import QComboBox, QFormLayout, QGroupBox, QLabel, QVBoxLayout, QWidget

from ...base.config_panel import ConfigPanel
from ...base.user_settings import UserSettings

USB_WATCHER_KEY = 'display_usb_watcher'
ON_CONNECT_KEY_PREFIX = 'display_on_connect_'
ON_DISCONNECT_KEY_PREFIX = 'display_on_disconnect_'

UNCHANGED_LABEL = "(unchanged)"


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
        self._usb_combo: QComboBox | None = None

        if list_monitors is not None or list_usb_devices is not None:
            self._schedule(self._populate)

    def _populate(self) -> None:
        self._monitors = list(self._list_monitors()) if self._list_monitors else []
        self._usb_devices = list(self._list_usb_devices()) if self._list_usb_devices else []

        self._placeholder.hide()
        self._build_usb_section()
        for info in self._monitors:
            self._build_monitor_section(info)

    def _build_monitor_section(self, info) -> None:
        box = QGroupBox(f"{info.model} ({info.device_name})", self)
        form = QFormLayout(box)

        connect_combo = self._make_input_combo(info.inputs, info.device_id, ON_CONNECT_KEY_PREFIX, box)
        disconnect_combo = self._make_input_combo(info.inputs, info.device_id, ON_DISCONNECT_KEY_PREFIX, box)

        form.addRow("On USB connect:", connect_combo)
        form.addRow("On USB disconnect:", disconnect_combo)

        self._monitor_groups[info.device_id] = {
            "connect_combo": connect_combo,
            "disconnect_combo": disconnect_combo,
        }
        self._layout.addWidget(box)

    def _make_input_combo(self, inputs, device_id, key_prefix, parent) -> QComboBox:
        combo = QComboBox(parent)
        combo.addItem(UNCHANGED_LABEL, userData=None)
        for entry in inputs:
            combo.addItem(str(entry), userData=entry)

        current = self._user_settings.get(key_prefix + device_id)
        if current is not None:
            for i in range(combo.count()):
                if str(combo.itemData(i)) == str(current):
                    combo.setCurrentIndex(i)
                    break
        return combo

    def _build_usb_section(self) -> None:
        box = QGroupBox("USB trigger for display switch", self)
        form = QFormLayout(box)

        combo = QComboBox(box)
        combo.addItem("(none)", userData=None)
        for device in self._usb_devices:
            label = f"{device.name} ({device.id})"
            combo.addItem(label, userData=device.id)

        current = self._user_settings.get(USB_WATCHER_KEY)
        if current is not None:
            for i in range(combo.count()):
                if combo.itemData(i) == current:
                    combo.setCurrentIndex(i)
                    break

        form.addRow("Watch:", combo)
        self._usb_combo = combo
        self._layout.addWidget(box)

    def apply(self) -> bool:
        if self._usb_combo is not None:
            self._user_settings.set(USB_WATCHER_KEY, self._usb_combo.currentData())
        for device_id, widgets in self._monitor_groups.items():
            for key_prefix, combo_key in (
                (ON_CONNECT_KEY_PREFIX, "connect_combo"),
                (ON_DISCONNECT_KEY_PREFIX, "disconnect_combo"),
            ):
                data = widgets[combo_key].currentData()
                if data is None:
                    # "(unchanged)" — leave existing setting alone.
                    continue
                self._user_settings.set(key_prefix + device_id, data)
        return True
