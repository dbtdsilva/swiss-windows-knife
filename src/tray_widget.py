from datetime import datetime
from time import time
from typing import Optional
from PySide6.QtCore import Slot, QCoreApplication, QTimer
from PySide6.QtGui import QAction, QPixmap, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

from device_listener import DeviceListener
from controllable_data import ControllableData
from pysolar import solar, radiation
from datetime import datetime

import resources
import monitorcontrol
import logging
import pytz
import time

class TrayWidget(QWidget):
    logger = logging.getLogger(__name__)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent=parent)

        self.last_process = 0

        self.controllable_data = ControllableData()
        self.device_listener = DeviceListener(self)
        self.device_listener.change_detected.connect(self.device_changed)

        tray_icon_menu = QMenu(self)
        tray_icon_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)
        tray_icon_menu.addAction(quit_action)

        self._tray_icon = QSystemTrayIcon(self)
        self._tray_icon.setContextMenu(tray_icon_menu)
        self._tray_icon.setToolTip("System Listener")
        self._tray_icon.setIcon(QIcon(":/icons/eye-fill.ico"))
        self._tray_icon.show()

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_monitor_settings)
        self.timer.start(1000 * 60)
        self.logger.info("Widget started with success")
        self.update_monitor_settings()

    def update_monitor_settings(self):
        request = datetime.now().astimezone(pytz.timezone('Europe/Zurich'))
        altitude = solar.get_altitude(46.521410, 6.632273, request) + 5
        power = radiation.get_radiation_direct(request, altitude)

        # Apply functions based on the location and sun strenght
        current_value = int(power / 6.0) if power < 600 else int(100)
        brightness = current_value if self.controllable_data.brightness is None \
                else self.controllable_data.brightness
        contrast = current_value if self.controllable_data.contrast is None \
                else self.controllable_data.contrast        

        # Change respective settings on the monitor through DDC/CI
        try:
            for monitor in monitorcontrol.get_monitors():
                with monitor:
                    if monitor.get_luminance() != brightness:
                        monitor.set_luminance(brightness)
                        self.logger.info(f"Setting brightness to {brightness}")
                    if monitor.get_contrast() != contrast:
                        monitor.set_contrast(contrast)
                        self.logger.info(f"Setting contrast to {contrast}")
        except (ValueError, monitorcontrol.VCPError) as e:
            self.logger.warn(f"Exception was caught while changing brightness / contrast: {e}")

    @Slot()
    def close(self):
        QCoreApplication.exit()

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

