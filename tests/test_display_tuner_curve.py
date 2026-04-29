import pytest

from src.plugins.display_image_tuner.curve import compute_target


@pytest.mark.parametrize("sun, expected", [
    (0, 0.0),
    (50, 50.0),
    (100, 100.0),
])
def test_compute_target_linear_full_range(sun, expected):
    assert compute_target(sun, min_value=0, max_value=100, gamma=1.0) == pytest.approx(expected)


@pytest.mark.parametrize("sun, expected", [
    (0, 20.0),
    (50, 50.0),
    (100, 80.0),
])
def test_compute_target_linear_clamped(sun, expected):
    assert compute_target(sun, min_value=20, max_value=80, gamma=1.0) == pytest.approx(expected)


def test_compute_target_boosted_gamma_above_linear():
    linear = compute_target(50, min_value=0, max_value=100, gamma=1.0)
    boosted = compute_target(50, min_value=0, max_value=100, gamma=0.5)
    assert boosted > linear


def test_compute_target_lazy_gamma_below_linear():
    linear = compute_target(50, min_value=0, max_value=100, gamma=1.0)
    lazy = compute_target(50, min_value=0, max_value=100, gamma=2.0)
    assert lazy < linear


def test_compute_target_clamps_at_min_when_sun_zero():
    assert compute_target(0, min_value=20, max_value=80, gamma=2.0) == pytest.approx(20.0)


def test_compute_target_clamps_at_max_when_sun_full():
    assert compute_target(100, min_value=20, max_value=80, gamma=0.5) == pytest.approx(80.0)


def test_compute_target_below_zero_sun_clamps_to_min():
    assert compute_target(-10, min_value=20, max_value=80, gamma=1.0) == pytest.approx(20.0)


def test_compute_target_above_hundred_sun_clamps_to_max():
    assert compute_target(150, min_value=20, max_value=80, gamma=1.0) == pytest.approx(80.0)


def test_compute_target_min_equals_max_returns_constant():
    assert compute_target(0, min_value=50, max_value=50, gamma=1.0) == pytest.approx(50.0)
    assert compute_target(73, min_value=50, max_value=50, gamma=2.5) == pytest.approx(50.0)
