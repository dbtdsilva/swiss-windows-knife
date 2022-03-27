from typing import Optional
from xml.sax.xmlreader import InputSource
from PySide6.QtCore import Slot, QCoreApplication
from PySide6.QtGui import QAction, QPixmap, QPainter
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

from device_listener import DeviceListener
from tray_window import TrayWindow

import rc_systray
import monitorcontrol

class TrayWidget(QWidget):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent=parent)
        
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

    @Slot(str)
    def icon_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self._tray_window.show()

    @Slot()
    def close(self):
        QCoreApplication.exit()

    @Slot(bool)
    def set_tray_icon(self, enabled):
        print(enabled)
        if enabled:
            pixmap = QPixmap(":/images/eye-fill.svg")
        else:
            pixmap = QPixmap(":/images/eye-slash-fill.svg")
        painter = QPainter(pixmap)
        painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
        painter.fillRect(pixmap.rect(), 'white')
        painter.end()

        self._tray_icon.setIcon(pixmap)

    @Slot(bool, str)
    def device_changed(self, connected, usb):
        print('Connected: ', connected)

        for monitor in monitorcontrol.get_monitors():
            with monitor:
                if connected:
                    monitor.set_input_source(monitorcontrol.InputSource.DP1)
                else:
                    monitor.set_input_source(monitorcontrol.InputSource.HDMI1)

