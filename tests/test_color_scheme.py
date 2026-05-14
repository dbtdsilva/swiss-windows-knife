from PySide6.QtCore import Qt

from swiss_windows_knife.base import color_scheme
from swiss_windows_knife.base.color_scheme import (
    SETTINGS_KEY,
    ColorSchemePreference,
    apply_preference,
    load_preference,
    save_preference,
)


def test_default_preference_is_follow_system(fake_user_settings):
    assert load_preference() is ColorSchemePreference.SYSTEM


def test_save_and_load_roundtrip(fake_user_settings):
    save_preference(ColorSchemePreference.DARK)
    assert load_preference() is ColorSchemePreference.DARK


def test_unrecognised_stored_value_falls_back_to_system(fake_user_settings):
    fake_user_settings.set(SETTINGS_KEY, "GARBAGE")
    assert load_preference() is ColorSchemePreference.SYSTEM


def test_apply_preference_sets_qt_color_scheme(qtbot, monkeypatch):
    seen: list = []

    class _FakeHints:
        def setColorScheme(self, scheme):
            seen.append(scheme)

    monkeypatch.setattr(
        "swiss_windows_knife.base.color_scheme.QGuiApplication.styleHints",
        staticmethod(lambda: _FakeHints()),
    )

    apply_preference(ColorSchemePreference.LIGHT)
    apply_preference(ColorSchemePreference.DARK)
    apply_preference(ColorSchemePreference.SYSTEM)

    assert seen == [
        Qt.ColorScheme.Light,
        Qt.ColorScheme.Dark,
        Qt.ColorScheme.Unknown,
    ]


def test_apply_preference_tolerates_missing_style_hints(monkeypatch):
    monkeypatch.setattr(
        "swiss_windows_knife.base.color_scheme.QGuiApplication.styleHints",
        staticmethod(lambda: None),
    )
    # Must not raise.
    color_scheme.apply_preference(ColorSchemePreference.DARK)
