
from PySide6 import QtCore
import pythoncom
import wmi
import monitorcontrol

class DeviceDisconnect(QtCore.QObject):
    finished = QtCore.Signal()
    running = True

    def run(self):
        pythoncom.CoInitialize()
        print("Waiting for devices to be disconnected..")
        c = wmi.WMI ()
        watcher = c.watch_for(
            notification_type="Deletion",
            wmi_class="Win32_PointingDevice")
        while self.running:
            usb = watcher()
            print('Disconnected: ', str(usb).replace('\n',' ').replace('\t', ''))

            for monitor in monitorcontrol.get_monitors():
                with monitor:
                    monitor.set_input_source(monitorcontrol.InputSource.HDMI1)
        pythoncom.CoUninitialize()

class DeviceConnect(QtCore.QObject):
    finished = QtCore.Signal()
    running = True

    def run(self):
        pythoncom.CoInitialize()
        print("Waiting for devices to be connected..")
        c = wmi.WMI ()
        watcher = c.watch_for(
            notification_type="Creation",
            wmi_class="Win32_PointingDevice",
            delay_secs=1)
        while self.running:
            usb = watcher()
            print('Connected: ', str(usb).replace('\n',' ').replace('\t', ''))
            for monitor in monitorcontrol.get_monitors():
                with monitor:
                    monitor.set_power_mode(monitorcontrol.PowerMode.on)
                    monitor.set_input_source(monitorcontrol.InputSource.DP1)
        pythoncom.CoUninitialize()
