import logging

import monitorcontrol
from PySide6.QtCore import QObject, Signal

from .monitor_info import MonitorInfo, MonitorInfoCtx


def list_monitors(monitor_info_ctx: MonitorInfoCtx) -> list[MonitorInfo]:
    """Read DDC/CI capabilities for every attached monitor.

    MUST run on the dedicated monitor-runner thread (see
    `src/base/monitor_runner.py`); calling from the GUI thread will block
    for seconds per monitor on a cold cache.
    """
    out: list[MonitorInfo] = []
    for monitor in monitorcontrol.get_monitors():
        with monitor:
            info = monitor_info_ctx.get_monitor_info_by_monitor(monitor=monitor)
            if info is None:
                logging.warning("No monitor info available for one of the attached displays")
                continue
            out.append(info)
    return out


class UsbWorker(QObject):
    """One-shot WMI Win32_PnPEntity enumeration on a worker thread.

    Each instance runs once: `moveToThread(thread)`, connect `thread.started`
    to `run`, start the thread; emits `finished(list[Device])` when done.
    `run` initialises COM on the worker thread (the GUI-thread `wmi.WMI()`
    instance can't be used cross-thread without crashing).
    """

    finished = Signal(list)

    def run(self) -> None:
        import pythoncom
        import wmi

        from .device_listener import Device, DeviceListener
        pythoncom.CoInitialize()
        try:
            local_wmi = wmi.WMI()
            devices: list[Device] = []
            for entity in local_wmi.Win32_PnPEntity():
                pnp_id = getattr(entity, "PNPDeviceID", "")
                if DeviceListener.is_real_usb_device(pnp_id):
                    devices.append(Device(entity.DeviceID, entity.Name, entity.Description, entity.Manufacturer))
            devices.sort(key=lambda d: d.name)
        except Exception:
            logging.exception("USB discovery failed")
            devices = []
        finally:
            pythoncom.CoUninitialize()
        self.finished.emit(devices)
