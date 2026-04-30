import pytest

from src.base.health import HealthState


@pytest.fixture
def configured_settings(fake_user_settings):
    fake_user_settings.set("homeassistant_host", "broker")
    fake_user_settings.set("homeassistant_port", 1883)
    fake_user_settings.set("homeassistant_username", "u")
    fake_user_settings.set("homeassistant_password", "p")
    fake_user_settings.set("homeassistant_client_id", "cid")
    fake_user_settings.set("homeassistant_device_name", "TestPC")
    return fake_user_settings


def _make_plugin(qtbot):
    from src.plugins.home_assistant_mqtt_pub.home_assistant_mqtt_pub_plugin import (
        HomeAssistantMqttPubPlugin,
    )
    plugin = HomeAssistantMqttPubPlugin(parent=None)
    qtbot.addWidget(plugin)
    return plugin


def test_health_is_warning_not_configured_when_no_config(qtbot, fake_user_settings, fake_paho_client):
    plugin = _make_plugin(qtbot)
    report = plugin.health()
    assert report.state is HealthState.WARNING
    assert report.message == "Not configured"


def test_health_is_warning_connecting_after_session_starts(qtbot, configured_settings, fake_paho_client):
    plugin = _make_plugin(qtbot)
    report = plugin.health()
    assert report.state is HealthState.WARNING
    assert report.message == "Connecting…"


def test_health_is_ok_connected_after_on_connect(qtbot, configured_settings, fake_paho_client):
    plugin = _make_plugin(qtbot)
    fake_paho_client[0].fire_on_connect(rc=0)
    qtbot.wait(20)  # cross to GUI thread via QMetaObject.invokeMethod
    report = plugin.health()
    assert report.state is HealthState.OK
    assert report.message == "Connected"


def test_health_returns_to_warning_after_disconnect(qtbot, configured_settings, fake_paho_client):
    plugin = _make_plugin(qtbot)
    fake_paho_client[0].fire_on_connect(rc=0)
    fake_paho_client[0].fire_on_disconnect(rc=0)
    qtbot.wait(20)  # cross to GUI thread via QMetaObject.invokeMethod
    report = plugin.health()
    assert report.state is HealthState.WARNING
    assert report.message == "Disconnected"


def test_retrieve_menus_no_longer_returns_status_submenu(qtbot, configured_settings, fake_paho_client):
    plugin = _make_plugin(qtbot)
    assert plugin.retrieve_menus() == []
