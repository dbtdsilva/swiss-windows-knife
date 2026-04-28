import pytest

from src.components.update_checker import _parse_version


@pytest.mark.parametrize("text,expected", [
    ("1.10.0", (1, 10, 0)),
    ("1.9.8", (1, 9, 8)),
    ("v1.10.0", (1, 10, 0)),
    ("2.0.0", (2, 0, 0)),
    ("0.0.1", (0, 0, 1)),
])
def test_parse_version_basic(text, expected):
    assert _parse_version(text) == expected


def test_parse_version_lexicographic_regression():
    """1.10.0 must be greater than 1.9.8.

    Previous string compare gave the wrong answer, silencing updates.
    """
    assert _parse_version("1.10.0") > _parse_version("1.9.8")
    assert _parse_version("1.10.1") > _parse_version("1.9.99")
    assert _parse_version("2.0.0") > _parse_version("1.99.99")


def test_parse_version_stops_at_non_numeric_segment():
    """Pre-release suffixes (rc1, a1, etc.) are not part of the integer tuple,
    so a release with such a suffix compares as the prefix of the final."""
    assert _parse_version("1.10.0-rc1") == (1, 10)
    assert _parse_version("1.10.0a1") == (1, 10)
    # And the final release sorts above any pre-release with the same prefix
    assert _parse_version("1.10.0") > _parse_version("1.10.0-rc1")


def test_parse_version_empty_or_garbage():
    assert _parse_version("") == ()
    assert _parse_version("not-a-version") == ()
