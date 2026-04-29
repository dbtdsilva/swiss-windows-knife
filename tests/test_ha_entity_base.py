from src.plugins.home_assistant_mqtt_pub.entities.base import SampleResult


def test_sample_result_available():
    r = SampleResult.available(value=42, unit="%")
    assert r.is_available is True
    assert r.value == 42
    assert r.unit == "%"


def test_sample_result_unavailable():
    r = SampleResult.unavailable(reason="no thermal zone")
    assert r.is_available is False
    assert r.value is None
    assert r.reason == "no thermal zone"


def test_sample_result_default_reason_empty_string():
    r = SampleResult.available(value=1)
    assert r.reason == ""
