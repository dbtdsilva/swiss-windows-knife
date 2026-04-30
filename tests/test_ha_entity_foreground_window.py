from unittest.mock import patch

from swiss_windows_knife.plugins.home_assistant_mqtt_pub.entities.foreground_window import ForegroundWindowEntity


def test_default_enabled_false():
    assert ForegroundWindowEntity().default_enabled is False


def test_sample_returns_window_title():
    e = ForegroundWindowEntity()
    with patch("win32gui.GetForegroundWindow", return_value=1234), \
         patch("win32gui.GetWindowText", return_value="Notepad — untitled"):
        r = e.sample()
    assert r.is_available is True
    assert r.value == "Notepad — untitled"


def test_sample_unavailable_when_title_empty():
    e = ForegroundWindowEntity()
    with patch("win32gui.GetForegroundWindow", return_value=1234), \
         patch("win32gui.GetWindowText", return_value=""):
        r = e.sample()
    assert r.is_available is False
