import pytest


class _FakePlugin:
    """Stand-in for a BaseWidget plugin: just enough surface for the panel."""

    def __init__(self, name: str, enabled: bool = True, toggleable: bool = True):
        self._name = name
        self._enabled = enabled
        self._toggleable = toggleable
        self.toggle_log: list[bool] = []

    def get_display_name(self) -> str:
        return self._name

    def is_enabled(self) -> bool:
        return self._enabled

    def is_toggleable(self) -> bool:
        return self._toggleable

    def set_enabled(self, value: bool) -> None:
        self._enabled = value
        self.toggle_log.append(value)


@pytest.fixture
def make_panel(qtbot, fake_user_settings):
    from swiss_windows_knife.ui.plugins_config_panel import PluginsConfigPanel

    def _make(plugins):
        panel = PluginsConfigPanel(plugins)
        qtbot.addWidget(panel)
        return panel

    return _make


def test_panel_lists_only_toggleable_plugins(make_panel):
    plugins = [
        _FakePlugin("First", enabled=True, toggleable=True),
        _FakePlugin("Locked", enabled=True, toggleable=False),
        _FakePlugin("Third", enabled=False, toggleable=True),
    ]
    panel = make_panel(plugins)
    assert set(panel._checkboxes.keys()) == {plugins[0], plugins[2]}
    assert panel._checkboxes[plugins[0]].isChecked() is True
    assert panel._checkboxes[plugins[2]].isChecked() is False


def test_apply_calls_set_enabled_only_for_changed_state(make_panel):
    plugins = [
        _FakePlugin("On", enabled=True),
        _FakePlugin("Off", enabled=False),
    ]
    panel = make_panel(plugins)
    panel._checkboxes[plugins[0]].setChecked(False)  # changed
    # plugins[1]: untouched

    assert panel.apply() is True
    assert plugins[0].toggle_log == [False]
    assert plugins[1].toggle_log == []


def test_panel_emits_signal_when_a_checkbox_is_toggled(qtbot, make_panel):
    plugin = _FakePlugin("First")
    panel = make_panel([plugin])

    received: list[tuple] = []
    panel.plugin_toggled.connect(lambda p, val: received.append((p, val)))

    panel._checkboxes[plugin].setChecked(False)
    assert received == [(plugin, False)]

    panel._checkboxes[plugin].setChecked(True)
    assert received == [(plugin, False), (plugin, True)]
