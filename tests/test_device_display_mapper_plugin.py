import pytest


class _FakeDeviceListener:
    """Minimal stand-in: tracks construction and close calls without
    spinning up real WMI watchers."""

    instances: list["_FakeDeviceListener"] = []

    def __init__(self, parent):
        self.closed = False
        self.parent = parent

        class _Sig:
            def connect(self, *_args, **_kwargs):
                pass

        self.change_detected = _Sig()
        _FakeDeviceListener.instances.append(self)

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def _reset_fake_instances():
    _FakeDeviceListener.instances.clear()
    yield
    _FakeDeviceListener.instances.clear()


@pytest.fixture
def plugin(qtbot, fake_user_settings, monkeypatch):
    """Construct the plugin with the WMI device-listener stubbed out."""
    monkeypatch.setattr(
        "swiss_windows_knife.plugins.device_display_mapper.device_display_mapper_plugin.DeviceListener",
        _FakeDeviceListener,
    )
    monkeypatch.setattr(
        "swiss_windows_knife.plugins.device_display_mapper.device_display_mapper_plugin."
        "DeviceDisplayMapperPlugin._prewarm_monitor_cache",
        lambda self: None,
    )
    monkeypatch.setattr(
        "swiss_windows_knife.plugins.device_display_mapper.device_display_mapper_plugin."
        "DeviceDisplayMapperPlugin.request_usb_devices",
        lambda self, cb: None,
    )

    from swiss_windows_knife.plugins.device_display_mapper.device_display_mapper_plugin import (
        DeviceDisplayMapperPlugin,
    )
    p = DeviceDisplayMapperPlugin(None)
    qtbot.addWidget(p)
    return p


def test_listener_started_when_enabled(plugin):
    assert plugin.device_listener is not None
    assert len(_FakeDeviceListener.instances) == 1


def test_status_changed_false_closes_listener(plugin):
    plugin.status_changed(False)
    assert plugin.device_listener is None
    assert _FakeDeviceListener.instances[-1].closed is True


def test_status_changed_true_creates_new_listener(plugin):
    plugin.status_changed(False)
    plugin.status_changed(True)
    assert plugin.device_listener is not None
    assert len(_FakeDeviceListener.instances) == 2


def test_construction_skips_listener_when_persisted_disabled(qtbot, fake_user_settings, monkeypatch):
    fake_user_settings.set('plugin_enabled_DeviceDisplayMapperPlugin', False)
    monkeypatch.setattr(
        "swiss_windows_knife.plugins.device_display_mapper.device_display_mapper_plugin.DeviceListener",
        _FakeDeviceListener,
    )
    monkeypatch.setattr(
        "swiss_windows_knife.plugins.device_display_mapper.device_display_mapper_plugin."
        "DeviceDisplayMapperPlugin._prewarm_monitor_cache",
        lambda self: None,
    )
    monkeypatch.setattr(
        "swiss_windows_knife.plugins.device_display_mapper.device_display_mapper_plugin."
        "DeviceDisplayMapperPlugin.request_usb_devices",
        lambda self, cb: None,
    )

    from swiss_windows_knife.plugins.device_display_mapper.device_display_mapper_plugin import (
        DeviceDisplayMapperPlugin,
    )
    p = DeviceDisplayMapperPlugin(None)
    qtbot.addWidget(p)
    assert p.device_listener is None
    assert _FakeDeviceListener.instances == []
