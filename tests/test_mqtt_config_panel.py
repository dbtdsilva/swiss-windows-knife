import pytest


@pytest.fixture
def panel(qtbot, fake_user_settings, silent_messagebox):
    from swiss_windows_knife.plugins.home_assistant_mqtt_pub.mqtt_config_panel import MqttConfigPanel
    p = MqttConfigPanel()
    qtbot.addWidget(p)
    return p


def test_apply_persists_all_fields(panel, fake_user_settings):
    panel.login_field.setText("user1")
    panel.password_field.setText("secret")
    panel.host_field.setText("broker.example.com")
    panel.port_field.setText("1883")
    panel.client_id_field.setText("client-x")
    panel.device_name_field.setText("PC")

    assert panel.apply() is True
    assert fake_user_settings.get_optional_str('homeassistant_username') == "user1"
    assert fake_user_settings.get_optional_str('homeassistant_password') == "secret"
    assert fake_user_settings.get_optional_str('homeassistant_host') == "broker.example.com"
    assert fake_user_settings.get_optional_int('homeassistant_port') == 1883
    assert fake_user_settings.get_optional_str('homeassistant_client_id') == "client-x"


def test_init_loads_existing_values(qtbot, fake_user_settings):
    fake_user_settings.set('homeassistant_host', 'h')
    fake_user_settings.set('homeassistant_port', '1883')
    fake_user_settings.set('homeassistant_username', 'u')
    fake_user_settings.set('homeassistant_password', 'p')
    fake_user_settings.set('homeassistant_client_id', 'c')

    from swiss_windows_knife.plugins.home_assistant_mqtt_pub.mqtt_config_panel import MqttConfigPanel
    p = MqttConfigPanel()
    qtbot.addWidget(p)

    assert p.host_field.text() == 'h'
    assert p.port_field.text() == '1883'
    assert p.login_field.text() == 'u'
    assert p.password_field.text() == 'p'
    assert p.client_id_field.text() == 'c'


def test_init_handles_completely_empty_settings(qtbot, fake_user_settings):
    from swiss_windows_knife.plugins.home_assistant_mqtt_pub.mqtt_config_panel import MqttConfigPanel
    p = MqttConfigPanel()
    qtbot.addWidget(p)

    assert p.host_field.text() == ''
    assert p.port_field.text() == ''
    assert p.login_field.text() == ''
    assert p.password_field.text() == ''
    assert p.client_id_field.text() == ''


def test_apply_coerces_port_to_int(qtbot, fake_user_settings, silent_messagebox):
    from swiss_windows_knife.plugins.home_assistant_mqtt_pub.mqtt_config_panel import MqttConfigPanel
    panel = MqttConfigPanel(parent=None)
    qtbot.addWidget(panel)
    panel.host_field.setText("broker")
    panel.port_field.setText("1883")
    panel.login_field.setText("u")
    panel.password_field.setText("p")
    panel.client_id_field.setText("cid")
    panel.device_name_field.setText("PC One")
    assert panel.apply() is True
    assert fake_user_settings.get_optional_int("homeassistant_port") == 1883


def test_apply_rejects_non_numeric_port(qtbot, fake_user_settings, silent_messagebox):
    from swiss_windows_knife.plugins.home_assistant_mqtt_pub.mqtt_config_panel import MqttConfigPanel
    panel = MqttConfigPanel(parent=None)
    qtbot.addWidget(panel)
    panel.host_field.setText("broker")
    panel.port_field.setText("not-a-port")
    panel.login_field.setText("u")
    panel.password_field.setText("p")
    panel.client_id_field.setText("cid")
    panel.device_name_field.setText("PC One")
    assert panel.apply() is False


def test_apply_rejects_empty_device_name(qtbot, fake_user_settings, silent_messagebox):
    from swiss_windows_knife.plugins.home_assistant_mqtt_pub.mqtt_config_panel import MqttConfigPanel
    panel = MqttConfigPanel(parent=None)
    qtbot.addWidget(panel)
    panel.host_field.setText("broker")
    panel.port_field.setText("1883")
    panel.login_field.setText("u")
    panel.password_field.setText("p")
    panel.client_id_field.setText("cid")
    panel.device_name_field.setText("   ")
    assert panel.apply() is False


def test_panel_shows_one_row_per_entity(qtbot, fake_user_settings, silent_messagebox):
    from swiss_windows_knife.plugins.home_assistant_mqtt_pub.entities import build_entity_registry
    from swiss_windows_knife.plugins.home_assistant_mqtt_pub.mqtt_config_panel import MqttConfigPanel
    panel = MqttConfigPanel(parent=None)
    qtbot.addWidget(panel)
    expected_keys = {e.key for e in build_entity_registry()}
    panel_keys = set(panel.entity_rows.keys())
    assert expected_keys.issubset(panel_keys)


def test_apply_persists_entity_publish_and_interval(qtbot, fake_user_settings, silent_messagebox):
    from swiss_windows_knife.plugins.home_assistant_mqtt_pub.mqtt_config_panel import MqttConfigPanel
    panel = MqttConfigPanel(parent=None)
    qtbot.addWidget(panel)
    panel.host_field.setText("broker")
    panel.port_field.setText("1883")
    panel.login_field.setText("u")
    panel.password_field.setText("p")
    panel.client_id_field.setText("cid")
    panel.device_name_field.setText("PC")
    row = panel.entity_rows["cpu_usage"]
    row.publish_checkbox.setChecked(False)
    row.interval_field.setText("90")
    assert panel.apply() is True
    assert fake_user_settings.get_bool("homeassistant_publish_cpu_usage", default=True) is False
    assert fake_user_settings.get_optional_int("homeassistant_interval_cpu_usage") == 90
