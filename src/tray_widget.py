from datetime import datetime
from typing import Optional
from PySide6.QtCore import Slot, QCoreApplication, QTimer
from PySide6.QtGui import QAction, QPixmap, QPainter
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

from device_listener import DeviceListener
from controllable_data import ControllableData
from tray_window import TrayWindow
from pysolar import solar, radiation
from datetime import datetime, timezone

import resources
import monitorcontrol
import logging
import pytz

class TrayWidget(QWidget):
    logger = logging.getLogger(__name__)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent=parent)

        self.controllable_data = ControllableData()
        self.device_listener = DeviceListener(self)
        self.device_listener.change_detected.connect(self.device_changed)

        tray_icon_menu = QMenu(self)
        tray_icon_menu.addSeparator()

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)
        tray_icon_menu.addAction(quit_action)

        self._tray_icon = QSystemTrayIcon(self)
        self.set_tray_icon(False)
        self._tray_icon.setContextMenu(tray_icon_menu)
        self._tray_icon.setToolTip("System Listener")
        self._tray_icon.activated.connect(self.icon_activated)

        self._tray_window = TrayWindow()
        self._tray_window.visibleChanged.connect(self.set_tray_icon)
        self._tray_icon.show()

        self.timer = QTimer()
        self.timer.timeout.connect(self.periodic_timeout)
        self.timer.start(1000 * 60)
        self.logger.info("Widget started with success")

    def periodic_timeout(self):
        request = datetime.now().astimezone(pytz.timezone('Europe/Zurich'))
        altitude = solar.get_altitude(46.521410, 6.632273, request) + 10
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

    @Slot(str)
    def icon_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self._tray_window.show()

    @Slot()
    def close(self):
        QCoreApplication.exit()

    @Slot(bool)
    def set_tray_icon(self, enabled):
        if enabled:
            pixmap = QPixmap(":/icons/eye-fill.svg")
        else:
            pixmap = QPixmap(":/icons/eye-slash-fill.svg")
        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), 'white')
        painter.end()

        self._tray_icon.setIcon(pixmap)

    @Slot(bool, str)
    def device_changed(self, connected, usb):
        for monitor in monitorcontrol.get_monitors():
            with monitor:
                if connected:
                    self.logger.info(f"Changing input source to {self.controllable_data.input_on_connect}")
                    monitor.set_input_source(self.controllable_data.input_on_connect)
                else:
                    self.logger.info(f"Changing input source to {self.controllable_data.input_on_disconnect}")
                    monitor.set_input_source(self.controllable_data.input_on_disconnect)

