from datetime import datetime
from time import time
from typing import Optional
from functools import partial
from PySide6.QtCore import Slot, QCoreApplication, QTimer, Signal
from PySide6.QtGui import QAction, QIcon, QActionGroup
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

from pysolar import solar, radiation

import monitorcontrol
import logging
import pytz

import resources # noqa: F401,E261

from app_info import APP_INFO
from controllable_data import ControllableData
from device_listener import DeviceListener
from tray_logger import TrayLogger


class TrayWidget(QWidget):
    logger = logging.getLogger(__name__)
    brightness_change = Signal(int)
    contrast_change = Signal(int)

    def createMenu(self, menu) -> QMenu:
        tray_icon_menu = QMenu(self)
        group = QActionGroup(self)
        group.setExclusive(True)
        for title, trigger, checkable in menu:
            if title is None:
                tray_icon_menu.addSeparator()
            elif type(trigger) is not list:
                action = QAction(title, self)
                action.triggered.connect(trigger)
                action.setCheckable(checkable)
                group.addAction(action)
                tray_icon_menu.addAction(action)
            else:
                sub_menu = self.createMenu(trigger)
                sub_menu.setTitle(title)
                tray_icon_menu.addMenu(sub_menu)
        return tray_icon_menu

    def createValueControlMenu(self, title, change_value_trigger, current_value) -> QMenu:
        menu = QMenu(title, self)
        group = QActionGroup(self)
        group.setExclusive(True)

        automatic_action = QAction('Automatic', self)
        automatic_action.setCheckable(True)
        automatic_action.triggered.connect(lambda: change_value_trigger(None))
        if current_value is None:
            automatic_action.setChecked(True)
        group.addAction(automatic_action)
        menu.addAction(automatic_action)
        menu.addSeparator()
        for value_entry in range(0, 101, 10):
            action = QAction(str(value_entry), self)
            action.setCheckable(True)
            action.triggered.connect(partial(lambda val: change_value_trigger(val), val=value_entry))
            if value_entry == current_value:
                action.setChecked(True)
            group.addAction(action)
            menu.addAction(action)
        return menu

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

    def createMainMenu(self) -> QMenu:
        menu = QMenu(self)
        menu.addMenu(self.createValueControlMenu('Brightness',
                                                 self.set_brightness,
                                                 self.controllable_data.brightness))
        menu.addMenu(self.createValueControlMenu('Contrast',
                                                 self.set_contrast,
                                                 self.controllable_data.contrast))
        menu.addMenu(self.createInputMenu('Input on connect',
                                          self.change_input_source_on_connect,
                                          self.controllable_data.input_on_connect))
        menu.addMenu(self.createInputMenu('Input on disconnect',
                                          self.change_input_source_on_disconnect,
                                          self.controllable_data.input_on_disconnect))
        menu.addSeparator()

        logs_action = QAction('View logs', self)
        logs_action.triggered.connect(self.open_logs_window)
        menu.addAction(logs_action)
        menu.addSeparator()
        quit_action = QAction('Quit', self)
        quit_action.triggered.connect(self.close)
        menu.addAction(quit_action)
        return menu

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent=parent)
        self.last_process = 0
        self.logger_window = TrayLogger(self)
        self.logger_window.hide()

        self.controllable_data = ControllableData()
        self.device_listener = DeviceListener(self)
        self.device_listener.change_detected.connect(self.device_changed)

        self._tray_icon = QSystemTrayIcon(self)
        self._tray_icon.setContextMenu(self.createMainMenu())
        self._tray_icon.setToolTip(APP_INFO.APP_NAME)
        self._tray_icon.setIcon(QIcon(":/icons/eye-fill.ico"))
        self._tray_icon.show()

        self.timer = QTimer()
        self.timer.timeout.connect(self.change_monitor_automatic)
        self.timer.start(1000 * 60)
        self.logger.info("Widget started with success")
        self.change_monitor_automatic()

    def change_input_source_on_connect(self, source):
        self.logger.info(f"Changing source on connect to {source}")
        self.controllable_data.input_on_connect = source

    def change_input_source_on_disconnect(self, source):
        self.logger.info(f"Changing source on disconnect to {source}")
        self.controllable_data.input_on_disconnect = source

    def change_monitor_automatic(self):
        request = datetime.now().astimezone(pytz.timezone('Europe/Zurich'))
        altitude = solar.get_altitude(46.521410, 6.632273, request) + 5
        power = radiation.get_radiation_direct(request, altitude)

        # Apply functions based on the location and sun strenght
        current_value = int(power / 6.0) if power < 600 else int(100)
        if self.controllable_data.brightness is None:
            self.change_monitor_brightness(current_value)
        if self.controllable_data.contrast is None:
            self.change_monitor_contrast(current_value)

    def change_monitor_brightness(self, brightness):
        # Change respective settings on the monitor through DDC/CI
        try:
            for i, monitor in enumerate(monitorcontrol.get_monitors()):
                with monitor:
                    if monitor.get_luminance() != brightness:
                        monitor.set_luminance(brightness)
                        self.logger.info(f"Setting brightness to {brightness} on monitor {i}")
        except (ValueError, monitorcontrol.VCPError) as e:
            self.logger.warn(f"Exception was caught while changing brightness: {e}")

    def change_monitor_contrast(self, contrast):
        # Change respective settings on the monitor through DDC/CI
        try:
            for i, monitor in enumerate(monitorcontrol.get_monitors()):
                with monitor:
                    if monitor.get_contrast() != contrast:
                        monitor.set_contrast(contrast)
                        self.logger.info(f"Setting contrast to {contrast} on monitor {i}")
        except (ValueError, monitorcontrol.VCPError) as e:
            self.logger.warn(f"Exception was caught while changing contrast: {e}")

    @Slot()
    def close(self):
        QCoreApplication.exit()

    @Slot()
    def open_logs_window(self):
        self.logger_window.show()

    def set_brightness(self, brightness):
        self.controllable_data.brightness = brightness
        if brightness is not None:
            self.logger.info(f"Setting brightness to manual with {brightness}")
            self.change_monitor_brightness(brightness=brightness)
        else:
            self.logger.info("Setting brightness to automatic mode")
            self.change_monitor_automatic()

    @Slot(int)
    def set_contrast(self, contrast):
        self.controllable_data.contrast = contrast
        if contrast is not None:
            self.logger.info(f"Setting contrast to manual with {contrast}")
            self.change_monitor_contrast(contrast=contrast)
        else:
            self.logger.info("Setting contrast to automatic mode")
            self.change_monitor_automatic()

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
                    monitor.set_input_source(self.controllable_data.input_on_connect)
                else:
                    self.logger.info(f"Changing monitor {i} input source to {self.controllable_data.input_on_disconnect}")
                    monitor.set_input_source(self.controllable_data.input_on_disconnect)
