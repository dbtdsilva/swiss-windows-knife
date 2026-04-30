import logging
import time
from collections.abc import Callable

import monitorcontrol
from PySide6.QtCore import Qt, QThread, QTimer, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QWidget

from ...base.base_widget import BaseWidget
from ...base.config_panel import ConfigPanel
from ...base.monitor_runner import runner
from ...base.user_settings import UserSettings
from .device_listener import Device, DeviceListener, DeviceNotificationType
from .discovery import UsbWorker
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
                     f"{self.user_settings.get(USER_SETTINGS_DISPLAY_USB_WATCHER_KEY)}")

        self.last_changed = 0
        self.device_listener = DeviceListener(self)
        self.device_listener.change_detected.connect(self.device_changed)

        self._usb_device_cache: list[Device] | None = None
        self._usb_fetch_callbacks: list[Callable[[list[Device]], None]] = []
        self._usb_fetch_thread: QThread | None = None

    def retrieve_menus(self) -> list[QMenu | QAction]:
        return []

    def retrieve_config_panels(self) -> list[ConfigPanel]:
        from .display_automation_panel import DisplayAutomationConfigPanel
        return [DisplayAutomationConfigPanel(parent=self)]

    def request_usb_devices(self, callback: Callable[[list[Device]], None]) -> None:
        """Provide the USB device list to `callback` on the GUI thread.

        Returns the cached list immediately (via a 0-ms QTimer to keep
        delivery asynchronous and predictable for callers). Otherwise
        dispatches a single `UsbWorker` on its own QThread (or joins an
        in-flight fetch) and fires every queued callback when results
        arrive. Cache is invalidated on every USB hot-plug event so the
        next request re-enumerates.
        """
        if self._usb_device_cache is not None:
            cached = list(self._usb_device_cache)
            QTimer.singleShot(0, lambda: callback(cached))
            return

        self._usb_fetch_callbacks.append(callback)
        if self._usb_fetch_thread is not None:
            return  # already in flight; will fire all callbacks when done

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

    @Slot(list)
    def _on_usb_fetched(self, devices: list) -> None:
        self._usb_device_cache = list(devices)
        callbacks = self._usb_fetch_callbacks
        self._usb_fetch_callbacks = []
        self._usb_fetch_thread = None
        for cb in callbacks:
            try:
                cb(list(devices))
            except Exception:
                logging.exception("USB fetch callback failed")

    @Slot(object, object)
    def device_changed(self, device_notification_type: DeviceNotificationType, usb_device: Device):
        logging.debug(f'Device change detected ({device_notification_type}): {usb_device.id}')
        # Any USB topology change invalidates the cached device list so the
        # next time the configuration panel is opened, it re-enumerates.
        self._usb_device_cache = None
        current_time = time.time()
        if current_time - self.last_changed < 1.0:
            return
        if self.user_settings.get(USER_SETTINGS_DISPLAY_USB_WATCHER_KEY) != usb_device.id:
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
                logging.debug(
                    f'Monitor {device_id} with settings: '
                    f'on connect {self.user_settings.get(USER_SETTINGS_DISPLAY_ON_CONNECT_KEY_FUNC(device_id))}; '
                    f'on disconnect {self.user_settings.get(USER_SETTINGS_DISPLAY_ON_DISCONNECT_KEY_FUNC(device_id))}')
                if device_notification_type == DeviceNotificationType.CREATION:
                    input_source = self.user_settings.get(USER_SETTINGS_DISPLAY_ON_CONNECT_KEY_FUNC(device_id))
                elif device_notification_type == DeviceNotificationType.DELETION:
                    input_source = self.user_settings.get(USER_SETTINGS_DISPLAY_ON_DISCONNECT_KEY_FUNC(device_id))

                if input_source is not None:
                    monitor.set_input_source(input_source)  # type: ignore
                    logging.info(f'Changing monitor {monitor_info.model} ({monitor_info.device_name}) '
                                 f'input source to {input_source}')

    def closeEvent(self, event):
        self.device_listener.close()
        event.accept()
