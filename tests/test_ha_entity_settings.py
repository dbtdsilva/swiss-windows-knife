from tests.conftest import _FakeUserSettings  # noqa: F401  -- imported for monkeypatch


def test_publish_flag_uses_default_when_unset(fake_user_settings):
    from swiss_windows_knife.plugins.home_assistant_mqtt_pub.entity_settings import EntitySettings
    s = EntitySettings(fake_user_settings)
    assert s.is_publish_enabled("cpu_usage", default=True) is True
    assert s.is_publish_enabled("foreground_window", default=False) is False


def test_publish_flag_returns_stored_value(fake_user_settings):
    from swiss_windows_knife.plugins.home_assistant_mqtt_pub.entity_settings import EntitySettings
    fake_user_settings.set("homeassistant_publish_cpu_usage", False)
    s = EntitySettings(fake_user_settings)
    assert s.is_publish_enabled("cpu_usage", default=True) is False


def test_interval_uses_default_when_unset(fake_user_settings):
    from swiss_windows_knife.plugins.home_assistant_mqtt_pub.entity_settings import EntitySettings
    s = EntitySettings(fake_user_settings)
    assert s.interval_s("cpu_usage", default=30) == 30


def test_interval_coerces_strings_from_qsettings(fake_user_settings):
    """QSettings round-trips ints as strings on Windows registry."""
    from swiss_windows_knife.plugins.home_assistant_mqtt_pub.entity_settings import EntitySettings
    fake_user_settings.set("homeassistant_interval_cpu_usage", "60")
    s = EntitySettings(fake_user_settings)
    assert s.interval_s("cpu_usage", default=30) == 60


def test_set_publish_writes_under_namespaced_key(fake_user_settings):
    from swiss_windows_knife.plugins.home_assistant_mqtt_pub.entity_settings import EntitySettings
    s = EntitySettings(fake_user_settings)
    s.set_publish_enabled("cpu_usage", True)
    assert fake_user_settings.get("homeassistant_publish_cpu_usage", bool, False) is True


def test_command_enabled_default(fake_user_settings):
    from swiss_windows_knife.plugins.home_assistant_mqtt_pub.entity_settings import EntitySettings
    s = EntitySettings(fake_user_settings)
    assert s.is_command_enabled("lock", default=True) is True


def test_previous_device_name_round_trip(fake_user_settings):
    from swiss_windows_knife.plugins.home_assistant_mqtt_pub.entity_settings import EntitySettings
    s = EntitySettings(fake_user_settings)
    assert s.previous_device_name() is None
    s.set_previous_device_name("Old PC")
    assert s.previous_device_name() == "Old PC"
    s.clear_previous_device_name()
    assert s.previous_device_name() is None
