from swiss_windows_knife.plugins.display_image_tuner.location_picker import coordinates_to_timezone


def test_coordinates_to_timezone_resolves_known_city():
    # Lausanne, Switzerland.
    assert coordinates_to_timezone(46.521410, 6.632273) == "Europe/Zurich"


def test_coordinates_to_timezone_resolves_paris():
    assert coordinates_to_timezone(48.8566, 2.3522) == "Europe/Paris"


def test_coordinates_to_timezone_returns_string_for_ocean_point():
    # timezonefinder covers the globe including Etc/GMT bands over open
    # ocean — we only need a non-empty result, exact value is implementation
    # detail.
    result = coordinates_to_timezone(-40.0, -30.0)
    assert result is not None
    assert result.startswith("Etc/")
