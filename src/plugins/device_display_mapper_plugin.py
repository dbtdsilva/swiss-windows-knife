from functools import partial
import time

from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QMenu, QWidget
from PySide6.QtCore import Slot

from ..base.user_settings import UserSettings
from .device_listener import DeviceListener
from .base_plugin import BasePlugin

import monitorcontrol


class DeviceDisplayMapperPlugin(BasePlugin):

    def __init__(self, parent: QWidget, device_listener: DeviceListener) -> None:
        super().__init__(parent)

        self.user_settings = UserSettings.instance()
        if not self.user_settings.has_key('input_on_disconnect'):
            self.user_settings.set('input_on_disconnect', monitorcontrol.InputSource.HDMI1)
        if not self.user_settings.has_key('input_on_connect'):
            self.user_settings.set('input_on_connect', monitorcontrol.InputSource.DP1)

        self.logger.info(f"Starting with the 'input_on_connect' set to {self.user_settings.get('input_on_connect')}")
        self.logger.info(f"Starting with the 'input_on_disconnect' set to {self.user_settings.get('input_on_disconnect')}")

        self.last_process = 0
        device_listener.change_detected.connect(self.device_changed)

    def retrieve_menus(self) -> list[QMenu]:
        return [
            self.createInputMenu('Input on connect',
                                 self.change_input_source_on_connect,
                                 'input_on_connect'),
            self.createInputMenu('Input on disconnect',
                                 self.change_input_source_on_disconnect,
                                 'input_on_disconnect')]

    def createInputMenu(self, title, change_value_trigger, key):
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

    def change_input_source_on_connect(self, source):
        self.user_settings.set('input_on_connect', source)

    def change_input_source_on_disconnect(self, source):
        self.user_settings.set('input_on_disconnect', source)

    @Slot(bool, str)
    def device_changed(self, connected, usb):
        current_time = time.time()
        if current_time - self.last_process < 1.0:
            return

        self.last_process = time.time()
        for i, monitor in enumerate(monitorcontrol.get_monitors()):
            with monitor:
                if connected:
                    input_source = self.user_settings.get('input_on_connect')
                    monitor.set_input_source(input_source)  # type: ignore
                    self.logger.info(f"Changing monitor {i} input source to {input_source}")
                else:
                    input_source = self.user_settings.get('input_on_disconnect')
                    monitor.set_input_source(input_source)  # type: ignore
                    self.logger.info(f"Changing monitor {i} input source to {input_source}")
