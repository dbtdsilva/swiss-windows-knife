import pytest

from src.plugins.display_image_tuner.curve import gamma_from_slider, slider_from_gamma


def test_slider_zero_gives_one_third():
    assert gamma_from_slider(0) == pytest.approx(1 / 3, rel=1e-6)


def test_slider_fifty_gives_one():
    assert gamma_from_slider(50) == pytest.approx(1.0, rel=1e-6)


def test_slider_hundred_gives_three():
    assert gamma_from_slider(100) == pytest.approx(3.0, rel=1e-6)


def test_slider_clamps_below_zero():
    assert gamma_from_slider(-20) == pytest.approx(1 / 3, rel=1e-6)


def test_slider_clamps_above_hundred():
    assert gamma_from_slider(150) == pytest.approx(3.0, rel=1e-6)


@pytest.mark.parametrize("gamma", [1 / 3, 0.5, 0.8, 1.0, 1.5, 2.0, 3.0])
def test_slider_round_trip(gamma):
    assert gamma_from_slider(slider_from_gamma(gamma)) == pytest.approx(gamma, rel=1.5e-2)


def test_slider_from_gamma_clamps_below_one_third():
    assert slider_from_gamma(0.1) == 0


def test_slider_from_gamma_clamps_above_three():
    assert slider_from_gamma(10.0) == 100
