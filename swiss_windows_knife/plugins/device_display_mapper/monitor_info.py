import logging
import time
from dataclasses import dataclass

import monitorcontrol
from win32api import EnumDisplayDevices, EnumDisplayMonitors, GetMonitorInfo


@dataclass
class MonitorInfo:
    device_id: str
    device_name: str
    model: str
    inputs: list


class MonitorInfoCtx:

    def __init__(self) -> None:
        self.last_requested = 0
        self.monitor_info_by_device_id = {}

    def __get_display_monitors_by_hmon(self):
        current_time = time.time()
        if current_time - self.last_requested < 10:
            return self.monitor_hmon_device_id

        self.last_requested = current_time
        logging.debug('Retrieving monitors information from win32api')
        self.monitor_hmon_device_id = {}
        for hmon, _, _ in EnumDisplayMonitors(None, None):
            info = GetMonitorInfo(hmon)     # type: ignore
            dev = EnumDisplayDevices(info['Device'], 0, 1)
            self.monitor_hmon_device_id[int(hmon)] = (dev.DeviceID, dev.DeviceName)    # type: ignore
        return self.monitor_hmon_device_id

    def get_monitor_info_by_monitor(self, monitor: monitorcontrol.Monitor) -> MonitorInfo | None:
        hmon = monitor.vcp.hmonitor.value    # type: ignore
        monitor_hmon_device_id = self.__get_display_monitors_by_hmon()
        if hmon not in monitor_hmon_device_id:
            return None

        device_id, device_name = monitor_hmon_device_id[hmon]
        if device_id in self.monitor_info_by_device_id:
            return self.monitor_info_by_device_id[device_id]

        capabilities = monitor.get_vcp_capabilities()
        monitor_info = MonitorInfo(device_id, device_name, capabilities['model'], capabilities['inputs'])
        self.monitor_info_by_device_id[device_id] = monitor_info
        return monitor_info
