from enum import StrEnum

from PySide6 import QtCore
from PySide6.QtWidgets import QWidget
import pythoncom
import wmi
import re
import logging

from ...base.base_widget import BaseWidget


class DeviceNotificationType(StrEnum):
    DELETION = "Deletion"
    CREATION = "Creation"
    MODIFICATION = "Modification"
    OPERATION = "Operation"


class Device:
    def __init__(self, device_id, name, description, manufacturer):
        self.id = device_id
        self.name = name
        self.description = description
        self.manufacturer = manufacturer


class DeviceListener(BaseWidget):

    change_detected = QtCore.Signal(DeviceNotificationType, Device)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)

        logging.info('Starting device listener..')
        self.connect_listener = _DeviceListenerThread(parent=self,
                                                      parent_signal=self.change_detected,
                                                      notification_type=DeviceNotificationType.CREATION)
        self.disconnect_listener = _DeviceListenerThread(parent=self,
                                                         parent_signal=self.change_detected,
                                                         notification_type=DeviceNotificationType.DELETION)
        self.connect_listener.start()
        self.disconnect_listener.start()

    @staticmethod
    def is_real_usb_device(pnp_id):
        if not pnp_id.startswith("USB\\"):
            return False
        if "ROOT" in pnp_id:
            return False
        if not re.search(r'VID_[0-9A-F]{4}&PID_[0-9A-F]{4}', pnp_id, re.IGNORECASE):
            return False
        return True

    @staticmethod
    def get_real_usb_devices():
        c = wmi.WMI()
        usb_devices = []

        for device in c.Win32_PnPEntity():
            pnp_id = getattr(device, "PNPDeviceID", "")
            if DeviceListener.is_real_usb_device(pnp_id):
                device = Device(device.DeviceID, device.Name, device.Description, device.Manufacturer)
                usb_devices.append(device)

        usb_devices.sort(key=lambda d: d.name)
        return usb_devices

    def closeEvent(self, event):
        self.connect_listener.requestInterruption()
        self.disconnect_listener.requestInterruption()

        self.connect_listener.wait()
        self.disconnect_listener.wait()
        event.accept()


class _DeviceListenerThread(QtCore.QThread):

    def __init__(self, parent,
                 parent_signal: QtCore.Signal(DeviceNotificationType, Device),
                 notification_type: DeviceNotificationType):
        super().__init__(parent)
        self.notification_type = notification_type
        self.signal = parent_signal

    def run(self):
        logging.info(f"Starting DeviceDisconnectListener for {self.notification_type}")

        pythoncom.CoInitialize()
        c = wmi.WMI()
        watcher = c.watch_for(
            notification_type=self.notification_type.value,
            wmi_class="Win32_PnPEntity",
            delay_secs=1)
        while not self.isInterruptionRequested():
            try:
                usb = watcher(500)
                self.signal.emit(self.notification_type,
                                 Device(usb.DeviceID, usb.Name, usb.Description, usb.Manufacturer))
            except wmi.x_wmi_timed_out:
                pass
        pythoncom.CoUninitialize()
