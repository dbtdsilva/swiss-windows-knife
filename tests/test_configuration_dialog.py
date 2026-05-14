import pytest

from swiss_windows_knife.base.config_panel import ConfigPanel


class _NamedPanel(ConfigPanel):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.title = title
        self.applied = False

    def apply(self) -> bool:
        self.applied = True
        return True


class _FakePlugin:
    instances: list = []

    def __init__(self, name: str, enabled: bool, panels: list[ConfigPanel]):
        self._name = name
        self._enabled = enabled
        self._panels = panels
        self._toggleable = True
        self.set_enabled_log: list[bool] = []
        _FakePlugin.instances.append(self)

    def get_display_name(self):
        return self._name

    def is_enabled(self):
        return self._enabled

    def is_toggleable(self):
        return self._toggleable

    def set_enabled(self, value: bool) -> None:
        self._enabled = value
        self.set_enabled_log.append(value)

    def retrieve_config_panels(self):
        return list(self._panels)


@pytest.fixture(autouse=True)
def _reset():
    _FakePlugin.instances.clear()
    yield
    _FakePlugin.instances.clear()


def _visible_tab_titles(tabs) -> list[str]:
    return [tabs.tabText(i) for i in range(tabs.count()) if tabs.isTabVisible(i)]


@pytest.fixture
def make_dialog(qtbot, fake_user_settings):
    from swiss_windows_knife.ui.configuration_dialog import ConfigurationDialog

    def _make(plugins):
        dlg = ConfigurationDialog(None, plugins)
        qtbot.addWidget(dlg)
        return dlg

    return _make


def test_dialog_includes_general_tab_first(make_dialog):
    enabled = _FakePlugin("Enabled", True, [_NamedPanel("EnabledPanel")])
    dlg = make_dialog([enabled])
    tabs = dlg._tabs
    assert tabs.tabText(0) == "General"
    assert tabs.tabText(1) == "EnabledPanel"


def test_disabled_plugin_panels_are_hidden_initially(make_dialog):
    enabled = _FakePlugin("E", True, [_NamedPanel("EPanel")])
    disabled = _FakePlugin("D", False, [_NamedPanel("DPanel")])
    dlg = make_dialog([enabled, disabled])
    assert _visible_tab_titles(dlg._tabs) == ["General", "EPanel"]


def test_enabling_via_general_panel_inserts_tab(make_dialog):
    enabled = _FakePlugin("E", True, [_NamedPanel("EPanel")])
    disabled = _FakePlugin("D", False, [_NamedPanel("DPanel")])
    dlg = make_dialog([enabled, disabled])
    general_panel = dlg._general_panel
    general_panel._checkboxes[disabled].setChecked(True)

    assert "DPanel" in _visible_tab_titles(dlg._tabs)


def test_disabling_via_general_panel_removes_tab(make_dialog):
    enabled = _FakePlugin("E", True, [_NamedPanel("EPanel")])
    dlg = make_dialog([enabled])
    general_panel = dlg._general_panel
    general_panel._checkboxes[enabled].setChecked(False)

    assert "EPanel" not in _visible_tab_titles(dlg._tabs)


def test_per_plugin_tabs_render_in_alphabetical_order(make_dialog):
    p1 = _FakePlugin("Whatever", True, [_NamedPanel("Zeta")])
    p2 = _FakePlugin("Whatever", True, [_NamedPanel("Alpha"), _NamedPanel("Mu")])
    dlg = make_dialog([p1, p2])
    assert _visible_tab_titles(dlg._tabs) == ["General", "Alpha", "Mu", "Zeta"]


def test_enabling_inserts_tab_at_alphabetical_position(make_dialog):
    enabled = _FakePlugin("E", True, [_NamedPanel("Beta"), _NamedPanel("Yankee")])
    disabled = _FakePlugin("D", False, [_NamedPanel("Mike")])
    dlg = make_dialog([enabled, disabled])
    assert _visible_tab_titles(dlg._tabs) == ["General", "Beta", "Yankee"]

    dlg._general_panel._checkboxes[disabled].setChecked(True)
    assert _visible_tab_titles(dlg._tabs) == [
        "General", "Beta", "Mike", "Yankee",
    ]


def test_apply_runs_per_plugin_panels_before_general_panel(make_dialog):
    enabled = _FakePlugin("E", True, [_NamedPanel("EPanel")])
    dlg = make_dialog([enabled])
    general_panel = dlg._general_panel
    general_panel._checkboxes[enabled].setChecked(False)

    dlg._on_accept()

    # Per-plugin panel applied before the General panel toggled the plugin off.
    panel_apply_call_index = [
        i for i, p in enumerate(dlg._all_panels) if p is enabled._panels[0]
    ][0]
    general_panel_index = dlg._all_panels.index(general_panel)
    assert panel_apply_call_index < general_panel_index
    assert enabled.set_enabled_log == [False]
