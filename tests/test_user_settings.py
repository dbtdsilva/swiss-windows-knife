"""Coercion tests for UserSettings' generic typed get/set.

QSettings on Windows round-trips most values as strings — booleans become
'true' / 'false', ints become '60', floats become '60.5', and absent keys
return None. These tests exercise the registry against both raw Python
types (used by tests via the dict-backed fake) and the string forms a real
Windows QSettings would hand back.
"""

import pytest
from monitorcontrol import InputSource

from swiss_windows_knife.base.user_settings import (
    _coerce,
    _coerce_bool,
    _coerce_enum,
    _coerce_float,
    _coerce_int,
    _serialize,
)


class TestCoerceBool:

    def test_native_bool_passes_through(self):
        assert _coerce_bool(True) is True
        assert _coerce_bool(False) is False

    @pytest.mark.parametrize('s', ['true', 'TRUE', 'True', '1', 'yes', '  true  '])
    def test_recognised_true_strings(self, s):
        assert _coerce_bool(s) is True

    @pytest.mark.parametrize('s', ['false', 'FALSE', 'False', '0', 'no', '  false  '])
    def test_recognised_false_strings(self, s):
        assert _coerce_bool(s) is False

    def test_none_is_none(self):
        assert _coerce_bool(None) is None

    def test_unrecognised_string_is_none(self):
        assert _coerce_bool('garbage') is None
        assert _coerce_bool('') is None


class TestCoerceInt:

    def test_none_stays_none(self):
        assert _coerce_int(None) is None

    def test_empty_string_is_none(self):
        assert _coerce_int('') is None
        assert _coerce_int('   ') is None

    def test_native_int_passes_through(self):
        assert _coerce_int(60) == 60
        assert _coerce_int(-5) == -5
        assert _coerce_int(0) == 0

    def test_string_int_is_parsed(self):
        assert _coerce_int('60') == 60
        assert _coerce_int(' 0 ') == 0

    def test_string_float_is_truncated(self):
        assert _coerce_int('60.7') == 60
        assert _coerce_int('-3.5') == -3

    def test_native_float_is_truncated(self):
        assert _coerce_int(60.7) == 60

    def test_native_bool_becomes_int(self):
        assert _coerce_int(True) == 1
        assert _coerce_int(False) == 0

    def test_garbage_string_is_none(self):
        assert _coerce_int('garbage') is None
        assert _coerce_int('1e1000a') is None


class TestCoerceFloat:

    def test_none_stays_none(self):
        assert _coerce_float(None) is None

    def test_empty_string_is_none(self):
        assert _coerce_float('') is None
        assert _coerce_float('   ') is None

    def test_string_float_is_parsed(self):
        assert _coerce_float('60.5') == 60.5
        assert _coerce_float('-3.25') == -3.25

    def test_string_int_becomes_float(self):
        assert _coerce_float('60') == 60.0

    def test_native_int_becomes_float(self):
        assert _coerce_float(60) == 60.0

    def test_native_float_passes_through(self):
        assert _coerce_float(3.14) == 3.14

    def test_garbage_string_is_none(self):
        assert _coerce_float('garbage') is None


class TestCoerceEnum:

    def test_member_passes_through(self):
        assert _coerce_enum(InputSource, InputSource.DP1) is InputSource.DP1

    def test_member_name_resolves(self):
        assert _coerce_enum(InputSource, "DP1") is InputSource.DP1
        assert _coerce_enum(InputSource, "HDMI1") is InputSource.HDMI1

    def test_legacy_qualified_form_strips_class_prefix(self):
        # Pre-refactor the registry persisted enums via str(), giving
        # 'InputSource.DP1'. Old registry entries must still resolve.
        assert _coerce_enum(InputSource, "InputSource.DP1") is InputSource.DP1

    def test_unknown_member_is_none(self):
        assert _coerce_enum(InputSource, "DOES_NOT_EXIST") is None

    def test_none_and_empty_are_none(self):
        assert _coerce_enum(InputSource, None) is None
        assert _coerce_enum(InputSource, "") is None
        assert _coerce_enum(InputSource, "   ") is None


class TestSerialize:

    def test_enum_serialises_to_member_name(self):
        assert _serialize(InputSource.DP1) == "DP1"

    def test_primitives_pass_through(self):
        assert _serialize(42) == 42
        assert _serialize(3.14) == 3.14
        assert _serialize("hello") == "hello"
        assert _serialize(True) is True
        assert _serialize(None) is None


class TestCoerceDispatch:

    def test_unregistered_type_raises(self):
        with pytest.raises(TypeError, match="no coercer registered"):
            _coerce(list, "anything")


class TestUserSettingsFakeAccessors:
    """The dict-backed fake mirrors the production API exactly — same
    serializer on write, same coercer registry on read."""

    def test_bool_round_trips(self, fake_user_settings):
        fake_user_settings.set('flag', True)
        assert fake_user_settings.get('flag', bool, False) is True
        fake_user_settings.set('flag', 'false')
        assert fake_user_settings.get('flag', bool, True) is False

    def test_bool_default_for_missing(self, fake_user_settings):
        assert fake_user_settings.get('absent', bool, True) is True

    def test_int_handles_string_form(self, fake_user_settings):
        fake_user_settings.set('volume', '60')
        assert fake_user_settings.get('volume', int, 0) == 60

    def test_int_default_for_missing(self, fake_user_settings):
        assert fake_user_settings.get('absent', int, 42) == 42

    def test_int_none_for_missing_no_default(self, fake_user_settings):
        assert fake_user_settings.get('absent', int) is None

    def test_int_none_for_empty_string(self, fake_user_settings):
        fake_user_settings.set('x', '')
        assert fake_user_settings.get('x', int) is None

    def test_float_handles_string_form(self, fake_user_settings):
        fake_user_settings.set('temp', '36.6')
        assert fake_user_settings.get('temp', float, 0.0) == 36.6

    def test_str_default_for_missing(self, fake_user_settings):
        assert fake_user_settings.get('absent', str, 'INFO') == 'INFO'

    def test_str_does_not_stringify_none(self, fake_user_settings):
        # str(None) yields 'None' — the bug the registry exists to prevent.
        assert fake_user_settings.get('absent', str, 'INFO') != 'None'

    def test_str_none_for_empty(self, fake_user_settings):
        fake_user_settings.set('x', '')
        assert fake_user_settings.get('x', str) is None

    def test_str_round_trips(self, fake_user_settings):
        fake_user_settings.set('x', 'hello')
        assert fake_user_settings.get('x', str) == 'hello'

    def test_enum_round_trips(self, fake_user_settings):
        fake_user_settings.set('input', InputSource.DP1)
        assert fake_user_settings.get('input', InputSource) is InputSource.DP1
