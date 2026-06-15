"""Coverage for the WM_DEVICECHANGE-based USB device listener.

The plugin's USB-driven monitor input switch depends on `DeviceListener`
parsing WM_DEVICECHANGE arrivals/removals correctly and emitting
`change_detected` with a PNPDeviceID that matches what the user picked
in settings. Regressions either mis-fire (wrong notif type, wrong id) or
silently drop events.
"""
import ctypes
from unittest.mock import MagicMock

import pytest


def _build_dev_broadcast(name: str) -> ctypes.Array:
    """Build an in-memory DEV_BROADCAST_DEVICEINTERFACE_W with `name` as
    the trailing null-terminated WCHAR payload. Returns the backing
    buffer (keep a reference; lParam points into it)."""
    from swiss_windows_knife.plugins.device_display_mapper.device_listener import (
        _DBCC_NAME_OFFSET,
        _DEV_BROADCAST_DEVICEINTERFACE_HEADER,
        DBT_DEVTYP_DEVICEINTERFACE,
    )

    encoded = name.encode("utf-16-le") + b"\x00\x00"
    total = _DBCC_NAME_OFFSET + len(encoded)
    buf = (ctypes.c_ubyte * total)()
    hdr = _DEV_BROADCAST_DEVICEINTERFACE_HEADER.from_address(ctypes.addressof(buf))
    hdr.dbcc_size = total
    hdr.dbcc_devicetype = DBT_DEVTYP_DEVICEINTERFACE
    ctypes.memmove(ctypes.addressof(buf) + _DBCC_NAME_OFFSET, encoded, len(encoded))
    return buf


def _build_msg(wparam: int, lparam: int, message: int | None = None) -> "ctypes.Structure":
    from swiss_windows_knife.plugins.device_display_mapper.device_listener import (
        _MSG,
        WM_DEVICECHANGE,
    )

    msg = _MSG()
    msg.message = WM_DEVICECHANGE if message is None else message
    msg.wParam = wparam
    msg.lParam = lparam
    return msg


@pytest.fixture
def listener(qtbot, monkeypatch):
    """Construct DeviceListener without touching Win32 registration."""
    from swiss_windows_knife.plugins.device_display_mapper.device_listener import (
        DeviceListener,
    )

    monkeypatch.setattr(
        DeviceListener, "_register_for_notifications", lambda self: None)
    listener = DeviceListener(parent=None)
    qtbot.addWidget(listener)
    return listener


@pytest.mark.parametrize("device_path,expected", [
    (
        "\\\\?\\USB#VID_046D&PID_C534#1234#{a5dcbf10-6530-11d2-901f-00c04fb951ed}",
        "USB\\VID_046D&PID_C534\\1234",
    ),
    (
        # Composite serial with extra '#' segments
        "\\\\?\\USB#VID_046D&PID_085B&MI_02#7&7c1799&0&0002#{a5dcbf10-6530-11d2-901f-00c04fb951ed}",
        "USB\\VID_046D&PID_085B&MI_02\\7&7c1799&0&0002",
    ),
    (
        # No \\?\ prefix (defensive — shouldn't normally happen)
        "USB#VID_1234&PID_5678#abc#{a5dcbf10-6530-11d2-901f-00c04fb951ed}",
        "USB\\VID_1234&PID_5678\\abc",
    ),
    (
        # No trailing GUID
        "\\\\?\\USB#VID_1234&PID_5678#abc",
        "USB\\VID_1234&PID_5678\\abc",
    ),
])
def test_device_path_to_pnp_id(device_path, expected):
    from swiss_windows_knife.plugins.device_display_mapper.device_listener import (
        _device_path_to_pnp_id,
    )
    assert _device_path_to_pnp_id(device_path) == expected


def test_handle_native_message_ignores_non_devicechange(listener):
    msg = _build_msg(wparam=0, lparam=0, message=0x0001)
    assert listener._handle_native_message(ctypes.addressof(msg)) is None


def test_handle_native_message_ignores_modification_wparam(listener):
    # 0x0007 = DBT_DEVNODES_CHANGED — fired for many topology changes; we
    # only act on arrival/removal.
    msg = _build_msg(wparam=0x0007, lparam=0)
    assert listener._handle_native_message(ctypes.addressof(msg)) is None


def test_handle_native_message_emits_creation_for_usb_arrival(listener):
    from swiss_windows_knife.plugins.device_display_mapper.device_listener import (
        DBT_DEVICEARRIVAL,
        Device,
        DeviceNotificationType,
    )

    payload = _build_dev_broadcast(
        "\\\\?\\USB#VID_046D&PID_C534#serial-1#{a5dcbf10-6530-11d2-901f-00c04fb951ed}")
    msg = _build_msg(wparam=DBT_DEVICEARRIVAL, lparam=ctypes.addressof(payload))

    result = listener._handle_native_message(ctypes.addressof(msg))
    assert result is not None
    notif_type, device = result
    assert notif_type is DeviceNotificationType.CREATION
    assert isinstance(device, Device)
    assert device.id == "USB\\VID_046D&PID_C534\\serial-1"


