import logging
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QComboBox, QFormLayout, QGroupBox, QLabel, QVBoxLayout, QWidget

from ...base.config_panel import ConfigPanel
from ...base.monitor_runner import runner
from ...base.user_settings import UserSettings
from .discovery import list_monitors as _list_monitors_default

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
        self._cleanup_callbacks: list[Callable[[], None]] = []

        if schedule_discovery is not None:
            schedule_discovery(self._populate)
        elif list_monitors is not None or list_usb_devices is not None:
            # Test path with explicit fakes — populate inline.
            self._populate()
        else:
            # Production: parent must be the plugin so we can reach its
            # monitor_info_ctx and device_listener.
            _default_schedule(self, parent)

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

    def cleanup(self) -> None:
        for cb in self._cleanup_callbacks:
            cb()
        self._cleanup_callbacks.clear()


class _DiscoveryBridge(QObject):
    """Marshals discovery results from the runner / worker threads back to GUI.

    Parented to the long-lived plugin (not the panel) so workers can always
    emit on it without RuntimeError. When the panel dies, the bridge nulls
    its panel reference, drops any not-yet-arrived results, and self-deletes
    once both work paths have settled. Token cancellation at the runner
    queue level skips queued (but not-yet-started) work to avoid wasting
    cycles on results nobody will use.
    """

    monitors_ready = Signal(list)

    def __init__(self, panel: "DisplayAutomationConfigPanel", plugin: QObject) -> None:
        super().__init__(plugin)
        self._panel: DisplayAutomationConfigPanel | None = panel
        self._monitors: list | None = None
        self._usb: list | None = None
        self._monitor_pending = True
        self._usb_pending = True
        self._monitor_token = None
        self._usb_token = None
        self.monitors_ready.connect(self._on_monitors, Qt.ConnectionType.QueuedConnection)
        # `panel.destroyed` fires synchronously inside the panel's destructor
        # on the GUI thread; bridge stays alive to absorb in-flight results.
        panel.destroyed.connect(self._on_panel_destroyed)

    def attach_tokens(self, monitor_token, usb_token) -> None:
        self._monitor_token = monitor_token
        self._usb_token = usb_token

    def _on_panel_destroyed(self) -> None:
        self._panel = None
        if self._monitor_token is not None:
            self._monitor_token.cancel()
        if self._usb_token is not None:
            self._usb_token.cancel()
        self._reap_if_settled()

    def _on_monitors(self, monitors: list) -> None:
        self._monitors = monitors
        self._monitor_pending = False
        self._maybe_finalize()
        self._reap_if_settled()

    def _on_usb(self, devices: list) -> None:
        self._usb = devices
        self._usb_pending = False
        self._maybe_finalize()
        self._reap_if_settled()

    def _maybe_finalize(self) -> None:
        if self._panel is None:
            return
        if self._monitors is None or self._usb is None:
            return
        self._panel._monitors = self._monitors
        self._panel._usb_devices = self._usb
        self._panel._placeholder.hide()
        self._panel._build_usb_section()
        for info in self._panel._monitors:
            self._panel._build_monitor_section(info)

    def _reap_if_settled(self) -> None:
        if self._panel is None and not self._monitor_pending and not self._usb_pending:
            self.deleteLater()


def _default_schedule(panel: "DisplayAutomationConfigPanel", plugin) -> None:
    """Real-world scheduler: monitor discovery on `runner()`, USB via the
    plugin's cached `request_usb_devices`. Bridge is parented to the plugin
    so it outlives the panel; tokens cancel queued-but-unstarted work when
    the panel goes away; in-flight work is allowed to complete and is then
    silently dropped by the bridge.
    """
    bridge = _DiscoveryBridge(panel, plugin)

    def _read_monitors() -> None:
        try:
            monitors = _list_monitors_default(plugin.monitor_info_ctx)
        except Exception:
            logging.exception("Monitor discovery failed")
            monitors = []
        bridge.monitors_ready.emit(monitors)

    monitor_token = runner().submit(_read_monitors)
    usb_token = plugin.request_usb_devices(bridge._on_usb)
    bridge.attach_tokens(monitor_token, usb_token)
    panel._cleanup_callbacks.append(lambda: (monitor_token.cancel(), usb_token.cancel()))
