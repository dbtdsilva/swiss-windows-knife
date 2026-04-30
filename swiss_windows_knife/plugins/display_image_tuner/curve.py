"""Pure-function math for the auto-mode display tuner.

`compute_keyframe_value` maps a time-of-day to a 0-100 monitor value using
a keyframe model: night level outside the bright window, day level inside,
and an eased ramp on each side anchored relative to sunrise/sunset.
"""
from __future__ import annotations


def compute_keyframe_value(
    when_hours: float,
    *,
    sunrise_hours: float | None,
    sunset_hours: float | None,
    night_level: float,
    day_level: float,
    sunrise_offset_minutes: float,
    sunset_offset_minutes: float,
    ramp_duration_minutes: float,
    ramp_smoothness: float,
) -> float:
    """Output value at `when_hours` (0..24) under the keyframe model.

    `sunrise_offset_minutes`: positive shifts the morning ramp earlier, so
        the monitor reaches `day_level` BEFORE sunrise (anticipates dawn).
        Negative shifts it later (lazy wake).
    `sunset_offset_minutes`: positive shifts the evening ramp later, so the
        monitor stays at `day_level` AFTER sunset (delays nightfall).
        Negative shifts it earlier (early dim).
    `ramp_duration_minutes`: width of each ramp.
    `ramp_smoothness`: in roughly [-1, +1]. 0 = linear; >0 = ease-in (slow
        start, fast finish); <0 = ease-out (fast start, slow finish).
        Mirror-applied to morning and evening so the same setting feels
        symmetric to the user.

    Polar edge cases: if sunrise/sunset is missing, falls back to a single
    level (day or night) appropriate to the missing event.
    """
    night = float(night_level)
    day = float(day_level)

    if sunrise_hours is None and sunset_hours is None:
        return night
    if sunrise_hours is None:
        return day
    if sunset_hours is None:
        return night

    sunrise_offset_h = sunrise_offset_minutes / 60.0
    sunset_offset_h = sunset_offset_minutes / 60.0
    duration_h = max(0.0, ramp_duration_minutes / 60.0)

    morning_end = sunrise_hours - sunrise_offset_h
    morning_start = morning_end - duration_h
    evening_start = sunset_hours + sunset_offset_h
    evening_end = evening_start + duration_h

    if when_hours <= morning_start or when_hours >= evening_end:
        return night
    if morning_end <= when_hours <= evening_start:
        return day

    eps = 1e-9
    if when_hours < morning_end:
        t = (when_hours - morning_start) / max(duration_h, eps)
        t = max(0.0, min(1.0, t))
        t_eased = t ** (2.0 ** ramp_smoothness)
        return night + (day - night) * t_eased

    t = (when_hours - evening_start) / max(duration_h, eps)
    t = max(0.0, min(1.0, t))
    t_eased = t ** (2.0 ** ramp_smoothness)
    return day + (night - day) * t_eased
