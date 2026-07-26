"""Coverage for the WM_POWERBROADCAST-based display wake listener.

The display tuner re-asserts brightness/contrast when `DisplayWakeListener`
emits `woke`. That must fire on a genuine monitor off->on transition (DPMS)
and on system resume, but not on redundant "on" broadcasts or unrelated
power settings.
"""
import ctypes
from unittest.mock import MagicMock

import pytest


def _build_msg(wparam: int, lparam: int, message: int | None = None):
    from swiss_windows_knife.plugins.display_image_tuner.display_wake_listener import (
        _MSG,
        WM_POWERBROADCAST,
    )
    msg = _MSG()
    msg.message = WM_POWERBROADCAST if message is None else message
    msg.wParam = wparam
    msg.lParam = lparam
    return msg


def _build_display_setting(data: int) -> ctypes.Array:
    """Build a POWERBROADCAST_SETTING carrying GUID_CONSOLE_DISPLAY_STATE
    with `data` as the DWORD payload. Returns the backing buffer (keep a
    reference; lParam points into it)."""
    from swiss_windows_knife.plugins.display_image_tuner.display_wake_listener import (
        _POWERBROADCAST_SETTING,
        GUID_CONSOLE_DISPLAY_STATE,
    )
    buf = (ctypes.c_ubyte * ctypes.sizeof(_POWERBROADCAST_SETTING))()
    setting = _POWERBROADCAST_SETTING.from_address(ctypes.addressof(buf))
    setting.PowerSetting = GUID_CONSOLE_DISPLAY_STATE
    setting.DataLength = 4
    setting.Data = data
    return buf


@pytest.fixture
def listener(qtbot):
    from swiss_windows_knife.plugins.display_image_tuner.display_wake_listener import (
        DisplayWakeListener,
    )
    # _register_for_notifications is stubbed by the autouse conftest fixture.
    listener = DisplayWakeListener(parent=None)
    qtbot.addWidget(listener)
    return listener


def test_ignores_non_powerbroadcast(listener):
    msg = _build_msg(wparam=0, lparam=0, message=0x0001)
    assert listener._handle_power_message(ctypes.addressof(msg)) is False


def test_system_resume_automatic_is_wake(listener):
    from swiss_windows_knife.plugins.display_image_tuner.display_wake_listener import (
        PBT_APMRESUMEAUTOMATIC,
    )
    msg = _build_msg(wparam=PBT_APMRESUMEAUTOMATIC, lparam=0)
    assert listener._handle_power_message(ctypes.addressof(msg)) is True


def test_display_off_then_on_is_wake(listener):
    from swiss_windows_knife.plugins.display_image_tuner.display_wake_listener import (
        DISPLAY_STATE_OFF,
        DISPLAY_STATE_ON,
        PBT_POWERSETTINGCHANGE,
    )
    off = _build_display_setting(DISPLAY_STATE_OFF)
    off_msg = _build_msg(wparam=PBT_POWERSETTINGCHANGE, lparam=ctypes.addressof(off))
    assert listener._handle_power_message(ctypes.addressof(off_msg)) is False

    on = _build_display_setting(DISPLAY_STATE_ON)
    on_msg = _build_msg(wparam=PBT_POWERSETTINGCHANGE, lparam=ctypes.addressof(on))
    assert listener._handle_power_message(ctypes.addressof(on_msg)) is True


def test_display_on_when_already_on_is_not_wake(listener):
    from swiss_windows_knife.plugins.display_image_tuner.display_wake_listener import (
        DISPLAY_STATE_ON,
        PBT_POWERSETTINGCHANGE,
    )
    # Startup assumes displays are on; a redundant "on" is no transition.
    on = _build_display_setting(DISPLAY_STATE_ON)
    on_msg = _build_msg(wparam=PBT_POWERSETTINGCHANGE, lparam=ctypes.addressof(on))
    assert listener._handle_power_message(ctypes.addressof(on_msg)) is False


def test_wrong_power_setting_guid_ignored(listener):
    from swiss_windows_knife.plugins.display_image_tuner.display_wake_listener import (
        _POWERBROADCAST_SETTING,
        PBT_POWERSETTINGCHANGE,
    )
    buf = (ctypes.c_ubyte * ctypes.sizeof(_POWERBROADCAST_SETTING))()
    setting = _POWERBROADCAST_SETTING.from_address(ctypes.addressof(buf))
    setting.PowerSetting.Data1 = 0xDEADBEEF  # not GUID_CONSOLE_DISPLAY_STATE
    setting.DataLength = 4
    setting.Data = 1
    msg = _build_msg(wparam=PBT_POWERSETTINGCHANGE, lparam=ctypes.addressof(buf))
    assert listener._handle_power_message(ctypes.addressof(msg)) is False


def test_native_event_emits_woke_on_resume(qtbot, listener):
    from swiss_windows_knife.plugins.display_image_tuner.display_wake_listener import (
        PBT_APMRESUMEAUTOMATIC,
    )
    msg = _build_msg(wparam=PBT_APMRESUMEAUTOMATIC, lparam=0)
    with qtbot.waitSignal(listener.woke, timeout=500):
        handled, result = listener.nativeEvent(b"windows_generic_MSG", ctypes.addressof(msg))
    assert handled is False
    assert result == 0


def test_native_event_ignores_non_windows_event_types(listener):
    handled, result = listener.nativeEvent(b"xcb_generic_event_t", 0)
    assert handled is False
    assert result == 0


def test_close_event_unregisters(qtbot, monkeypatch):
    from swiss_windows_knife.plugins.display_image_tuner import display_wake_listener as m

    fake_user32 = MagicMock()
    monkeypatch.setattr(m, "_user32", fake_user32)
    listener = m.DisplayWakeListener(parent=None)
    qtbot.addWidget(listener)
    listener._notify_handle = 0xABCD1234

    event = MagicMock()
    listener.closeEvent(event)

    fake_user32.UnregisterPowerSettingNotification.assert_called_once_with(0xABCD1234)
    assert listener._notify_handle is None
    event.accept.assert_called_once()
