"""Coverage for the WMI device-listener shutdown path.

Tray shutdown depends on `_DeviceListenerThread.run` exiting on
interruption and unwinding COM, and on `DeviceListener.closeEvent`
joining both watcher threads. A regression in either manifests as
"tray won't quit cleanly".
"""
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def _listener_module():
    import swiss_windows_knife.plugins.device_display_mapper.device_listener as m
    return m


def _run_with_iterations(thread, listener_module, iterations, watcher):
    """Drive `thread.run()` with a controlled isInterruptionRequested
    sequence and a mocked wmi + pythoncom environment. Returns the
    pythoncom mock so callers can assert on Co(Un)Initialize."""
    # `except wmi.x_wmi_timed_out:` in the source needs the real
    # exception class; capture it before the patch swaps `wmi` for a Mock.
    real_x_wmi_timed_out = listener_module.wmi.x_wmi_timed_out
    fake_wmi = MagicMock()
    fake_wmi.watch_for.return_value = watcher

    with patch.object(thread, "isInterruptionRequested", side_effect=lambda: next(iterations)), \
         patch.object(listener_module, "wmi") as mock_wmi_mod, \
         patch.object(listener_module, "pythoncom") as mock_pythoncom:
        mock_wmi_mod.x_wmi_timed_out = real_x_wmi_timed_out
        mock_wmi_mod.WMI.return_value = fake_wmi
        thread.run()
        return mock_pythoncom, fake_wmi


def test_listener_thread_initializes_com_and_uninitializes_on_interrupt(_listener_module):
    from swiss_windows_knife.plugins.device_display_mapper.device_listener import (
        DeviceNotificationType,
        _DeviceListenerThread,
    )

    signal = MagicMock()
    thread = _DeviceListenerThread(
        parent=None,
        parent_signal=signal,
        notification_type=DeviceNotificationType.CREATION,
    )
    watcher = MagicMock(side_effect=_listener_module.wmi.x_wmi_timed_out)
    iterations = iter([False, True])

    pythoncom_mock, fake_wmi = _run_with_iterations(thread, _listener_module, iterations, watcher)

    assert pythoncom_mock.CoInitialize.called
    assert pythoncom_mock.CoUninitialize.called
    signal.emit.assert_not_called()
    fake_wmi.watch_for.assert_called_once_with(
        notification_type="Creation",
        wmi_class="Win32_PnPEntity",
        delay_secs=1,
    )


def test_listener_thread_emits_signal_on_wmi_event(_listener_module):
    from swiss_windows_knife.plugins.device_display_mapper.device_listener import (
        Device,
        DeviceNotificationType,
        _DeviceListenerThread,
    )

    signal = MagicMock()
    thread = _DeviceListenerThread(
        parent=None,
        parent_signal=signal,
        notification_type=DeviceNotificationType.DELETION,
    )
    fake_usb = MagicMock(
        DeviceID="USB\\VID_046D&PID_C534\\1234",
        Name="USB Receiver",
        Description="USB Composite Device",
        Manufacturer="Logitech",
    )
    watcher = MagicMock(return_value=fake_usb)
    iterations = iter([False, True])

    pythoncom_mock, _ = _run_with_iterations(thread, _listener_module, iterations, watcher)

    assert pythoncom_mock.CoUninitialize.called
    signal.emit.assert_called_once()
    notif_type, device = signal.emit.call_args.args
    assert notif_type is DeviceNotificationType.DELETION
    assert isinstance(device, Device)
    assert device.id == "USB\\VID_046D&PID_C534\\1234"
    assert device.name == "USB Receiver"
    assert device.manufacturer == "Logitech"


def test_listener_thread_skips_event_with_bad_attributes(_listener_module):
    """A WMI event that loses its backing object mid-read raises on
    attribute access. The loop must log and keep going, not exit."""
    from swiss_windows_knife.plugins.device_display_mapper.device_listener import (
        DeviceNotificationType,
        _DeviceListenerThread,
    )

    signal = MagicMock()
    thread = _DeviceListenerThread(
        parent=None,
        parent_signal=signal,
        notification_type=DeviceNotificationType.CREATION,
    )
    bad_usb = MagicMock()
    type(bad_usb).DeviceID = property(lambda self: (_ for _ in ()).throw(RuntimeError("gone")))
    watcher = MagicMock(return_value=bad_usb)
    iterations = iter([False, True])

    pythoncom_mock, _ = _run_with_iterations(thread, _listener_module, iterations, watcher)

    assert pythoncom_mock.CoUninitialize.called
    signal.emit.assert_not_called()


def test_close_event_interrupts_and_waits_for_both_listener_threads(qtbot, monkeypatch):
    fake_threads: list = []

    class _FakeListenerThread:
        def __init__(self, parent, parent_signal, notification_type):
            self.notification_type = notification_type
            self.started = False
            self.interrupted = False
            self.waited = False
            fake_threads.append(self)

        def start(self):
            self.started = True

        def requestInterruption(self):
            self.interrupted = True

        def wait(self):
            self.waited = True

    monkeypatch.setattr(
        "swiss_windows_knife.plugins.device_display_mapper.device_listener.wmi.WMI",
        MagicMock(),
    )
    monkeypatch.setattr(
        "swiss_windows_knife.plugins.device_display_mapper.device_listener._DeviceListenerThread",
        _FakeListenerThread,
    )

    from swiss_windows_knife.plugins.device_display_mapper.device_listener import DeviceListener
    listener = DeviceListener(parent=None)
    qtbot.addWidget(listener)

    assert len(fake_threads) == 2
    assert all(t.started for t in fake_threads)
    notif_types = {t.notification_type for t in fake_threads}
    from swiss_windows_knife.plugins.device_display_mapper.device_listener import DeviceNotificationType
    assert notif_types == {DeviceNotificationType.CREATION, DeviceNotificationType.DELETION}

    event = MagicMock()
    listener.closeEvent(event)

    assert all(t.interrupted for t in fake_threads)
    assert all(t.waited for t in fake_threads)
    event.accept.assert_called_once()
