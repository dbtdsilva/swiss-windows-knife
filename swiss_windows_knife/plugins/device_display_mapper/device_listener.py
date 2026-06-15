"""USB device-arrival listener via Win32 WM_DEVICECHANGE.

Subscribes to USB device-interface arrival/removal through
RegisterDeviceNotificationW and emits `change_detected` on the GUI
thread. Replaces the previous WMI polling implementation: WM_DEVICECHANGE
fires synchronously from the OS, so the ~1s polling latency is gone.
"""
import ctypes
import logging
import re
from ctypes import wintypes
from enum import StrEnum

from PySide6 import QtCore
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from ...base.base_widget import BaseWidget

WM_DEVICECHANGE = 0x0219
DBT_DEVICEARRIVAL = 0x8000
DBT_DEVICEREMOVECOMPLETE = 0x8004
DBT_DEVTYP_DEVICEINTERFACE = 0x00000005
DEVICE_NOTIFY_WINDOW_HANDLE = 0x00000000


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_ulong),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8),
    ]


GUID_DEVINTERFACE_USB_DEVICE = _GUID(
    0xA5DCBF10, 0x6530, 0x11D2,
    (ctypes.c_ubyte * 8)(0x90, 0x1F, 0x00, 0xC0, 0x4F, 0xB9, 0x51, 0xED),
)


class _MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt_x", ctypes.c_long),
        ("pt_y", ctypes.c_long),
    ]


class _DEV_BROADCAST_HDR(ctypes.Structure):
    _fields_ = [
        ("dbch_size", wintypes.DWORD),
        ("dbch_devicetype", wintypes.DWORD),
        ("dbch_reserved", wintypes.DWORD),
    ]


class _DEV_BROADCAST_DEVICEINTERFACE_HEADER(ctypes.Structure):
    """Fixed-size prefix of DEV_BROADCAST_DEVICEINTERFACE_W; the
    variable-length `dbcc_name` WCHAR array follows in memory."""
    _fields_ = [
        ("dbcc_size", wintypes.DWORD),
        ("dbcc_devicetype", wintypes.DWORD),
        ("dbcc_reserved", wintypes.DWORD),
        ("dbcc_classguid", _GUID),
    ]


_DBCC_NAME_OFFSET = ctypes.sizeof(_DEV_BROADCAST_DEVICEINTERFACE_HEADER)


_user32 = ctypes.WinDLL("user32", use_last_error=True)
_user32.RegisterDeviceNotificationW.argtypes = [
    wintypes.HWND, ctypes.c_void_p, wintypes.DWORD]
_user32.RegisterDeviceNotificationW.restype = wintypes.HANDLE
_user32.UnregisterDeviceNotification.argtypes = [wintypes.HANDLE]
_user32.UnregisterDeviceNotification.restype = wintypes.BOOL


class DeviceNotificationType(StrEnum):
    DELETION = "Deletion"
    CREATION = "Creation"
    MODIFICATION = "Modification"
    OPERATION = "Operation"


class Device:
    def __init__(self, device_id, name="", description="", manufacturer=""):
        self.id = device_id
        self.name = name
        self.description = description
        self.manufacturer = manufacturer


def _device_path_to_pnp_id(device_path: str) -> str:
    r"""Convert a WM_DEVICECHANGE device interface path to PNPDeviceID form.

    `\\?\USB#VID_046D&PID_C534#1234#{A5DCBF10-...}` →
    `USB\VID_046D&PID_C534\1234`. The trailing GUID is the device
    interface class and isn't part of the PNPDeviceID the user settings
    match against.
    """
    if device_path.startswith("\\\\?\\"):
        device_path = device_path[4:]
    segments = device_path.split("#")
    while segments and segments[-1].startswith("{") and segments[-1].endswith("}"):
        segments.pop()
    return "\\".join(segments)


class DeviceListener(BaseWidget):

    change_detected = QtCore.Signal(DeviceNotificationType, Device)

    def __init__(self, parent: QWidget | None) -> None:
        super().__init__(parent)
        # Top-level tool window: exists solely so the OS has an HWND to
        # deliver WM_DEVICECHANGE to. Never shown.
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
        self._notify_handle: int | None = None

        logging.info("Starting device listener (WM_DEVICECHANGE)")
        self._register_for_notifications()

    def _register_for_notifications(self) -> None:
        hwnd = int(self.winId())
        filt = _DEV_BROADCAST_DEVICEINTERFACE_HEADER()
        filt.dbcc_size = _DBCC_NAME_OFFSET
        filt.dbcc_devicetype = DBT_DEVTYP_DEVICEINTERFACE
        filt.dbcc_classguid = GUID_DEVINTERFACE_USB_DEVICE
        handle = _user32.RegisterDeviceNotificationW(
            hwnd, ctypes.byref(filt), DEVICE_NOTIFY_WINDOW_HANDLE)
        if not handle:
            err = ctypes.get_last_error()
            raise OSError(err, f"RegisterDeviceNotificationW failed (GetLastError={err})")
        self._notify_handle = handle

    @staticmethod
    def is_real_usb_device(pnp_id):
        if not pnp_id.startswith("USB\\"):
            return False
        if "ROOT" in pnp_id:
            return False
        if not re.search(r'VID_[0-9A-F]{4}&PID_[0-9A-F]{4}', pnp_id, re.IGNORECASE):
            return False
        return True

    def nativeEvent(self, eventType, message):
        if eventType == b"windows_generic_MSG":
            result = self._handle_native_message(int(message))
            if result is not None:
                notif_type, device = result
                self.change_detected.emit(notif_type, device)
        return False, 0

    def _handle_native_message(self, msg_ptr: int):
        """Parse a Windows MSG pointer; return `(type, Device)` for a USB
        arrival/removal we care about, or `None` otherwise."""
        msg = _MSG.from_address(msg_ptr)
        if msg.message != WM_DEVICECHANGE:
            return None
        wparam = int(msg.wParam)
        if wparam == DBT_DEVICEARRIVAL:
            notif_type = DeviceNotificationType.CREATION
        elif wparam == DBT_DEVICEREMOVECOMPLETE:
            notif_type = DeviceNotificationType.DELETION
        else:
            return None
        if not msg.lParam:
            return None
        hdr = _DEV_BROADCAST_HDR.from_address(msg.lParam)
        if hdr.dbch_devicetype != DBT_DEVTYP_DEVICEINTERFACE:
            return None
        try:
            name = ctypes.wstring_at(msg.lParam + _DBCC_NAME_OFFSET)
        except Exception:
            logging.exception("Failed to read device interface name from WM_DEVICECHANGE")
            return None
        pnp_id = _device_path_to_pnp_id(name)
        if not self.is_real_usb_device(pnp_id):
            return None
        return notif_type, Device(pnp_id)

    def closeEvent(self, event):
        if self._notify_handle:
            try:
                _user32.UnregisterDeviceNotification(self._notify_handle)
            except Exception:
                logging.exception("UnregisterDeviceNotification failed")
            self._notify_handle = None
        event.accept()
