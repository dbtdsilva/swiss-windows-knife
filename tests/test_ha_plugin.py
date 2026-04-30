import pytest


@pytest.fixture
def configured_settings(fake_user_settings):
    fake_user_settings.set("homeassistant_host", "broker")
    fake_user_settings.set("homeassistant_port", 1883)
    fake_user_settings.set("homeassistant_username", "u")
    fake_user_settings.set("homeassistant_password", "p")
    fake_user_settings.set("homeassistant_client_id", "cid")
    fake_user_settings.set("homeassistant_device_name", "TestPC")
    return fake_user_settings


def test_plugin_starts_session_when_fully_configured(qtbot, configured_settings, fake_paho_client):
    from swiss_windows_knife.plugins.home_assistant_mqtt_pub.home_assistant_mqtt_pub_plugin import (
        HomeAssistantMqttPubPlugin,
    )
    plugin = HomeAssistantMqttPubPlugin(parent=None)
    qtbot.addWidget(plugin)
    assert plugin.is_homeassistant_configured is True
    assert len(fake_paho_client) == 1


def test_plugin_inert_when_unconfigured(qtbot, fake_user_settings, fake_paho_client):
    from swiss_windows_knife.plugins.home_assistant_mqtt_pub.home_assistant_mqtt_pub_plugin import (
        HomeAssistantMqttPubPlugin,
    )
    plugin = HomeAssistantMqttPubPlugin(parent=None)
    qtbot.addWidget(plugin)
    assert plugin.is_homeassistant_configured is False
    assert len(fake_paho_client) == 0


def test_status_changed_accepts_bool_signature(qtbot, configured_settings, fake_paho_client):
    from swiss_windows_knife.plugins.home_assistant_mqtt_pub.home_assistant_mqtt_pub_plugin import (
        HomeAssistantMqttPubPlugin,
    )
    plugin = HomeAssistantMqttPubPlugin(parent=None)
    qtbot.addWidget(plugin)
    plugin.status_changed(False)  # must not raise


def test_disable_deletes_discovery_and_disconnects(qtbot, configured_settings, fake_paho_client):
    from swiss_windows_knife.plugins.home_assistant_mqtt_pub.home_assistant_mqtt_pub_plugin import (
        HomeAssistantMqttPubPlugin,
    )
    plugin = HomeAssistantMqttPubPlugin(parent=None)
    qtbot.addWidget(plugin)
    fake_paho_client[0].fire_on_connect(rc=0)
    fake_paho_client[0].published.clear()
    plugin.set_enabled(False)
    deletion_publishes = [
        (topic, payload) for (topic, payload, _retain) in fake_paho_client[0].published
        if topic.endswith("/config") and payload == ""
    ]
    assert deletion_publishes, "expected at least one empty-payload publish for entity discovery deletion"
    assert fake_paho_client[0].connected is False
