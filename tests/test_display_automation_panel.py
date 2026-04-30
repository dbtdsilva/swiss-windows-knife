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
