"""Coercion tests for UserSettings typed accessors.

QSettings on Windows round-trips most values as strings — booleans become
'true' / 'false', ints become '60', floats become '60.5', and absent keys
return None. These tests exercise the typed accessors against both raw
Python types (used by tests via the dict-backed fake) and the string
forms a real Windows QSettings would hand back.
"""

import pytest

from src.base.user_settings import (
    _coerce_bool,
    _coerce_optional_float,
    _coerce_optional_int,
)


class TestCoerceBool:

    def test_native_bool_passes_through(self):
        assert _coerce_bool(True, default=False) is True
        assert _coerce_bool(False, default=True) is False

    @pytest.mark.parametrize('s', ['true', 'TRUE', 'True', '1', 'yes', '  true  '])
    def test_recognised_true_strings(self, s):
        assert _coerce_bool(s, default=False) is True

    @pytest.mark.parametrize('s', ['false', 'FALSE', 'False', '0', 'no', '  false  '])
    def test_recognised_false_strings(self, s):
        assert _coerce_bool(s, default=True) is False

    def test_none_falls_back_to_default(self):
        assert _coerce_bool(None, default=True) is True
        assert _coerce_bool(None, default=False) is False

    def test_unrecognised_string_falls_back_to_truthiness(self):
        assert _coerce_bool('garbage', default=False) is True
        assert _coerce_bool('', default=True) is False


class TestCoerceOptionalInt:

    def test_none_stays_none(self):
        assert _coerce_optional_int(None) is None

    def test_empty_string_is_none(self):
        assert _coerce_optional_int('') is None
        assert _coerce_optional_int('   ') is None

    def test_native_int_passes_through(self):
        assert _coerce_optional_int(60) == 60
        assert _coerce_optional_int(-5) == -5
        assert _coerce_optional_int(0) == 0

    def test_string_int_is_parsed(self):
        assert _coerce_optional_int('60') == 60
        assert _coerce_optional_int(' 0 ') == 0

    def test_string_float_is_truncated(self):
        assert _coerce_optional_int('60.7') == 60
        assert _coerce_optional_int('-3.5') == -3

    def test_native_float_is_truncated(self):
        assert _coerce_optional_int(60.7) == 60

    def test_native_bool_becomes_int(self):
        assert _coerce_optional_int(True) == 1
        assert _coerce_optional_int(False) == 0

    def test_garbage_string_is_none(self):
        assert _coerce_optional_int('garbage') is None
        assert _coerce_optional_int('1e1000a') is None


class TestCoerceOptionalFloat:

    def test_none_stays_none(self):
        assert _coerce_optional_float(None) is None

    def test_empty_string_is_none(self):
        assert _coerce_optional_float('') is None
        assert _coerce_optional_float('   ') is None

    def test_string_float_is_parsed(self):
        assert _coerce_optional_float('60.5') == 60.5
        assert _coerce_optional_float('-3.25') == -3.25

    def test_string_int_becomes_float(self):
        assert _coerce_optional_float('60') == 60.0

    def test_native_int_becomes_float(self):
        assert _coerce_optional_float(60) == 60.0

    def test_native_float_passes_through(self):
        assert _coerce_optional_float(3.14) == 3.14

    def test_garbage_string_is_none(self):
        assert _coerce_optional_float('garbage') is None


class TestUserSettingsFakeAccessors:
    """The dict-backed fake exposed by `fake_user_settings` must implement
    the same typed accessors as the real `UserSettings`."""

    def test_get_bool_handles_string_form(self, fake_user_settings):
        fake_user_settings.set('flag', 'true')
        assert fake_user_settings.get_bool('flag', default=False) is True
        fake_user_settings.set('flag', 'false')
        assert fake_user_settings.get_bool('flag', default=True) is False

    def test_get_bool_returns_default_for_missing(self, fake_user_settings):
        assert fake_user_settings.get_bool('absent', default=True) is True

    def test_get_int_handles_string_form(self, fake_user_settings):
        fake_user_settings.set('volume', '60')
        assert fake_user_settings.get_int('volume', default=0) == 60

    def test_get_int_returns_default_for_missing(self, fake_user_settings):
        assert fake_user_settings.get_int('absent', default=42) == 42

    def test_get_optional_int_returns_none_for_missing(self, fake_user_settings):
        assert fake_user_settings.get_optional_int('absent') is None

    def test_get_optional_int_returns_none_for_empty_string(self, fake_user_settings):
        fake_user_settings.set('x', '')
        assert fake_user_settings.get_optional_int('x') is None

    def test_get_float_handles_string_form(self, fake_user_settings):
        fake_user_settings.set('temp', '36.6')
        assert fake_user_settings.get_float('temp', default=0.0) == 36.6

    def test_get_str_returns_default_for_missing(self, fake_user_settings):
        assert fake_user_settings.get_str('absent', default='INFO') == 'INFO'

    def test_get_str_does_not_stringify_none(self, fake_user_settings):
        """str(None) yields 'None' — the bug this whole accessor surface
        exists to prevent. The default must be returned instead."""
        assert fake_user_settings.get_str('absent', default='INFO') != 'None'

    def test_get_optional_str_returns_none_for_missing(self, fake_user_settings):
        assert fake_user_settings.get_optional_str('absent') is None

    def test_get_optional_str_returns_none_for_empty_string(self, fake_user_settings):
        fake_user_settings.set('x', '')
        assert fake_user_settings.get_optional_str('x') is None

    def test_get_optional_str_returns_text_for_set_value(self, fake_user_settings):
        fake_user_settings.set('x', 'hello')
        assert fake_user_settings.get_optional_str('x') == 'hello'
