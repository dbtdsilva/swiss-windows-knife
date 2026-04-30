import logging
import time
from collections.abc import Callable

import monitorcontrol
from PySide6.QtCore import Qt, QThread, QTimer, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QWidget

from ...base.base_widget import BaseWidget
from ...base.cancellation import Token
from ...base.config_panel import ConfigPanel
from ...base.health import HealthState
from ...base.monitor_runner import runner
from ...base.user_settings import UserSettings
from .device_listener import Device, DeviceListener, DeviceNotificationType
from .discovery import UsbWorker, list_monitors
from .monitor_info import MonitorInfoCtx

USER_SETTINGS_DISPLAY_USB_WATCHER_KEY = 'display_usb_watcher'


def USER_SETTINGS_DISPLAY_ON_CONNECT_KEY_FUNC(device_id): return f'display_on_connect_{device_id}'
def USER_SETTINGS_DISPLAY_ON_DISCONNECT_KEY_FUNC(device_id): return f'display_on_disconnect_{device_id}'


class DeviceDisplayMapperPlugin(BaseWidget):

    display_name = "Monitor input switch on USB events"

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)

        self.monitor_info_ctx = MonitorInfoCtx()
        self.user_settings = UserSettings.instance()

        logging.info(f"Starting with the {USER_SETTINGS_DISPLAY_USB_WATCHER_KEY} set to "
                     f"{self.user_settings.get_optional_str(USER_SETTINGS_DISPLAY_USB_WATCHER_KEY)}")

        self.last_changed = 0
        self.device_listener: DeviceListener | None = None

        self._usb_device_cache: list[Device] | None = None
        self._usb_fetch_subscriptions: list[tuple[Token, Callable[[list[Device]], None]]] = []
        self._usb_fetch_thread: QThread | None = None

        if self.is_enabled():
            self._start_runtime()

    def _start_runtime(self) -> None:
        """Spin up the USB watcher and warm caches. Idempotent."""
        if self.device_listener is None:
            try:
                self.device_listener = DeviceListener(self)
            except Exception as e:
                logging.exception("Failed to start device listener")
                self._set_health(HealthState.ERROR, str(e))
                return
            self.device_listener.change_detected.connect(self.device_changed)
        # Pre-warm both caches in the background so the first time the user
        # opens Configuration the panel populates instantly. Both calls
        # schedule work off the GUI thread (runner / QThread) and return
        # immediately; results land in `monitor_info_ctx` and the USB
        # cache. No-op callback because no live receiver is interested yet.
        runner().submit(self._prewarm_monitor_cache)
        self.request_usb_devices(lambda _devices: None)
        self._set_health(HealthState.OK, "Listening")

    def _stop_runtime(self) -> None:
        """Tear down the USB watcher. Pre-warmed caches stay (harmless)."""
        if self.device_listener is not None:
            self.device_listener.close()
            self.device_listener = None

    def status_changed(self, status: bool) -> None:
        if status:
            self._start_runtime()
        else:
            self._stop_runtime()

    def _prewarm_monitor_cache(self) -> None:
        try:
            list_monitors(self.monitor_info_ctx)
        except Exception:
            logging.exception("Monitor cache pre-warm failed")

    def retrieve_menus(self) -> list[QMenu | QAction]:
        return []

    def retrieve_config_panels(self) -> list[ConfigPanel]:
        from .display_automation_panel import DisplayAutomationConfigPanel
        return [DisplayAutomationConfigPanel(parent=self)]

    def request_usb_devices(self, callback: Callable[[list[Device]], None]) -> Token:
        """Provide the USB device list to `callback` on the GUI thread.

        Returns a `Token`; if the caller cancels it (e.g., from the panel's
        `destroyed` signal) the callback is suppressed even if results have
        already arrived. Cached lists are delivered via `QTimer.singleShot`
        so all paths are reliably asynchronous; cold lookups dispatch a
        single `UsbWorker` (or join an in-flight fetch). The cache is
        invalidated on every USB hot-plug event so the next request
        re-enumerates.
        """
        token = Token()
        if self._usb_device_cache is not None:
            cached = list(self._usb_device_cache)

            def _deliver_cached() -> None:
                if not token.is_cancelled:
                    callback(cached)
            QTimer.singleShot(0, _deliver_cached)
            return token

        self._usb_fetch_subscriptions.append((token, callback))
        if self._usb_fetch_thread is not None:
            return token  # already in flight; we'll fire when results land

        thread = QThread(self)
        worker = UsbWorker()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_usb_fetched, Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        # Anchor the worker against PySide6 GC: signal connections are
        # weak-ref'd, so without this the worker can be collected before
        # `started` fires and `run` would silently never execute.
        thread._usb_worker_anchor = worker  # type: ignore[attr-defined]
        thread.start()
        self._usb_fetch_thread = thread
        return token

    @Slot(list)
    def _on_usb_fetched(self, devices: list) -> None:
        self._usb_device_cache = list(devices)
        subscriptions = self._usb_fetch_subscriptions
        self._usb_fetch_subscriptions = []
        self._usb_fetch_thread = None
        for token, cb in subscriptions:
            if token.is_cancelled:
                continue
            cb(list(devices))

    @Slot(object, object)
    def device_changed(self, device_notification_type: DeviceNotificationType, usb_device: Device):
        logging.debug(f'Device change detected ({device_notification_type}): {usb_device.id}')
        # Any USB topology change invalidates the cached device list so the
        # next time the configuration panel is opened, it re-enumerates.
        self._usb_device_cache = None
        current_time = time.time()
        if current_time - self.last_changed < 1.0:
            return
        if self.user_settings.get_optional_str(USER_SETTINGS_DISPLAY_USB_WATCHER_KEY) != usb_device.id:
            return
        self.last_changed = current_time

        logging.debug(f'Matched device {usb_device.id}, changing input source on monitors')
        runner().submit(self._apply_input_source, device_notification_type)

    def _apply_input_source(self, device_notification_type: DeviceNotificationType) -> None:
        for monitor in monitorcontrol.get_monitors():
            with monitor:
                monitor_info = self.monitor_info_ctx.get_monitor_info_by_monitor(monitor)
                if monitor_info is None:
                    logging.warning('No monitor info not available')
                    continue
                device_id = monitor_info.device_id
                input_source = None
                on_connect = self.user_settings.get_optional_str(
                    USER_SETTINGS_DISPLAY_ON_CONNECT_KEY_FUNC(device_id))
                on_disconnect = self.user_settings.get_optional_str(
                    USER_SETTINGS_DISPLAY_ON_DISCONNECT_KEY_FUNC(device_id))
                logging.debug(
                    f'Monitor {device_id} with settings: '
                    f'on connect {on_connect}; on disconnect {on_disconnect}')
                if device_notification_type == DeviceNotificationType.CREATION:
                    input_source = on_connect
                elif device_notification_type == DeviceNotificationType.DELETION:
                    input_source = on_disconnect

                if input_source is not None:
                    monitor.set_input_source(input_source)  # type: ignore
                    logging.info(f'Changing monitor {monitor_info.model} ({monitor_info.device_name}) '
                                 f'input source to {input_source}')

    def closeEvent(self, event):
        if self.device_listener is not None:
            self.device_listener.close()
        event.accept()
