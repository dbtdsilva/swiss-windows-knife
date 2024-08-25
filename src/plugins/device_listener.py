from PySide6 import QtCore
from PySide6.QtWidgets import QWidget
import pythoncom
import wmi
import atexit

from .base_plugin import BasePlugin


class DeviceListener(BasePlugin):

    change_detected = QtCore.Signal(bool, str)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.connect_listener = _DeviceConnectListener(parent=self)
        self.connect_listener.start()
        self.disconnect_listener = _DeviceDisconnectListener(parent=self)
        self.disconnect_listener.start()

        self.disconnect_listener.disconnect_signal.connect(lambda usb: self.device_change(False, usb))
        self.connect_listener.connect_signal.connect(lambda usb: self.device_change(True, usb))
        atexit.register(self.stop)

    @QtCore.Slot(str)
    def device_change(self, connected, usb):
        self.change_detected.emit(connected, usb)

    def stop(self):
        self.connect_listener.requestInterruption()
        self.disconnect_listener.requestInterruption()

        self.connect_listener.wait()
        self.disconnect_listener.wait()


class _DeviceDisconnectListener(QtCore.QThread):

    disconnect_signal = QtCore.Signal(str)

    def run(self):
        pythoncom.CoInitialize()
        c = wmi.WMI()
        watcher = c.watch_for(
            notification_type="Deletion",
            wmi_class="Win32_PointingDevice")
        while not self.isInterruptionRequested():
            try:
                usb = watcher(500)
                self.disconnect_signal.emit(str(usb))
            except wmi.x_wmi_timed_out:
                pass
        pythoncom.CoUninitialize()


class _DeviceConnectListener(QtCore.QThread):

    connect_signal = QtCore.Signal(str)

    def run(self):
        pythoncom.CoInitialize()
        c = wmi.WMI()
        watcher = c.watch_for(
            notification_type="Creation",
            wmi_class="Win32_PointingDevice",
            delay_secs=1)
        while not self.isInterruptionRequested():
            try:
                usb = watcher(500)
                self.connect_signal.emit((str(usb)))
            except wmi.x_wmi_timed_out:
                pass
        pythoncom.CoUninitialize()
