import logging

import monitorcontrol

from .device_listener import DeviceListener
from .monitor_info import MonitorInfo, MonitorInfoCtx


def list_monitors(monitor_info_ctx: MonitorInfoCtx) -> list[MonitorInfo]:
    """Read DDC/CI capabilities for every attached monitor.

    MUST run on the dedicated monitor-runner thread (see
    `src/base/monitor_runner.py`); calling from the GUI thread will block
    for seconds per monitor.
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


def list_usb_devices(device_listener: DeviceListener):
    """Enumerate currently-attached real USB devices via WMI.

    MUST run off the GUI thread; `Win32_PnPEntity` enumeration is multi-second.
    """
    return device_listener.get_real_usb_devices()
