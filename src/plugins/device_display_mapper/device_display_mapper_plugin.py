from functools import partial
import time

from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QMenu, QWidget
from PySide6.QtCore import Slot

from ...base.user_settings import UserSettings
from .device_listener import DeviceListener, DeviceNotificationType, Device
from ...base.base_widget import BaseWidget

import monitorcontrol
import logging

USER_SETTINGS_DISPLAY_ON_CONNECT_KEY = 'display_on_connect'
USER_SETTINGS_DISPLAY_ON_DISCONNECT_KEY = 'display_on_disconnect'
USER_SETTINGS_DISPLAY_USB_WATCHER_KEY = 'display_usb_watcher'


class DeviceDisplayMapperPlugin(BaseWidget):

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)

        self.user_settings = UserSettings.instance()
        if not self.user_settings.has_key(USER_SETTINGS_DISPLAY_ON_DISCONNECT_KEY):
            self.user_settings.set(USER_SETTINGS_DISPLAY_ON_DISCONNECT_KEY, monitorcontrol.InputSource.HDMI1)
        if not self.user_settings.has_key(USER_SETTINGS_DISPLAY_ON_CONNECT_KEY):
            self.user_settings.set(USER_SETTINGS_DISPLAY_ON_CONNECT_KEY, monitorcontrol.InputSource.DP1)

        logging.info(f"Starting with the {USER_SETTINGS_DISPLAY_ON_CONNECT_KEY} set to "
                     f"{self.user_settings.get(USER_SETTINGS_DISPLAY_ON_CONNECT_KEY)}")
        logging.info(f"Starting with the {USER_SETTINGS_DISPLAY_ON_DISCONNECT_KEY} set to "
                     f"{self.user_settings.get(USER_SETTINGS_DISPLAY_ON_DISCONNECT_KEY)}")
        logging.info(f"Starting with the {USER_SETTINGS_DISPLAY_USB_WATCHER_KEY} set to "
                     f"{self.user_settings.get(USER_SETTINGS_DISPLAY_USB_WATCHER_KEY)}")

        self.last_process = 0
        self.device_listener = DeviceListener(self)
        self.device_listener.change_detected.connect(self.device_changed)

    def retrieve_menus(self) -> list[QMenu]:
        menu = QMenu('Display automation', self)
        sub_menus = [
            self.create_display_selection_menu('Display on connect',
                                               self.change_display_on_input_connect,
                                               USER_SETTINGS_DISPLAY_ON_CONNECT_KEY),
            self.create_display_selection_menu('Display on disconnect',
                                               self.change_display_on_input_disconnect,
                                               USER_SETTINGS_DISPLAY_ON_DISCONNECT_KEY),
            self.create_usb_selection_menu(),
        ]
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

    def create_display_selection_menu(self, title, change_value_trigger, key):
        menu = QMenu(title, self)
        group = QActionGroup(self)
        group.setExclusive(True)
        for source in monitorcontrol.InputSource:
            action = QAction(str(source), self)
            action.setCheckable(True)
            action.triggered.connect(partial(lambda val: change_value_trigger(val), val=source))
            if source == self.user_settings.get(key):
                action.setChecked(True)
            group.addAction(action)
            menu.addAction(action)
        return menu

    def change_display_on_input_connect(self, source):
        self.user_settings.set(USER_SETTINGS_DISPLAY_ON_CONNECT_KEY, source)

    def change_display_on_input_disconnect(self, source):
        self.user_settings.set(USER_SETTINGS_DISPLAY_ON_DISCONNECT_KEY, source)

    def change_usb_watcher(self, device: Device):
        self.user_settings.set(USER_SETTINGS_DISPLAY_USB_WATCHER_KEY, device.id)

    @Slot(bool, str)
    def device_changed(self, device_notification_type: DeviceNotificationType, usb_device: Device):
        current_time = time.time()
        if current_time - self.last_process < 1.0:
            return

        if self.user_settings.get(USER_SETTINGS_DISPLAY_USB_WATCHER_KEY) != usb_device.id:
            return

        self.last_process = time.time()
        for i, monitor in enumerate(monitorcontrol.get_monitors()):
            with monitor:
                if device_notification_type == DeviceNotificationType.CREATION:
                    input_source = self.user_settings.get(USER_SETTINGS_DISPLAY_ON_CONNECT_KEY)
                    monitor.set_input_source(input_source)  # type: ignore
                    logging.info(f"Changing monitor {i} input source to {input_source}")
                elif device_notification_type == DeviceNotificationType.DELETION:
                    input_source = self.user_settings.get(USER_SETTINGS_DISPLAY_ON_DISCONNECT_KEY)
                    monitor.set_input_source(input_source)  # type: ignore
                    logging.info(f"Changing monitor {i} input source to {input_source}")

    def closeEvent(self, event):
        self.device_listener.close()
        event.accept()
