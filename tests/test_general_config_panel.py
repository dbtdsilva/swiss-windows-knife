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
def make_panel(qtbot, fake_user_settings, monkeypatch):
    from swiss_windows_knife.ui import general_config_panel
    from swiss_windows_knife.ui.general_config_panel import GeneralConfigPanel

    applied: list = []
    monkeypatch.setattr(general_config_panel, "apply_preference",
                        lambda pref: applied.append(pref))

    def _make(plugins):
        panel = GeneralConfigPanel(plugins)
        qtbot.addWidget(panel)
        panel._test_applied = applied
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


def test_color_scheme_defaults_to_follow_system(make_panel, fake_user_settings):
    from swiss_windows_knife.base.color_scheme import ColorSchemePreference

    panel = make_panel([])
    assert panel._color_scheme_combo.currentData() is ColorSchemePreference.SYSTEM


def test_color_scheme_reads_persisted_preference(make_panel, fake_user_settings):
    from swiss_windows_knife.base.color_scheme import (
        SETTINGS_KEY,
        ColorSchemePreference,
    )

    fake_user_settings.set(SETTINGS_KEY, ColorSchemePreference.DARK)
    panel = make_panel([])
    assert panel._color_scheme_combo.currentData() is ColorSchemePreference.DARK


def test_changing_combo_previews_color_scheme_live(make_panel, fake_user_settings):
    from swiss_windows_knife.base.color_scheme import ColorSchemePreference

    panel = make_panel([])
    dark_index = panel._color_scheme_combo.findData(ColorSchemePreference.DARK)
    panel._color_scheme_combo.setCurrentIndex(dark_index)
    # Live preview pushed the new scheme to QStyleHints immediately, without apply().
    assert panel._test_applied == [ColorSchemePreference.DARK]


def test_apply_persists_changed_color_scheme(make_panel, fake_user_settings):
    from swiss_windows_knife.base.color_scheme import (
        SETTINGS_KEY,
        ColorSchemePreference,
    )

    panel = make_panel([])
    dark_index = panel._color_scheme_combo.findData(ColorSchemePreference.DARK)
    panel._color_scheme_combo.setCurrentIndex(dark_index)

    assert panel.apply() is True
    assert fake_user_settings.get(SETTINGS_KEY, ColorSchemePreference) is ColorSchemePreference.DARK
    # apply() itself doesn't reapply — the live preview already did.
    assert panel._test_applied == [ColorSchemePreference.DARK]


def test_apply_skips_color_scheme_when_unchanged(make_panel, fake_user_settings):
    from swiss_windows_knife.base.color_scheme import (
        SETTINGS_KEY,
        ColorSchemePreference,
    )

    fake_user_settings.set(SETTINGS_KEY, ColorSchemePreference.LIGHT)
    panel = make_panel([])

    assert panel.apply() is True
    # No re-apply because the user never touched the combo.
    assert panel._test_applied == []


def test_cleanup_reverts_live_preview_when_apply_not_called(make_panel, fake_user_settings):
    from swiss_windows_knife.base.color_scheme import ColorSchemePreference

    panel = make_panel([])
    dark_index = panel._color_scheme_combo.findData(ColorSchemePreference.DARK)
    panel._color_scheme_combo.setCurrentIndex(dark_index)
    assert panel._test_applied == [ColorSchemePreference.DARK]

    # User cancels — cleanup runs, restoring whatever was the committed baseline.
    panel.cleanup()
    assert panel._test_applied == [ColorSchemePreference.DARK, ColorSchemePreference.SYSTEM]


def test_cleanup_does_not_revert_after_apply(make_panel, fake_user_settings):
    from swiss_windows_knife.base.color_scheme import ColorSchemePreference

    panel = make_panel([])
    dark_index = panel._color_scheme_combo.findData(ColorSchemePreference.DARK)
    panel._color_scheme_combo.setCurrentIndex(dark_index)
    panel.apply()
    # The combo position now matches the committed baseline → no revert call.
    panel.cleanup()
    assert panel._test_applied == [ColorSchemePreference.DARK]
