from unittest.mock import MagicMock, patch

from swiss_windows_knife.plugins.home_assistant_mqtt_pub.entities.lock_state import (
    WTS_SESSION_LOCK,
    WTS_SESSION_UNLOCK,
    LockStateEntity,
)


def test_metadata_event_driven(qapp):
    e = LockStateEntity()
    assert e.is_event_driven is True
    assert e.default_interval_s is None
    assert e.component == "binary_sensor"


def test_dispatch_lock_emits_true(qtbot):
    e = LockStateEntity()
    received = []
    e.subscribe(lambda result: received.append(result))
    e._dispatch_session_event(WTS_SESSION_LOCK)
    assert received[-1].is_available is True
    assert received[-1].value is True


def test_dispatch_unlock_emits_false(qtbot):
    e = LockStateEntity()
    received = []
    e.subscribe(lambda result: received.append(result))
    e._dispatch_session_event(WTS_SESSION_UNLOCK)
    assert received[-1].value is False


def test_initial_sample_via_wts_query(qtbot):
    e = LockStateEntity()
    fake_user32 = MagicMock()
    fake_user32.OpenInputDesktop.return_value = 1
    fake_user32.SwitchDesktop.return_value = 1  # not locked

    with patch("ctypes.windll", MagicMock(user32=fake_user32)):
        r = e.sample()
    assert r.is_available is True
    assert r.value is False  # unlocked
