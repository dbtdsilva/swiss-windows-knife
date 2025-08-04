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

class DeviceListener(BaseWidget):

    change_detected = QtCore.Signal(DeviceNotificationType, str)

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
    def get_usb_list():
        c = wmi.WMI()
        usb_devices = []

        for usb in c.query("SELECT * FROM Win32_USBControllerDevice"):
            try:
                dependent = usb.Dependent
                device_info = {
                    "DeviceID": dependent.DeviceID,
                    "PNPDeviceID": dependent.PNPDeviceID,
                    "Description": dependent.Description,
                    "Name": dependent.Name
                }
                print(dependent)
                usb_devices.append(device_info)
            except Exception as e:
                print("Failed to get USB device info:", e)
        return usb_devices

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
                usb_devices.append(pnp_id)
                print(pnp_id, device.Name, device.Description, device.Manufacturer)

        return usb_devices

    def closeEvent(self, event):
        self.connect_listener.requestInterruption()
        self.disconnect_listener.requestInterruption()

        self.connect_listener.wait()
        self.disconnect_listener.wait()
        event.accept()


class _DeviceListenerThread(QtCore.QThread):

    def __init__(self, parent,
                 parent_signal: QtCore.Signal(DeviceNotificationType, str),
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
                self.signal.emit(self.notification_type, usb.wmi_property('DeviceID').value)
            except wmi.x_wmi_timed_out:
                pass
        pythoncom.CoUninitialize()
