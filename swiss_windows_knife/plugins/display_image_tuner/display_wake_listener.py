"""Display wake / system-resume listener via Win32 WM_POWERBROADCAST.

Fires `woke` when the monitors power back on (DPMS console display state
off -> on, e.g. the user moves the mouse to wake idle screens) or the
system resumes from sleep. The display tuner uses it to re-assert
brightness/contrast, because some monitors reset their DDC luminance to
the onboard OSD value on a power-cycle while still reporting the old
value on `get_luminance()`.
"""
import ctypes
import logging
from ctypes import wintypes

from PySide6 import QtCore
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from ...base.base_widget import BaseWidget

WM_POWERBROADCAST = 0x0218
PBT_APMRESUMESUSPEND = 0x0007
PBT_APMRESUMEAUTOMATIC = 0x0012
PBT_POWERSETTINGCHANGE = 0x8013
DEVICE_NOTIFY_WINDOW_HANDLE = 0x00000000

DISPLAY_STATE_OFF = 0
DISPLAY_STATE_ON = 1
DISPLAY_STATE_DIMMED = 2


class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_ulong),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8),
    ]


# GUID_CONSOLE_DISPLAY_STATE {6FE69556-704A-47A0-8F24-C28D936FDA47}:
# monitor DPMS power state; Data is a DWORD (off/on/dimmed).
GUID_CONSOLE_DISPLAY_STATE = _GUID(
    0x6FE69556, 0x704A, 0x47A0,
    (ctypes.c_ubyte * 8)(0x8F, 0x24, 0xC2, 0x8D, 0x93, 0x6F, 0xDA, 0x47),
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


class _POWERBROADCAST_SETTING(ctypes.Structure):
    """Prefix of POWERBROADCAST_SETTING; for GUID_CONSOLE_DISPLAY_STATE the
    variable `Data` payload is a single DWORD (DataLength == 4)."""
    _fields_ = [
        ("PowerSetting", _GUID),
        ("DataLength", wintypes.DWORD),
        ("Data", wintypes.DWORD),
    ]


_user32 = ctypes.WinDLL("user32", use_last_error=True)
_user32.RegisterPowerSettingNotification.argtypes = [
    wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
_user32.RegisterPowerSettingNotification.restype = wintypes.HANDLE
_user32.UnregisterPowerSettingNotification.argtypes = [wintypes.HANDLE]
_user32.UnregisterPowerSettingNotification.restype = wintypes.BOOL


class DisplayWakeListener(BaseWidget):

    woke = QtCore.Signal()

    def __init__(self, parent: QWidget | None) -> None:
        super().__init__(parent)
        # Hidden top-level tool window: exists solely so the OS has an HWND
        # to deliver WM_POWERBROADCAST to. Never shown.
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
        self._notify_handle: int | None = None
        # Assume displays are on at startup so an initial "on" broadcast
        # isn't mistaken for a wake transition.
        self._display_on = True

        logging.info("Starting display wake listener (WM_POWERBROADCAST)")
        self._register_for_notifications()

    def _register_for_notifications(self) -> None:
        hwnd = int(self.winId())
        handle = _user32.RegisterPowerSettingNotification(
            wintypes.HANDLE(hwnd),
            ctypes.byref(GUID_CONSOLE_DISPLAY_STATE),
            DEVICE_NOTIFY_WINDOW_HANDLE)
        if not handle:
            err = ctypes.get_last_error()
            raise OSError(err, f"RegisterPowerSettingNotification failed (GetLastError={err})")
        self._notify_handle = handle

    def nativeEvent(self, eventType, message):
        if eventType == b"windows_generic_MSG":
            if self._handle_power_message(int(message)):
                self.woke.emit()
        return False, 0

    def _handle_power_message(self, msg_ptr: int) -> bool:
        """Return True when the message represents a display/system wake we
        should re-assert brightness for, False otherwise."""
        msg = _MSG.from_address(msg_ptr)
        if msg.message != WM_POWERBROADCAST:
            return False
        wparam = int(msg.wParam)
        if wparam in (PBT_APMRESUMEAUTOMATIC, PBT_APMRESUMESUSPEND):
            return True
        if wparam != PBT_POWERSETTINGCHANGE or not msg.lParam:
            return False
        setting = _POWERBROADCAST_SETTING.from_address(msg.lParam)
        if bytes(setting.PowerSetting) != bytes(GUID_CONSOLE_DISPLAY_STATE):
            return False
        display_on = setting.Data == DISPLAY_STATE_ON
        was_on = self._display_on
        self._display_on = display_on
        # Only a genuine off/dimmed -> on transition is a wake.
        return display_on and not was_on

    def closeEvent(self, event):
        if self._notify_handle:
            try:
                _user32.UnregisterPowerSettingNotification(self._notify_handle)
            except Exception:
                logging.exception("UnregisterPowerSettingNotification failed")
            self._notify_handle = None
        event.accept()
