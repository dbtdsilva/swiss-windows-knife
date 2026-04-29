from datetime import datetime

import pytz

from src.plugins.display_image_tuner.sun_strength_notifier import compute_sun_strength


def test_compute_sun_strength_zero_at_midnight_local():
    # Midnight in Lausanne -> sun is below horizon -> strength is 0
    when = pytz.timezone("Europe/Zurich").localize(datetime(2026, 6, 21, 0, 0, 0))
    val = compute_sun_strength(when, latitude=46.521410, longitude=6.632273)
    assert val == 0


def test_compute_sun_strength_positive_at_solar_noon_summer():
    when = pytz.timezone("Europe/Zurich").localize(datetime(2026, 6, 21, 12, 30, 0))
    val = compute_sun_strength(when, latitude=46.521410, longitude=6.632273)
    assert val > 0
    assert val <= 100


def test_compute_sun_strength_capped_at_one_hundred():
    # Equator at solar noon on equinox should still be capped at 100
    when = pytz.timezone("UTC").localize(datetime(2026, 3, 20, 12, 0, 0))
    val = compute_sun_strength(when, latitude=0.0, longitude=0.0)
    assert val == 100


def test_compute_sun_strength_lower_in_winter_than_summer_at_same_hour():
    tz = pytz.timezone("Europe/Zurich")
    summer = compute_sun_strength(
        tz.localize(datetime(2026, 6, 21, 7, 0)),
        latitude=46.521410, longitude=6.632273,
    )
    winter = compute_sun_strength(
        tz.localize(datetime(2026, 12, 21, 7, 0)),
        latitude=46.521410, longitude=6.632273,
    )
    assert winter < summer
