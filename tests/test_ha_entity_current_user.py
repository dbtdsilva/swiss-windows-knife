from unittest.mock import patch

from swiss_windows_knife.plugins.home_assistant_mqtt_pub.entities.current_user import CurrentUserEntity


def test_default_enabled_is_false_for_privacy():
    assert CurrentUserEntity().default_enabled is False


def test_sample_returns_current_user():
    e = CurrentUserEntity()
    with patch("getpass.getuser", return_value="alice"):
        r = e.sample()
    assert r.is_available is True
    assert r.value == "alice"
