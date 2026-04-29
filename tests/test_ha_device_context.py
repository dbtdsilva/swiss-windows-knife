from src.plugins.home_assistant_mqtt_pub.device_context import DeviceContext, slugify


def test_slugify_lowercases_and_replaces_spaces():
    assert slugify("Camelot Aorus 02") == "camelot_aorus_02"


def test_slugify_strips_non_ascii_and_punctuation():
    assert slugify("Diogo's PC!") == "diogos_pc"


def test_slugify_collapses_repeated_separators():
    assert slugify("a   b---c") == "a_b_c"


def test_slugify_rejects_empty():
    import pytest
    with pytest.raises(ValueError):
        slugify("   ")


def test_device_id_uses_swk_prefix():
    ctx = DeviceContext(name="Camelot Aorus")
    assert ctx.device_id == "swk_camelot_aorus"


def test_state_topic_includes_component_and_entity():
    ctx = DeviceContext(name="pc")
    assert ctx.state_topic("sensor", "cpu_usage") == \
        "homeassistant/sensor/swk_pc/cpu_usage/state"


def test_discovery_topic_matches_state_topic_layout():
    ctx = DeviceContext(name="pc")
    assert ctx.discovery_topic("sensor", "cpu_usage") == \
        "homeassistant/sensor/swk_pc/cpu_usage/config"


def test_availability_topic_per_device():
    ctx = DeviceContext(name="pc")
    assert ctx.availability_topic == "homeassistant/swk_pc/availability"


def test_command_topic():
    ctx = DeviceContext(name="pc")
    assert ctx.command_topic("lock") == "homeassistant/button/swk_pc/lock/set"


def test_device_block_includes_app_metadata():
    ctx = DeviceContext(name="pc")
    block = ctx.device_block()
    assert block["identifiers"] == ["swk_pc"]
    assert block["name"] == "pc"
    assert "Swiss Windows Knife" in block["manufacturer"]
    assert "sw_version" in block
