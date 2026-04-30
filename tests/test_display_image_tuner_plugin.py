import pytest


@pytest.fixture
def plugin(qtbot, fake_user_settings):
    """Construct the plugin in isolation, with no UserSettings preconditions."""
    from src.plugins.display_image_tuner.image_tuner_plugin import DisplayImageTunerPlugin
    p = DisplayImageTunerPlugin(None)
    qtbot.addWidget(p)
    return p


def test_tick_timer_runs_when_enabled(plugin):
    assert plugin._tick_timer.isActive()


def test_status_changed_false_stops_tick_timer(plugin):
    plugin.status_changed(False)
    assert not plugin._tick_timer.isActive()


def test_status_changed_true_starts_tick_timer(plugin):
    plugin.status_changed(False)
    plugin.status_changed(True)
    assert plugin._tick_timer.isActive()


def test_construction_skips_timer_when_persisted_disabled(qtbot, fake_user_settings):
    fake_user_settings.set('plugin_enabled_DisplayImageTunerPlugin', False)
    from src.plugins.display_image_tuner.image_tuner_plugin import DisplayImageTunerPlugin
    p = DisplayImageTunerPlugin(None)
    qtbot.addWidget(p)
    assert not p._tick_timer.isActive()
