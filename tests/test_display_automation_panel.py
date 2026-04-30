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
    assert fake_user_settings.get_optional_str('display_usb_watcher') is None


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
    assert fake_user_settings.get_optional_str('display_usb_watcher') == "USB\\VID_9999&PID_1111\\BBB"


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
    assert fake_user_settings.get_optional_str('display_usb_watcher') is None


def test_panel_renders_per_monitor_input_choices_and_persists(make_panel, fake_user_settings):
    monitors = [
        _FakeMonitorInfo(
            device_id="MON-A-DEVID",
            device_name="\\\\.\\DISPLAY1",
            model="Dell U2723QE",
            inputs=["DP1", "HDMI1", "USBC"],
        ),
        _FakeMonitorInfo(
            device_id="MON-B-DEVID",
            device_name="\\\\.\\DISPLAY2",
            model="LG 27UP850",
            inputs=["DP1", "HDMI2"],
        ),
    ]
    panel = make_panel(monitors=monitors, usb_devices=[])

    assert "MON-A-DEVID" in panel._monitor_groups
    assert "MON-B-DEVID" in panel._monitor_groups

    a = panel._monitor_groups["MON-A-DEVID"]
    # Each combobox has the inputs plus a "(unchanged)" sentinel at index 0.
    assert a["connect_combo"].count() == 1 + 3
    assert a["disconnect_combo"].count() == 1 + 3

    a["connect_combo"].setCurrentIndex(2)     # "HDMI1" on connect
    a["disconnect_combo"].setCurrentIndex(1)  # "DP1" on disconnect

    assert panel.apply() is True
    assert fake_user_settings.get_optional_str('display_on_connect_MON-A-DEVID') == "HDMI1"
    assert fake_user_settings.get_optional_str('display_on_disconnect_MON-A-DEVID') == "DP1"
    # Untouched monitor keeps its "(unchanged)" sentinel — no key written.
    assert fake_user_settings.get_optional_str('display_on_connect_MON-B-DEVID') is None


def test_panel_populates_when_discovery_completes_async(qtbot, fake_user_settings, silent_messagebox):
    """When schedule_discovery defers `_populate`, the panel still shows the
    placeholder before discovery and the widgets after."""
    from src.plugins.device_display_mapper.display_automation_panel import (
        DisplayAutomationConfigPanel,
    )
    deferred: list = []

    panel = DisplayAutomationConfigPanel(
        parent=None,
        list_monitors=lambda: [],
        list_usb_devices=lambda: [_FakeDevice(id="X", name="X")],
        schedule_discovery=lambda fn: deferred.append(fn),
    )
    qtbot.addWidget(panel)

    assert panel._placeholder.isHidden() is False  # placeholder visible
    assert panel._usb_combo is None  # not yet populated

    # Simulate async completion.
    for fn in deferred:
        fn()

    assert panel._placeholder.isHidden() is True
    assert panel._usb_combo is not None


def test_panel_preselects_existing_per_monitor_choice(make_panel, fake_user_settings):
    fake_user_settings.set('display_on_connect_MON-A-DEVID', "HDMI1")
    fake_user_settings.set('display_on_disconnect_MON-A-DEVID', "DP1")
    monitors = [
        _FakeMonitorInfo(
            device_id="MON-A-DEVID",
            device_name="\\\\.\\DISPLAY1",
            model="Dell U2723QE",
            inputs=["DP1", "HDMI1", "USBC"],
        ),
    ]
    panel = make_panel(monitors=monitors, usb_devices=[])

    a = panel._monitor_groups["MON-A-DEVID"]
    # "HDMI1" is index 2 (after the "(unchanged)" sentinel + "DP1" at index 1).
    assert a["connect_combo"].currentText() == "HDMI1"
    assert a["disconnect_combo"].currentText() == "DP1"
