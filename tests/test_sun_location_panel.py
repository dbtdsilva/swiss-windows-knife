from unittest.mock import patch

import pytest


class _FakeSunStrength:
    def __init__(self) -> None:
        self.recalc_count = 0

    def calculate_sun_strength(self) -> None:
        self.recalc_count += 1


@pytest.fixture
def panel(qtbot, fake_user_settings, silent_messagebox):
    from src.plugins.display_image_tuner.sun_location_panel import SunLocationConfigPanel
    sun = _FakeSunStrength()
    p = SunLocationConfigPanel(sun)
    qtbot.addWidget(p)
    return p, sun


def test_apply_persists_picked_coordinates_and_timezone(panel, fake_user_settings):
    p, sun = panel
    p.picker._on_coordinates_picked(48.8566, 2.3522)  # Paris

    assert p.apply() is True
    assert fake_user_settings.get('sun_latitude') == pytest.approx(48.8566)
    assert fake_user_settings.get('sun_longitude') == pytest.approx(2.3522)
    assert fake_user_settings.get('sun_timezone') == "Europe/Paris"
    assert sun.recalc_count == 1


def test_apply_rejects_when_timezone_cannot_be_resolved(panel, fake_user_settings):
    p, sun = panel
    # Mid-ocean point with no timezone polygon.
    with patch(
        'src.plugins.display_image_tuner.location_picker.coordinates_to_timezone',
        return_value=None,
    ):
        p.picker._on_coordinates_picked(0.0, -30.0)

    assert p.apply() is False
    assert sun.recalc_count == 0
    assert fake_user_settings.get('sun_timezone') is None


def test_init_seeds_defaults_when_settings_empty(panel):
    p, _ = panel
    assert p.picker.latitude() == pytest.approx(46.52141)
    assert p.picker.longitude() == pytest.approx(6.632273)
    assert p.picker.timezone() == "Europe/Zurich"
