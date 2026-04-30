from unittest.mock import MagicMock

import pytest

from swiss_windows_knife.plugins.home_assistant_mqtt_pub.device_context import DeviceContext
from swiss_windows_knife.plugins.home_assistant_mqtt_pub.publisher import Publisher


class _SyncSampler:
    """SamplerRunner stand-in that runs fn + on_done synchronously."""

    def submit(self, fn, on_done):
        on_done(fn())


class _StubEntity:
    component = "sensor"
    is_event_driven = False

    def __init__(self, key, value):
        self.key = key
        self.display_name = key
        self.default_enabled = True
        self.default_interval_s = 30
        self._value = value

    def discovery_payload(self, ctx):
        return {"name": self.display_name, "state_topic": ctx.state_topic(self.component, self.key)}

    def sample(self):
        from swiss_windows_knife.plugins.home_assistant_mqtt_pub.entities.base import SampleResult
        return SampleResult.available(value=self._value, unit="%")


@pytest.fixture
def settings(fake_user_settings):
    from swiss_windows_knife.plugins.home_assistant_mqtt_pub.entity_settings import EntitySettings
    return EntitySettings(fake_user_settings)


def test_on_connected_publishes_discovery_state_and_availability(qtbot, fake_user_settings, settings):
    ctx = DeviceContext(name="pc")
    session = MagicMock()
    entities = [_StubEntity("cpu_usage", 12.5)]
    pub = Publisher(
        session=session, ctx=ctx, settings=settings,
        sampler=_SyncSampler(), entities=entities, commands=[],
    )
    pub.on_connected()
    topics = [c.args[0] for c in session.publish.call_args_list]
    assert "homeassistant/sensor/swk_pc/cpu_usage/config" in topics
    assert "homeassistant/sensor/swk_pc/cpu_usage/state" in topics
    assert "homeassistant/swk_pc/availability" in topics
    avail_payload = next(c.args[1] for c in session.publish.call_args_list
                         if c.args[0] == "homeassistant/swk_pc/availability")
    assert avail_payload == "online"


def test_on_connected_skips_disabled_entities(qtbot, fake_user_settings, settings):
    ctx = DeviceContext(name="pc")
    session = MagicMock()
    settings.set_publish_enabled("cpu_usage", False)
    entities = [_StubEntity("cpu_usage", 12.5)]
    pub = Publisher(session, ctx, settings, _SyncSampler(), entities, [])
    pub.on_connected()
    topics = [c.args[0] for c in session.publish.call_args_list]
    assert "homeassistant/sensor/swk_pc/cpu_usage/config" not in topics
    assert "homeassistant/sensor/swk_pc/cpu_usage/state" not in topics


def test_publish_state_uses_value_and_retain_true(qtbot, fake_user_settings, settings):
    ctx = DeviceContext(name="pc")
    session = MagicMock()
    entities = [_StubEntity("cpu_usage", 7.5)]
    pub = Publisher(session, ctx, settings, _SyncSampler(), entities, [])
    pub.tick(entities[0])
    state_calls = [c for c in session.publish.call_args_list
                   if c.args[0] == "homeassistant/sensor/swk_pc/cpu_usage/state"]
    assert len(state_calls) == 1
    assert state_calls[0].args[1] == "7.5"
    assert state_calls[0].kwargs.get("retain") is True


def test_unavailable_sample_publishes_nothing(qtbot, fake_user_settings, settings):
    from swiss_windows_knife.plugins.home_assistant_mqtt_pub.entities.base import SampleResult

    class _Bad(_StubEntity):
        def sample(self):
            return SampleResult.unavailable("nope")

    ctx = DeviceContext(name="pc")
    session = MagicMock()
    entities = [_Bad("cpu_temperature", 0)]
    pub = Publisher(session, ctx, settings, _SyncSampler(), entities, [])
    pub.tick(entities[0])
    state_calls = [c for c in session.publish.call_args_list
                   if "/state" in c.args[0]]
    assert state_calls == []


def test_apply_handles_device_rename(qtbot, fake_user_settings, settings):
    settings.set_previous_device_name("OldPC")
    ctx = DeviceContext(name="NewPC")
    session = MagicMock()
    entities = [_StubEntity("cpu_usage", 1)]
    pub = Publisher(session, ctx, settings, _SyncSampler(), entities, [])
    pub.apply()
    topics = [c.args[0] for c in session.publish.call_args_list]
    assert "homeassistant/sensor/swk_oldpc/cpu_usage/config" in topics
    delete_payload = next(c.args[1] for c in session.publish.call_args_list
                          if c.args[0] == "homeassistant/sensor/swk_oldpc/cpu_usage/config")
    assert delete_payload == ""
    assert "homeassistant/sensor/swk_newpc/cpu_usage/config" in topics
    assert settings.previous_device_name() == "NewPC"


def test_ha_status_online_re_publishes_discovery(qtbot, fake_user_settings, settings):
    ctx = DeviceContext(name="pc")
    session = MagicMock()
    entities = [_StubEntity("cpu_usage", 1)]
    pub = Publisher(session, ctx, settings, _SyncSampler(), entities, [])
    pub.on_ha_status("online")
    topics = [c.args[0] for c in session.publish.call_args_list]
    assert "homeassistant/sensor/swk_pc/cpu_usage/config" in topics
