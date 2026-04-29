"""Pure-function math for the auto-mode display tuner.

`compute_target` maps a 0-100 sun strength to a 0-100 monitor value via a
gamma curve clamped to a configurable [min_value, max_value] range. No Qt,
no I/O — safe to unit-test in isolation.
"""
from __future__ import annotations

import math


def compute_target(
    sun: float,
    *,
    min_value: int,
    max_value: int,
    gamma: float,
) -> float:
    s = max(0.0, min(100.0, float(sun))) / 100.0
    shaped = s ** gamma
    return float(min_value) + (float(max_value) - float(min_value)) * shaped


def ease(
    actual: float,
    target: float,
    *,
    dt: float,
    smoothing_seconds: float,
) -> float:
    if smoothing_seconds <= 0.0:
        return float(target)
    fraction = dt / smoothing_seconds
    if fraction >= 1.0:
        return float(target)
    return float(actual) + (float(target) - float(actual)) * fraction


GAMMA_MIN = 1 / 3
GAMMA_MAX = 3.0
_LN3 = math.log(3.0)


def gamma_from_slider(slider_pos: int) -> float:
    pos = max(0, min(100, int(slider_pos)))
    # Symmetric in log space: pos=0 -> 1/3, pos=50 -> 1, pos=100 -> 3
    return math.exp(((pos - 50) / 50.0) * _LN3)


def slider_from_gamma(gamma: float) -> int:
    g = max(GAMMA_MIN, min(GAMMA_MAX, float(gamma)))
    pos = round(50.0 + (math.log(g) / _LN3) * 50.0)
    return max(0, min(100, int(pos)))
