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


def test_main_menu_first_entry_is_health_submenu_with_summary_title(qtbot, tray_with_stubs):
    plugins = [
        _StubPlugin("Alpha", HealthReport(HealthState.OK, "Auto")),
        _StubPlugin("Bravo", HealthReport(HealthState.WARNING, "Disconnected")),
    ]
    tray = tray_with_stubs(plugins)

    from PySide6.QtWidgets import QMenu
    menu = QMenu()
    tray._populate_main_menu(menu)

    health_submenu = menu.actions()[0].menu()
    assert health_submenu is not None
    assert health_submenu.title() == "Health: 1 warning(s), 0 error(s)"
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

    health_submenu = menu.actions()[0].menu()
    assert health_submenu.title() == "Health: All OK"
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
    health_submenu = menu.actions()[0].menu()
    rows = [a.text() for a in health_submenu.actions()]
    assert rows[0] == "Bad — health() failed"
    assert rows[1] == "Good — ok"


def test_tray_icon_refreshes_on_plugin_health_change(qtbot, fake_user_settings):
    """The tray's icon refresh slot is wired to each plugin's health_changed
    signal and rebuilds the icon via tray_icon_for_state."""
    from unittest.mock import MagicMock

    from PySide6.QtCore import Signal
    from PySide6.QtWidgets import QWidget

    from src import resources  # noqa: F401
    from src.base.health import HealthState
    from src.ui.tray_widget import TrayWidget

    class _SignalingPlugin(QWidget):
        health_changed = Signal()

        def __init__(self, name: str, report: HealthReport):
            super().__init__()
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

        def set_report(self, report: HealthReport) -> None:
            self._report = report
            self.health_changed.emit()

    plugins = [
        _SignalingPlugin("Alpha", HealthReport(HealthState.OK, "ok")),
        _SignalingPlugin("Bravo", HealthReport(HealthState.OK, "ok")),
    ]

    class _TrayForTest(TrayWidget):
        def __init__(self, components):
            QWidget.__init__(self, parent=None)
            self._config_dialog = None
            self.logger_window = None
            self.child_components = components
            self._tray_icon = MagicMock()
            self._wire_health_signals()
            self._refresh_tray_icon()

    tray = _TrayForTest(plugins)
    qtbot.addWidget(tray)

    # Initial refresh in __init__ called setIcon once with the OK icon.
    assert tray._tray_icon.setIcon.call_count == 1

    tray._tray_icon.setIcon.reset_mock()
    plugins[1].set_report(HealthReport(HealthState.WARNING, "broker down"))
    assert tray._tray_icon.setIcon.call_count == 1
