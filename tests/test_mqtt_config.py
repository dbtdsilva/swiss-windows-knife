from swiss_windows_knife.plugins.home_assistant_mqtt_pub.mqtt_config import MqttConfig

from .conftest import _FakeUserSettings


def _settings(initial=None) -> _FakeUserSettings:
    s = _FakeUserSettings()
    for key, value in (initial or {}).items():
        s.set(key, value)
    return s


def test_load_from_settings_pulls_all_known_keys():
    config = MqttConfig.load_from_settings(_settings({
        'homeassistant_host': 'broker.example.com',
        'homeassistant_port': '1883',
        'homeassistant_username': 'user',
        'homeassistant_password': 'pass',
        'homeassistant_client_id': 'client-1',
    }))
    assert config.host == 'broker.example.com'
    assert config.port == 1883  # coerced from string by the int branch
    assert config.username == 'user'
    assert config.password == 'pass'
    assert config.client_id == 'client-1'


def test_load_from_settings_returns_none_for_missing_keys():
    config = MqttConfig.load_from_settings(_settings())
    assert config.host is None
    assert config.port is None
    assert config.username is None
    assert config.password is None
    assert config.client_id is None


def test_load_from_settings_treats_empty_string_as_none():
    """Windows QSettings can return empty strings for cleared values."""
    config = MqttConfig.load_from_settings(_settings({
        'homeassistant_host': '',
        'homeassistant_port': '',
        'homeassistant_username': '',
    }))
    assert config.host is None
    assert config.port is None
    assert config.username is None


def test_save_to_settings_writes_all_keys():
    config = MqttConfig(
        host='broker.example.com',
        port=1883,
        username='user',
        password='pass',
        client_id='client-1',
    )
    settings = _settings()
    config.save_to_settings(settings)

    assert settings.get('homeassistant_host', str) == 'broker.example.com'
    assert settings.get('homeassistant_port', int) == 1883
    assert settings.get('homeassistant_username', str) == 'user'
    assert settings.get('homeassistant_password', str) == 'pass'
    assert settings.get('homeassistant_client_id', str) == 'client-1'


def test_round_trip_normalises_port_to_int():
    initial = {
        'homeassistant_host': 'h',
        'homeassistant_port': '1883',
        'homeassistant_username': 'u',
        'homeassistant_password': 'p',
        'homeassistant_client_id': 'c',
    }
    config = MqttConfig.load_from_settings(_settings(initial))
    written = _settings()
    config.save_to_settings(written)
    assert written.get('homeassistant_host', str) == 'h'
    assert written.get('homeassistant_port', int) == 1883
    assert written.get('homeassistant_username', str) == 'u'
    assert written.get('homeassistant_password', str) == 'p'
    assert written.get('homeassistant_client_id', str) == 'c'


def test_is_complete_true_when_all_fields_populated():
    config = MqttConfig(
        host='h', port=1883, username='u', password='p', client_id='c', device_name='d',
    )
    assert config.is_complete() is True


def test_is_complete_false_when_port_missing():
    config = MqttConfig(
        host='h', port=None, username='u', password='p', client_id='c', device_name='d',
    )
    assert config.is_complete() is False


def test_is_complete_false_when_string_field_empty():
    config = MqttConfig(
        host='', port=1883, username='u', password='p', client_id='c', device_name='d',
    )
    assert config.is_complete() is False
