import pytest

from src.base.health import HealthReport, HealthState


def test_aggregate_health_all_ok():
    from src.ui.tray_widget import aggregate_health

    reports = [HealthReport(HealthState.OK, ""), HealthReport(HealthState.OK, "")]
    state, text = aggregate_health(reports)
    assert state is HealthState.OK
    assert text == "Health: All OK"


def test_aggregate_health_disabled_does_not_contribute():
    from src.ui.tray_widget import aggregate_health

    reports = [HealthReport(HealthState.OK, ""), HealthReport(HealthState.DISABLED, "")]
    state, text = aggregate_health(reports)
    assert state is HealthState.OK
    assert text == "Health: All OK"


def test_aggregate_health_warning_count():
    from src.ui.tray_widget import aggregate_health

    reports = [
        HealthReport(HealthState.OK, ""),
        HealthReport(HealthState.WARNING, "x"),
        HealthReport(HealthState.WARNING, "y"),
    ]
    state, text = aggregate_health(reports)
    assert state is HealthState.WARNING
    assert text == "Health: 2 warning(s), 0 error(s)"


def test_aggregate_health_error_outranks_warning():
    from src.ui.tray_widget import aggregate_health

    reports = [
        HealthReport(HealthState.WARNING, ""),
        HealthReport(HealthState.ERROR, ""),
    ]
    state, text = aggregate_health(reports)
    assert state is HealthState.ERROR
    assert text == "Health: 1 warning(s), 1 error(s)"


class _StubPlugin:
    def __init__(self, name: str, report: HealthReport):
        self._name = name
        self._report = report

    def get_display_name(self):
        return self._name

    def is_toggleable(self):
        return True

    def is_enabled(self):
        return self._report.state is not HealthState.DISABLED

    def health(self):
        return self._report

    def retrieve_menus(self):
        return []

    def close(self):
        pass


@pytest.fixture
def tray_with_stubs(qtbot, fake_user_settings):
    """Build a TrayWidget-like instance backed by a real QWidget so QAction
    parenting works, but skipping the real plugin construction and the
    QSystemTrayIcon side-effects."""
    from PySide6.QtWidgets import QWidget

    from src.ui.tray_widget import TrayWidget

    class _TrayForTest(TrayWidget):
        def __init__(self, stubs):
            QWidget.__init__(self, parent=None)
            self._config_dialog = None
            self.logger_window = None
            self.child_components = stubs

    def _make(stubs):
        tray = _TrayForTest(stubs)
        qtbot.addWidget(tray)
        return tray

    return _make


def test_main_menu_starts_with_summary_and_health_submenu(qtbot, tray_with_stubs):
    plugins = [
        _StubPlugin("Alpha", HealthReport(HealthState.OK, "Auto")),
        _StubPlugin("Bravo", HealthReport(HealthState.WARNING, "Disconnected")),
    ]
    tray = tray_with_stubs(plugins)

    from PySide6.QtWidgets import QMenu
    menu = QMenu()
    tray._populate_main_menu(menu)
    actions = menu.actions()

    assert actions[0].text() == "Health: 1 warning(s), 0 error(s)"
    assert actions[0].isEnabled() is False  # summary line is informational

    health_submenu = actions[1].menu()
    assert health_submenu is not None
    rows = [a.text() for a in health_submenu.actions()]
    assert rows == ["Alpha — Auto", "Bravo — Disconnected"]


def test_main_menu_summary_all_ok_when_only_disabled_remain(qtbot, tray_with_stubs):
    plugins = [
        _StubPlugin("Alpha", HealthReport(HealthState.DISABLED, "Disabled")),
        _StubPlugin("Bravo", HealthReport(HealthState.OK, "Listening")),
    ]
    tray = tray_with_stubs(plugins)

    from PySide6.QtWidgets import QMenu
    menu = QMenu()
    tray._populate_main_menu(menu)
    assert menu.actions()[0].text() == "Health: All OK"

    health_submenu = menu.actions()[1].menu()
    rows = [a.text() for a in health_submenu.actions()]
    assert rows == ["Alpha — Disabled", "Bravo — Listening"]


def test_health_row_for_failing_plugin_does_not_break_menu(qtbot, tray_with_stubs):
    class _Bad(_StubPlugin):
        def health(self):
            raise RuntimeError("boom")

    plugins = [
        _Bad("Bad", HealthReport(HealthState.OK, "")),
        _StubPlugin("Good", HealthReport(HealthState.OK, "ok")),
    ]
    tray = tray_with_stubs(plugins)

    from PySide6.QtWidgets import QMenu
    menu = QMenu()
    tray._populate_main_menu(menu)
    health_submenu = menu.actions()[1].menu()
    rows = [a.text() for a in health_submenu.actions()]
    assert rows[0] == "Bad — health() failed"
    assert rows[1] == "Good — ok"
