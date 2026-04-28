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


def test_apply_persists_valid_input_and_recalculates(panel, fake_user_settings):
    p, sun = panel
    p.latitude_field.setText("48.8")
    p.longitude_field.setText("2.35")
    p.timezone_field.setText("Europe/Paris")

    assert p.apply() is True
    assert fake_user_settings.get('sun_latitude') == 48.8
    assert fake_user_settings.get('sun_longitude') == 2.35
    assert fake_user_settings.get('sun_timezone') == "Europe/Paris"
    assert sun.recalc_count == 1


def test_apply_rejects_non_numeric_lat_lon(panel, fake_user_settings):
    p, sun = panel
    p.latitude_field.setText("not-a-number")
    p.longitude_field.setText("0")
    p.timezone_field.setText("UTC")

    assert p.apply() is False
    assert sun.recalc_count == 0
    assert fake_user_settings.get('sun_latitude') is None


@pytest.mark.parametrize("lat,lon", [
    ("100", "0"),     # latitude too high
    ("-91", "0"),     # latitude too low
    ("0", "181"),     # longitude too high
    ("0", "-200"),    # longitude too low
])
def test_apply_rejects_out_of_range(panel, fake_user_settings, lat, lon):
    p, sun = panel
    p.latitude_field.setText(lat)
    p.longitude_field.setText(lon)
    p.timezone_field.setText("UTC")

    assert p.apply() is False
    assert sun.recalc_count == 0
    assert fake_user_settings.get('sun_latitude') is None


def test_apply_rejects_unknown_timezone(panel, fake_user_settings):
    p, sun = panel
    p.latitude_field.setText("0")
    p.longitude_field.setText("0")
    p.timezone_field.setText("Europe/NotARealCity")

    assert p.apply() is False
    assert sun.recalc_count == 0
    assert fake_user_settings.get('sun_timezone') is None


def test_init_seeds_defaults_when_settings_empty(panel):
    p, _ = panel
    # Defaults pulled from sun_strength_notifier
    assert p.latitude_field.text() == "46.52141"
    assert p.longitude_field.text() == "6.632273"
    assert p.timezone_field.text() == "Europe/Zurich"
