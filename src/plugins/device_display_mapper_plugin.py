from functools import partial
from plugins.base_plugin import BasePlugin
import time

from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QMenu, QWidget
from PySide6.QtCore import Slot

from plugins.controllable_data import ControllableData
from plugins.device_listener import DeviceListener

import monitorcontrol


class DeviceDisplayMapperPlugin(BasePlugin):

    def __init__(self, parent: QWidget, device_listener: DeviceListener) -> None:
        super().__init__(parent)

        self.controllable_data = ControllableData()
        self.last_process = 0
        device_listener.change_detected.connect(self.device_changed)

    def retrieve_menus(self) -> list[QMenu]:
        return [
            self.createInputMenu('Input on connect',
                                 self.change_input_source_on_connect,
                                 self.controllable_data.input_on_connect),
            self.createInputMenu('Input on disconnect',
                                 self.change_input_source_on_disconnect,
                                 self.controllable_data.input_on_disconnect)]

    def createInputMenu(self, title, change_value_trigger, current_value):
        menu = QMenu(title, self)
        group = QActionGroup(self)
        group.setExclusive(True)
        for source in monitorcontrol.InputSource:
            action = QAction(str(source), self)
            action.setCheckable(True)
            action.triggered.connect(partial(lambda val: change_value_trigger(val), val=source))
            if source == current_value:
                action.setChecked(True)
            group.addAction(action)
            menu.addAction(action)
        return menu

    def change_input_source_on_connect(self, source):
        self.controllable_data.input_on_connect = source

    def change_input_source_on_disconnect(self, source):
        self.controllable_data.input_on_disconnect = source

    @Slot(bool, str)
    def device_changed(self, connected, usb):
        current_time = time.time()
        if current_time - self.last_process < 1.0:
            return

        self.last_process = time.time()
        for i, monitor in enumerate(monitorcontrol.get_monitors()):
            with monitor:
                if connected:
                    self.logger.info(f"Changing monitor {i} input source to {self.controllable_data.input_on_connect}")
                    monitor.set_input_source(self.controllable_data.input_on_connect)  # type: ignore
                else:
                    self.logger.info(f"Changing monitor {i} input source to {self.controllable_data.input_on_disconnect}")
                    monitor.set_input_source(self.controllable_data.input_on_disconnect)  # type: ignore
