"""Pure-function math for the auto-mode display tuner.

`compute_target` maps a 0-100 sun strength to a 0-100 monitor value via a
gamma curve clamped to a configurable [min_value, max_value] range. No Qt,
no I/O — safe to unit-test in isolation.
"""
from __future__ import annotations


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
