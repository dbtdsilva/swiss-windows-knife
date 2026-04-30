import pytest

from swiss_windows_knife.base.health import HealthReport, HealthState


def test_health_state_has_four_values():
    assert {s.value for s in HealthState} == {"ok", "warning", "error", "disabled"}


def test_health_report_holds_state_and_message():
    r = HealthReport(HealthState.OK, "Connected")
    assert r.state is HealthState.OK
    assert r.message == "Connected"


def test_health_report_is_frozen():
    r = HealthReport(HealthState.OK, "Connected")
    with pytest.raises((AttributeError, Exception)):
        r.message = "Other"
