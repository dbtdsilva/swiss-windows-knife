import pytest


class _FakeSunStrength:
    def __init__(self) -> None:
        self.recalc_count = 0

    def calculate_sun_strength(self) -> None:
        self.recalc_count += 1


@pytest.fixture
def panel(qtbot, fake_user_settings, silent_messagebox):
    from swiss_windows_knife.plugins.display_image_tuner.display_tuning_panel import (
        DisplayTuningConfigPanel,
    )
    sun = _FakeSunStrength()
    p = DisplayTuningConfigPanel(sun)
    qtbot.addWidget(p)
    return p, sun


def test_summary_shows_default_when_settings_empty(panel):
    p, _ = panel
    assert "default" in p._location_summary.text().lower()
    assert "Europe/Zurich" in p._location_summary.text()


def test_summary_shows_saved_location(qtbot, fake_user_settings, silent_messagebox):
    fake_user_settings.set('sun_latitude', 48.8566)
    fake_user_settings.set('sun_longitude', 2.3522)
    fake_user_settings.set('sun_timezone', 'Europe/Paris')
    from swiss_windows_knife.plugins.display_image_tuner.display_tuning_panel import (
        DisplayTuningConfigPanel,
    )
    p = DisplayTuningConfigPanel(_FakeSunStrength())
    qtbot.addWidget(p)
    text = p._location_summary.text()
    assert "48.8566" in text
    assert "2.3522" in text
    assert "Europe/Paris" in text
    assert "default" not in text.lower()


def test_apply_persists_pending_location_and_recalcs(panel, fake_user_settings):
    p, sun = panel
    p._pending_lat = 48.8566
    p._pending_lng = 2.3522
    p._pending_tz = 'Europe/Paris'

    assert p.apply() is True
    assert fake_user_settings.get('sun_latitude', float) == pytest.approx(48.8566)
    assert fake_user_settings.get('sun_longitude', float) == pytest.approx(2.3522)
    assert fake_user_settings.get('sun_timezone', str) == 'Europe/Paris'
    assert sun.recalc_count == 1


def test_apply_skips_recalc_when_location_unchanged(panel, fake_user_settings):
    p, sun = panel
    p.apply()
    sun.recalc_count = 0

    assert p.apply() is True
    assert sun.recalc_count == 0


def test_apply_rejects_when_timezone_missing(panel, fake_user_settings):
    p, sun = panel
    p._pending_tz = ''

    assert p.apply() is False
    assert sun.recalc_count == 0
    assert fake_user_settings.get('sun_latitude', float) is None


def test_apply_rejects_when_timezone_unknown(panel, fake_user_settings):
    p, sun = panel
    p._pending_tz = 'Not/A_Real_Zone'

    assert p.apply() is False
    assert sun.recalc_count == 0
    assert fake_user_settings.get('sun_timezone', str) is None
