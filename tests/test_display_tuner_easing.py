import pytest

from src.plugins.display_image_tuner.curve import ease


def test_ease_snaps_to_target_when_smoothing_zero():
    assert ease(actual=10.0, target=80.0, dt=1.0, smoothing_seconds=0.0) == pytest.approx(80.0)


def test_ease_snaps_to_target_when_smoothing_negative():
    assert ease(actual=10.0, target=80.0, dt=1.0, smoothing_seconds=-5.0) == pytest.approx(80.0)


def test_ease_moves_toward_target():
    out = ease(actual=0.0, target=100.0, dt=1.0, smoothing_seconds=10.0)
    assert 0.0 < out < 100.0


def test_ease_closes_proportional_fraction_of_gap_per_tick():
    # smoothing=10s, dt=1s -> exactly 1/10 of the gap closed per tick
    out = ease(actual=0.0, target=100.0, dt=1.0, smoothing_seconds=10.0)
    assert out == pytest.approx(10.0)


def test_ease_does_not_overshoot_when_target_above():
    actual = 0.0
    for _ in range(1000):
        actual = ease(actual=actual, target=50.0, dt=1.0, smoothing_seconds=5.0)
    assert actual <= 50.0
    assert actual == pytest.approx(50.0, abs=1e-3)


def test_ease_does_not_overshoot_when_target_below():
    actual = 100.0
    for _ in range(1000):
        actual = ease(actual=actual, target=50.0, dt=1.0, smoothing_seconds=5.0)
    assert actual >= 50.0
    assert actual == pytest.approx(50.0, abs=1e-3)


def test_ease_already_at_target_stays_at_target():
    assert ease(actual=42.0, target=42.0, dt=1.0, smoothing_seconds=10.0) == pytest.approx(42.0)
