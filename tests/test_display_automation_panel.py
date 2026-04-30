import pytest


class _FakeMonitorInfo:
    def __init__(self, device_id, device_name, model, inputs):
        self.device_id = device_id
        self.device_name = device_name
        self.model = model
        self.inputs = inputs


class _FakeDevice:
    def __init__(self, id, name, description="", manufacturer=""):
        self.id = id
        self.name = name
        self.description = description
        self.manufacturer = manufacturer


@pytest.fixture
def make_panel(qtbot, fake_user_settings, silent_messagebox):
    """Build a panel with controllable, sync providers."""
    from src.plugins.device_display_mapper.display_automation_panel import (
        DisplayAutomationConfigPanel,
    )

    def _make(monitors=None, usb_devices=None):
        panel = DisplayAutomationConfigPanel(
            parent=None,
            list_monitors=lambda: list(monitors or []),
            list_usb_devices=lambda: list(usb_devices or []),
            schedule_discovery=lambda fn: fn(),  # run inline for tests
        )
        qtbot.addWidget(panel)
        return panel

    return _make


def test_panel_with_no_monitors_or_devices_apply_is_noop(make_panel, fake_user_settings):
    panel = make_panel(monitors=[], usb_devices=[])
    assert panel.apply() is True
    # No settings should be written when there is nothing to choose from.
    assert fake_user_settings.get('display_usb_watcher') is None


def test_panel_renders_usb_devices_and_persists_selection(make_panel, fake_user_settings):
    devices = [
        _FakeDevice(id="USB\\VID_1234&PID_5678\\AAA", name="Dock A", description="USB-C dock"),
        _FakeDevice(id="USB\\VID_9999&PID_1111\\BBB", name="Mouse", description="Optical mouse"),
    ]
    panel = make_panel(monitors=[], usb_devices=devices)

    assert panel._usb_combo is not None
    # First entry is the "(none)" option, then one entry per device, in input order.
    assert panel._usb_combo.count() == 1 + len(devices)

    panel._usb_combo.setCurrentIndex(2)  # Select "Mouse"
    assert panel.apply() is True
    assert fake_user_settings.get('display_usb_watcher') == "USB\\VID_9999&PID_1111\\BBB"


def test_panel_preselects_existing_usb_watcher(make_panel, fake_user_settings):
    fake_user_settings.set('display_usb_watcher', "USB\\VID_1234&PID_5678\\AAA")
    devices = [
        _FakeDevice(id="USB\\VID_1234&PID_5678\\AAA", name="Dock A"),
        _FakeDevice(id="USB\\VID_9999&PID_1111\\BBB", name="Mouse"),
    ]
    panel = make_panel(monitors=[], usb_devices=devices)

    # Index 1 is the first device in our list; 0 is the "(none)" sentinel.
    assert panel._usb_combo.currentIndex() == 1


def test_panel_apply_with_none_clears_usb_watcher(make_panel, fake_user_settings):
    fake_user_settings.set('display_usb_watcher', "USB\\VID_1234&PID_5678\\AAA")
    devices = [_FakeDevice(id="USB\\VID_1234&PID_5678\\AAA", name="Dock A")]
    panel = make_panel(monitors=[], usb_devices=devices)
    panel._usb_combo.setCurrentIndex(0)  # "(none)"

    assert panel.apply() is True
    assert fake_user_settings.get('display_usb_watcher') is None
