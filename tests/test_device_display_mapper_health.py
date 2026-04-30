import pytest

from src.base.health import HealthState


class _FakeDeviceListener:
    instances: list = []

    def __init__(self, parent):
        self.closed = False

        class _Sig:
            def connect(self, *_args, **_kwargs):
                pass

        self.change_detected = _Sig()
        _FakeDeviceListener.instances.append(self)

    def close(self):
        self.closed = True


class _ExplodingListener:
    def __init__(self, parent):
        raise RuntimeError("WMI unavailable")


@pytest.fixture(autouse=True)
def _reset():
    _FakeDeviceListener.instances.clear()
    yield
    _FakeDeviceListener.instances.clear()


def _patch(monkeypatch, listener_cls):
    monkeypatch.setattr(
        "src.plugins.device_display_mapper.device_display_mapper_plugin.DeviceListener",
        listener_cls,
    )
    monkeypatch.setattr(
        "src.plugins.device_display_mapper.device_display_mapper_plugin."
        "DeviceDisplayMapperPlugin._prewarm_monitor_cache",
        lambda self: None,
    )
    monkeypatch.setattr(
        "src.plugins.device_display_mapper.device_display_mapper_plugin."
        "DeviceDisplayMapperPlugin.request_usb_devices",
        lambda self, cb: None,
    )


def test_health_is_ok_listening_on_successful_start(qtbot, fake_user_settings, monkeypatch):
    _patch(monkeypatch, _FakeDeviceListener)
    from src.plugins.device_display_mapper.device_display_mapper_plugin import (
        DeviceDisplayMapperPlugin,
    )
    p = DeviceDisplayMapperPlugin(None)
    qtbot.addWidget(p)
    assert p.health().state is HealthState.OK
    assert p.health().message == "Listening"


def test_health_is_error_when_listener_construction_fails(qtbot, fake_user_settings, monkeypatch):
    _patch(monkeypatch, _ExplodingListener)
    from src.plugins.device_display_mapper.device_display_mapper_plugin import (
        DeviceDisplayMapperPlugin,
    )
    p = DeviceDisplayMapperPlugin(None)
    qtbot.addWidget(p)
    assert p.health().state is HealthState.ERROR
    assert "WMI unavailable" in p.health().message
