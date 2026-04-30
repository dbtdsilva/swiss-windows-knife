import pytest

from swiss_windows_knife.plugins.display_image_tuner.curve import compute_keyframe_value


def call(when, **kwargs):
    defaults = dict(
        sunrise_hours=6.0,
        sunset_hours=18.0,
        night_level=20,
        day_level=80,
        sunrise_offset_minutes=0,
        sunset_offset_minutes=0,
        ramp_duration_minutes=60,
        ramp_smoothness=0.0,
    )
    defaults.update(kwargs)
    return compute_keyframe_value(when, **defaults)


def test_constant_at_night():
    assert call(0.0) == pytest.approx(20.0)
    assert call(3.0) == pytest.approx(20.0)
    assert call(23.0) == pytest.approx(20.0)


def test_constant_at_day():
    assert call(7.0) == pytest.approx(80.0)
    assert call(12.0) == pytest.approx(80.0)
    assert call(17.0) == pytest.approx(80.0)


def test_morning_ramp_linear_midpoint():
    assert call(5.5) == pytest.approx(50.0)


def test_evening_ramp_linear_midpoint():
    assert call(18.5) == pytest.approx(50.0)


def test_morning_ramp_endpoints():
    assert call(5.0) == pytest.approx(20.0)
    assert call(6.0) == pytest.approx(80.0)


def test_evening_ramp_endpoints():
    assert call(18.0) == pytest.approx(80.0)
    assert call(19.0) == pytest.approx(20.0)


def test_positive_sunrise_offset_anticipates_dawn():
    # +30 min: morning ramp ends 30 min before sunrise (at 5.5h),
    # so by sunrise we are well into the day plateau.
    assert call(6.0, sunrise_offset_minutes=30) == pytest.approx(80.0)
    assert call(5.5, sunrise_offset_minutes=30) == pytest.approx(80.0)


def test_negative_sunrise_offset_delays_dawn():
    # -30 min: morning ramp ends 30 min AFTER sunrise (at 6.5h).
    # At 6.0 we're mid-ramp.
    assert call(6.0, sunrise_offset_minutes=-30) == pytest.approx(50.0)


def test_positive_sunset_offset_delays_nightfall():
    # +30 min: evening ramp starts 30 min AFTER sunset (at 18.5).
    # At 18.0 (sunset) we are still at day_level.
    assert call(18.0, sunset_offset_minutes=30) == pytest.approx(80.0)
    # Mid-ramp at 19.0.
    assert call(19.0, sunset_offset_minutes=30) == pytest.approx(50.0)


def test_negative_sunset_offset_advances_dusk():
    # -30 min: evening ramp starts 30 min BEFORE sunset (at 17.5).
    # By sunset we are mid-ramp.
    assert call(18.0, sunset_offset_minutes=-30) == pytest.approx(50.0)


def test_offsets_independent_per_side():
    # Asymmetric: anticipate dawn but normal dusk.
    assert call(6.0, sunrise_offset_minutes=60, sunset_offset_minutes=0) == pytest.approx(80.0)
    assert call(18.5, sunrise_offset_minutes=60, sunset_offset_minutes=0) == pytest.approx(50.0)


def test_extended_duration_widens_transition():
    assert call(4.0, ramp_duration_minutes=120) == pytest.approx(20.0)
    assert call(5.0, ramp_duration_minutes=120) == pytest.approx(50.0)
    assert call(6.0, ramp_duration_minutes=120) == pytest.approx(80.0)


def test_smoothness_positive_is_ease_in():
    linear_mid = call(5.5)
    eased_mid = call(5.5, ramp_smoothness=1.0)
    assert eased_mid < linear_mid


def test_smoothness_negative_is_ease_out():
    linear_mid = call(5.5)
    eased_mid = call(5.5, ramp_smoothness=-1.0)
    assert eased_mid > linear_mid


def test_evening_smoothness_mirrors_morning():
    linear_mid = call(18.5)
    eased_mid = call(18.5, ramp_smoothness=1.0)
    assert eased_mid > linear_mid


def test_missing_sun_events_falls_back_to_night_level():
    assert call(12.0, sunrise_hours=None, sunset_hours=None) == pytest.approx(20.0)
