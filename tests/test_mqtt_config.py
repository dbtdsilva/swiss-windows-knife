import pytest

from src.plugins.home_assistant_mqtt_pub.mqtt_config import MqttConfig


class FakeSettings:
    """Stand-in for UserSettings backed by a plain dict."""

    def __init__(self, initial=None):
        self._data = dict(initial or {})

    def get(self, key):
        return self._data.get(key)

    def has_key(self, key):
        return key in self._data

    def set(self, key, value):
        self._data[key] = value


def test_load_from_settings_pulls_all_known_keys():
    settings = FakeSettings({
        'homeassistant_host': 'broker.example.com',
        'homeassistant_port': '1883',
        'homeassistant_username': 'user',
        'homeassistant_password': 'pass',
        'homeassistant_client_id': 'client-1',
    })
    config = MqttConfig.load_from_settings(settings)
    assert config.host == 'broker.example.com'
    assert config.port == '1883'
    assert config.username == 'user'
    assert config.password == 'pass'
    assert config.client_id == 'client-1'


def test_load_from_settings_returns_none_for_missing_keys():
    config = MqttConfig.load_from_settings(FakeSettings())
    assert config.host is None
    assert config.port is None
    assert config.username is None
    assert config.password is None
    assert config.client_id is None


def test_save_to_settings_writes_all_keys():
    config = MqttConfig(
        host='broker.example.com',
        port=1883,
        username='user',
        password='pass',
        client_id='client-1',
    )
    settings = FakeSettings()
    config.save_to_settings(settings)

    assert settings.get('homeassistant_host') == 'broker.example.com'
    assert settings.get('homeassistant_port') == 1883
    assert settings.get('homeassistant_username') == 'user'
    assert settings.get('homeassistant_password') == 'pass'
    assert settings.get('homeassistant_client_id') == 'client-1'


def test_round_trip_preserves_values():
    initial = {
        'homeassistant_host': 'h',
        'homeassistant_port': '1883',
        'homeassistant_username': 'u',
        'homeassistant_password': 'p',
        'homeassistant_client_id': 'c',
    }
    config = MqttConfig.load_from_settings(FakeSettings(initial))
    written = FakeSettings()
    config.save_to_settings(written)
    for key, value in initial.items():
        assert written.get(key) == value
