from unittest.mock import MagicMock, patch

import monitorcontrol
import pytest

from swiss_windows_knife.base.health import HealthState


@pytest.fixture
def plugin(qtbot, fake_user_settings):
    from swiss_windows_knife.plugins.display_image_tuner.image_tuner_plugin import DisplayImageTunerPlugin
    p = DisplayImageTunerPlugin(None)
    qtbot.addWidget(p)
    return p


def test_initial_health_is_ok_auto(plugin):
    report = plugin.health()
    assert report.state is HealthState.OK
    assert report.message == "Auto"


def test_health_message_reflects_manual_brightness(qtbot, fake_user_settings):
    fake_user_settings.set("brightness", 60)
    from swiss_windows_knife.plugins.display_image_tuner.image_tuner_plugin import DisplayImageTunerPlugin
    p = DisplayImageTunerPlugin(None)
    qtbot.addWidget(p)
    assert p.health().message == "Manual 60"


def _stub_monitor(value: int):
    cm = MagicMock()
    cm.__enter__ = lambda self: self
    cm.__exit__ = lambda self, exc_type, exc, tb: None
    cm.get_luminance = MagicMock(return_value=value)
    cm.set_luminance = MagicMock()
    cm.get_contrast = MagicMock(return_value=value)
    cm.set_contrast = MagicMock()
    return cm


def test_apply_brightness_failure_sets_warning(plugin):
    with patch("monitorcontrol.get_monitors", side_effect=monitorcontrol.VCPError("boom")):
        plugin._apply_brightness(50)
    assert plugin.health().state is HealthState.WARNING
    assert "Monitor error" in plugin.health().message


def test_apply_brightness_success_restores_ok(plugin):
    with patch("monitorcontrol.get_monitors", side_effect=monitorcontrol.VCPError("boom")):
        plugin._apply_brightness(50)
    assert plugin.health().state is HealthState.WARNING

    with patch("monitorcontrol.get_monitors", return_value=[_stub_monitor(0)]):
        plugin._apply_brightness(50)
    assert plugin.health().state is HealthState.OK


def test_apply_failure_invalidates_last_emitted_so_tick_retries(plugin):
    # _tick advances _last_emitted before the async runner has tried to
    # write — if the write fails, the dedup gate must not lock the plugin
    # at the never-applied value, or auto mode stops updating the monitor.
    plugin._last_emitted['brightness'] = 50
    plugin._last_emitted['contrast'] = 70
    with patch("monitorcontrol.get_monitors", side_effect=monitorcontrol.VCPError("boom")):
        plugin._apply_brightness(50)
        plugin._apply_contrast(70)
    assert plugin._last_emitted['brightness'] is None
    assert plugin._last_emitted['contrast'] is None


def test_apply_success_preserves_last_emitted(plugin):
    plugin._last_emitted['brightness'] = 50
    plugin._last_emitted['contrast'] = 70
    with patch("monitorcontrol.get_monitors", return_value=[_stub_monitor(0)]):
        plugin._apply_brightness(50)
        plugin._apply_contrast(70)
    assert plugin._last_emitted['brightness'] == 50
    assert plugin._last_emitted['contrast'] == 70
