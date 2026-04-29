import pytest


@pytest.fixture
def panel(qtbot, fake_user_settings):
    from src.plugins.home_assistant_mqtt_pub.mqtt_config_panel import MqttConfigPanel
    p = MqttConfigPanel()
    qtbot.addWidget(p)
    return p


def test_apply_persists_all_fields(panel, fake_user_settings):
    panel.login_field.setText("user1")
    panel.password_field.setText("secret")
    panel.host_field.setText("broker.example.com")
    panel.port_field.setText("1883")
    panel.client_id_field.setText("client-x")

    assert panel.apply() is True
    assert fake_user_settings.get('homeassistant_username') == "user1"
    assert fake_user_settings.get('homeassistant_password') == "secret"
    assert fake_user_settings.get('homeassistant_host') == "broker.example.com"
    assert fake_user_settings.get('homeassistant_port') == 1883
    assert fake_user_settings.get('homeassistant_client_id') == "client-x"


def test_init_loads_existing_values(qtbot, fake_user_settings):
    fake_user_settings.set('homeassistant_host', 'h')
    fake_user_settings.set('homeassistant_port', '1883')
    fake_user_settings.set('homeassistant_username', 'u')
    fake_user_settings.set('homeassistant_password', 'p')
    fake_user_settings.set('homeassistant_client_id', 'c')

    from src.plugins.home_assistant_mqtt_pub.mqtt_config_panel import MqttConfigPanel
    p = MqttConfigPanel()
    qtbot.addWidget(p)

    assert p.host_field.text() == 'h'
    assert p.port_field.text() == '1883'
    assert p.login_field.text() == 'u'
    assert p.password_field.text() == 'p'
    assert p.client_id_field.text() == 'c'


def test_init_handles_completely_empty_settings(qtbot, fake_user_settings):
    from src.plugins.home_assistant_mqtt_pub.mqtt_config_panel import MqttConfigPanel
    p = MqttConfigPanel()
    qtbot.addWidget(p)

    assert p.host_field.text() == ''
    assert p.port_field.text() == ''
    assert p.login_field.text() == ''
    assert p.password_field.text() == ''
    assert p.client_id_field.text() == ''