def test_handle_native_message_emits_deletion_for_usb_removal(listener):
    from swiss_windows_knife.plugins.device_display_mapper.device_listener import (
        DBT_DEVICEREMOVECOMPLETE,
        DeviceNotificationType,
    )

    payload = _build_dev_broadcast(
        "\\\\?\\USB#VID_046D&PID_C534#serial-1#{a5dcbf10-6530-11d2-901f-00c04fb951ed}")
    msg = _build_msg(wparam=DBT_DEVICEREMOVECOMPLETE, lparam=ctypes.addressof(payload))

    result = listener._handle_native_message(ctypes.addressof(msg))
    assert result is not None
    notif_type, _ = result
    assert notif_type is DeviceNotificationType.DELETION


def test_handle_native_message_filters_non_usb_devices(listener):
    """Hub/root entries are real device-interface arrivals too, but the
    plugin's settings only match VID/PID-bearing USB endpoints."""
    from swiss_windows_knife.plugins.device_display_mapper.device_listener import (
        DBT_DEVICEARRIVAL,
    )

    payload = _build_dev_broadcast(
        "\\\\?\\USB#ROOT_HUB30#4&12345&0&0#{a5dcbf10-6530-11d2-901f-00c04fb951ed}")
    msg = _build_msg(wparam=DBT_DEVICEARRIVAL, lparam=ctypes.addressof(payload))

    assert listener._handle_native_message(ctypes.addressof(msg)) is None


def test_handle_native_message_ignores_non_interface_broadcasts(listener):
    """Volume / port / handle broadcasts use the same WM_DEVICECHANGE but
    a different dbch_devicetype — they must not be parsed as interfaces."""
    from swiss_windows_knife.plugins.device_display_mapper.device_listener import (
        _DEV_BROADCAST_HDR,
        DBT_DEVICEARRIVAL,
    )

    buf = (ctypes.c_ubyte * ctypes.sizeof(_DEV_BROADCAST_HDR))()
    hdr = _DEV_BROADCAST_HDR.from_address(ctypes.addressof(buf))
    hdr.dbch_size = ctypes.sizeof(_DEV_BROADCAST_HDR)
    hdr.dbch_devicetype = 0x00000002  # DBT_DEVTYP_VOLUME
    msg = _build_msg(wparam=DBT_DEVICEARRIVAL, lparam=ctypes.addressof(buf))

    assert listener._handle_native_message(ctypes.addressof(msg)) is None


def test_native_event_emits_change_detected(qtbot, listener):
    from swiss_windows_knife.plugins.device_display_mapper.device_listener import (
        DBT_DEVICEARRIVAL,
        DeviceNotificationType,
    )

    payload = _build_dev_broadcast(
        "\\\\?\\USB#VID_AAAA&PID_BBBB#xyz#{a5dcbf10-6530-11d2-901f-00c04fb951ed}")
    msg = _build_msg(wparam=DBT_DEVICEARRIVAL, lparam=ctypes.addressof(payload))

    with qtbot.waitSignal(listener.change_detected, timeout=500) as blocker:
        handled, result = listener.nativeEvent(b"windows_generic_MSG", ctypes.addressof(msg))

    assert handled is False
    assert result == 0
    notif_type, device = blocker.args
    assert notif_type is DeviceNotificationType.CREATION
    assert device.id == "USB\\VID_AAAA&PID_BBBB\\xyz"


def test_native_event_ignores_non_windows_event_types(listener):
    handled, result = listener.nativeEvent(b"xcb_generic_event_t", 0)
    assert handled is False
    assert result == 0


def test_close_event_unregisters_notification(qtbot, monkeypatch):
    """Cleanup path: closing the listener must release the OS-side
    device-notification subscription."""
    from swiss_windows_knife.plugins.device_display_mapper import device_listener as m

    monkeypatch.setattr(m.DeviceListener, "_register_for_notifications", lambda self: None)
    fake_user32 = MagicMock()
    monkeypatch.setattr(m, "_user32", fake_user32)

    listener = m.DeviceListener(parent=None)
    qtbot.addWidget(listener)
    listener._notify_handle = 0xABCD1234

    event = MagicMock()
    listener.closeEvent(event)

    fake_user32.UnregisterDeviceNotification.assert_called_once_with(0xABCD1234)
    assert listener._notify_handle is None
    event.accept.assert_called_once()


def test_close_event_no_op_when_not_registered(qtbot, monkeypatch):
    from swiss_windows_knife.plugins.device_display_mapper import device_listener as m

    monkeypatch.setattr(m.DeviceListener, "_register_for_notifications", lambda self: None)
    fake_user32 = MagicMock()
    monkeypatch.setattr(m, "_user32", fake_user32)

    listener = m.DeviceListener(parent=None)
    qtbot.addWidget(listener)
    assert listener._notify_handle is None

    event = MagicMock()
    listener.closeEvent(event)

    fake_user32.UnregisterDeviceNotification.assert_not_called()
    event.accept.assert_called_once()
