from functools import partial
import time

from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QMenu, QWidget
from PySide6.QtCore import Slot

from .monitor_info import MonitorInfo
from .device_listener import DeviceListener, DeviceNotificationType, Device
from ...base.base_widget import BaseWidget
from ...base.user_settings import UserSettings

import monitorcontrol
import logging
from win32api import EnumDisplayDevices, EnumDisplayMonitors, GetMonitorInfo


USER_SETTINGS_DISPLAY_USB_WATCHER_KEY = 'display_usb_watcher'


def USER_SETTINGS_DISPLAY_ON_CONNECT_KEY_FUNC(device_id): return f'display_on_connect_{device_id}'
def USER_SETTINGS_DISPLAY_ON_DISCONNECT_KEY_FUNC(device_id): return f'display_on_disconnect_{device_id}'


class DeviceDisplayMapperPlugin(BaseWidget):

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)

        self.user_settings = UserSettings.instance()
        self.load_inputs_per_monitor()

        logging.info(f"Starting with the {USER_SETTINGS_DISPLAY_USB_WATCHER_KEY} set to "
                     f"{self.user_settings.get(USER_SETTINGS_DISPLAY_USB_WATCHER_KEY)}")

        self.last_process = 0
        self.device_listener = DeviceListener(self)
        self.device_listener.change_detected.connect(self.device_changed)

    def load_inputs_per_monitor(self):
        logging.info('Getting monitors information')

        monitor_hmon_device_id = {}
        for hmon, _, _ in EnumDisplayMonitors(None, None):
            info = GetMonitorInfo(hmon)     # type: ignore
            dev = EnumDisplayDevices(info['Device'], 0, 1)
            monitor_hmon_device_id[int(hmon)] = (dev.DeviceID, dev.DeviceName)    # type: ignore

        self.input_per_monitor: dict[int, MonitorInfo] = {}
        for monitor in monitorcontrol.get_monitors():
            with monitor:
                capabilities = monitor.get_vcp_capabilities()
                hmon = monitor.vcp.hmonitor.value   # type: ignore
                device_id, device_name = monitor_hmon_device_id[hmon]
                self.input_per_monitor[hmon] = MonitorInfo(device_id,
                                                           device_name,
                                                           capabilities['model'],
                                                           capabilities['inputs'])

                logging.info(f"Display ({capabilities['model']} {device_name}) will change input to on USB connect: "
                             f"{self.user_settings.get(USER_SETTINGS_DISPLAY_ON_CONNECT_KEY_FUNC(device_id))}")
                logging.info(f"Display ({capabilities['model']} {device_name}) will change input to on USB disconnect: "
                             f"{self.user_settings.get(USER_SETTINGS_DISPLAY_ON_DISCONNECT_KEY_FUNC(device_id))}")

    def retrieve_menus(self) -> list[QMenu | QAction]:
        menu = QMenu('Display automation', self)

        sub_menus = []
        for _, monitor_info in self.input_per_monitor.items():
            monitor_label = f'{monitor_info.model} ({monitor_info.device_name})'
            sub_menus.extend([
                self.create_display_selection_menu(
                    f'Input for {monitor_label} on connect',
                    monitor_info.device_id,
                    monitor_info.inputs,
                    USER_SETTINGS_DISPLAY_ON_CONNECT_KEY_FUNC),
                self.create_display_selection_menu(
                    f'Input for {monitor_label} on disconnect',
                    monitor_info.device_id,
                    monitor_info.inputs,
                    USER_SETTINGS_DISPLAY_ON_DISCONNECT_KEY_FUNC)])
        sub_menus.append(self.create_usb_selection_menu())
        for sub_menu in sub_menus:
            menu.addMenu(sub_menu)
        return [menu]

    def create_usb_selection_menu(self):
        menu = QMenu('USB trigger for display switch', self)
        group = QActionGroup(self)
        group.setExclusive(True)
        for device in self.device_listener.get_real_usb_devices():
            action = QAction(f'{device.name}, {device.description} ({device.id})', self)
            action.setCheckable(True)
            action.setData(device)
            action.triggered.connect(partial(lambda val: self.change_usb_watcher(val), val=device))
            if device.id == self.user_settings.get(USER_SETTINGS_DISPLAY_USB_WATCHER_KEY):
                action.setChecked(True)
            group.addAction(action)
            menu.addAction(action)
        return menu

    def create_display_selection_menu(self, title, device_id, monitor_inputs, key_func):
        menu = QMenu(title, self)
        group = QActionGroup(self)
        group.setExclusive(True)

        for monitor_input in monitor_inputs:
            action = QAction(str(monitor_input), self)
            action.setCheckable(True)
            action.triggered.connect(partial(
                lambda val: self.user_settings.set(key_func(device_id), val),
                val=monitor_input))
            if monitor_input == self.user_settings.get(key_func(device_id)):
                action.setChecked(True)
            group.addAction(action)
            menu.addAction(action)
        return menu

    def change_usb_watcher(self, device: Device):
        self.user_settings.set(USER_SETTINGS_DISPLAY_USB_WATCHER_KEY, device.id)

    @Slot(bool, str)
    def device_changed(self, device_notification_type: DeviceNotificationType, usb_device: Device):
        logging.debug(f'Device change detected ({device_notification_type}): {usb_device.id}')
        current_time = time.time()
        if current_time - self.last_process < 1.0:
            return

        if self.user_settings.get(USER_SETTINGS_DISPLAY_USB_WATCHER_KEY) != usb_device.id:
            return

        for monitor in monitorcontrol.get_monitors():
            with monitor:
                hmon = monitor.vcp.hmonitor.value    # type: ignore
                monitor_info = self.input_per_monitor[hmon]
                device_id = monitor_info.device_id
                input_source = None
                if device_notification_type == DeviceNotificationType.CREATION:
                    input_source = self.user_settings.get(USER_SETTINGS_DISPLAY_ON_CONNECT_KEY_FUNC(device_id))
                elif device_notification_type == DeviceNotificationType.DELETION:
                    input_source = self.user_settings.get(USER_SETTINGS_DISPLAY_ON_DISCONNECT_KEY_FUNC(device_id))

                if input_source is not None:
                    self.last_process = time.time()
                    monitor.set_input_source(input_source)  # type: ignore
                    logging.info(f'Changing monitor {monitor_info.model} ({monitor_info.device_name}) '
                                 f'input source to {input_source}')

    def closeEvent(self, event):
        self.device_listener.close()
        event.accept()
