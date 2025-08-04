from functools import partial
import time

from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QMenu, QWidget
from PySide6.QtCore import Slot

from ...base.user_settings import UserSettings
from .device_listener import DeviceListener, DeviceNotificationType
from ...base.base_widget import BaseWidget

import monitorcontrol
import logging


class DeviceDisplayMapperPlugin(BaseWidget):

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)

        self.user_settings = UserSettings.instance()
        if not self.user_settings.has_key('display_on_disconnect'):
            self.user_settings.set('display_on_disconnect', monitorcontrol.InputSource.HDMI1)
        if not self.user_settings.has_key('display_on_connect'):
            self.user_settings.set('display_on_connect', monitorcontrol.InputSource.DP1)

        logging.info(f"Starting with the 'display_on_connect' set to {self.user_settings.get('display_on_connect')}")
        logging.info(f"Starting with the 'display_on_disconnect' set to {self.user_settings.get('display_on_disconnect')}")

        self.last_process = 0
        self.device_listener = DeviceListener(self)
        self.device_listener.change_detected.connect(self.device_changed)

    def retrieve_menus(self) -> list[QMenu]:
        return [
            self.create_display_selection_menu('Display on connect',
                                               self.change_display_on_input_connect,
                                 'display_on_connect'),
            self.create_display_selection_menu('Display on disconnect',
                                               self.change_display_on_input_disconnect,
                                 'display_on_disconnect'),
            self.create_usb_selection_menu('USB to be watched for display connection',
                                           self.change_usb_watcher,
                                           'usb_watcher'),
        ]

    def create_usb_selection_menu(self, title, change_value_trigger, key):
        menu = QMenu(title, self)
        group = QActionGroup(self)
        group.setExclusive(True)
        for source in self.device_listener.get_real_usb_devices():
            action = QAction(str(source), self)
            action.setCheckable(True)
            action.triggered.connect(partial(lambda val: change_value_trigger(val), val=source))
            if source == self.user_settings.get(key):
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
        self.user_settings.set('display_on_connect', source)

    def change_display_on_input_disconnect(self, source):
        self.user_settings.set('display_on_disconnect', source)

    def change_usb_watcher(self, source):
        self.user_settings.set('usb_watcher', source)

    @Slot(bool, str)
    def device_changed(self, device_notification_type: DeviceNotificationType, usb_device_id: str):
        current_time = time.time()
        if current_time - self.last_process < 1.0:
            return

        if self.user_settings.get('usb_watcher') != usb_device_id:
            return

        self.last_process = time.time()
        for i, monitor in enumerate(monitorcontrol.get_monitors()):
            with monitor:
                if device_notification_type == DeviceNotificationType.CREATION:
                    input_source = self.user_settings.get('display_on_connect')
                    monitor.set_input_source(input_source)  # type: ignore
                    logging.info(f"Changing monitor {i} input source to {input_source}")
                elif device_notification_type == DeviceNotificationType.DELETION:
                    input_source = self.user_settings.get('display_on_disconnect')
                    monitor.set_input_source(input_source)  # type: ignore
                    logging.info(f"Changing monitor {i} input source to {input_source}")

    def closeEvent(self, event):
        self.device_listener.close()
        event.accept()
