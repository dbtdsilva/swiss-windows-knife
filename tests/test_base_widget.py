from swiss_windows_knife.base.base_widget import BaseWidget


def test_set_enabled_is_noop_when_state_unchanged(qtbot, fake_user_settings):
    widget = BaseWidget(None, is_enabled=True)
    qtbot.addWidget(widget)

    captured: list[bool] = []
    widget.status_changed = lambda status: captured.append(status)
    widget.set_enabled(True)

    assert captured == []
    assert widget.is_enabled() is True


def test_set_enabled_transitions_and_notifies(qtbot, fake_user_settings):
    widget = BaseWidget(None, is_enabled=False)
    qtbot.addWidget(widget)

    captured: list[bool] = []
    widget.status_changed = lambda status: captured.append(status)
    widget.set_enabled(True)

    assert widget.is_enabled() is True
    assert captured == [True]


def test_set_enabled_round_trip(qtbot, fake_user_settings):
    widget = BaseWidget(None, is_enabled=False)
    qtbot.addWidget(widget)

    captured: list[bool] = []
    widget.status_changed = lambda status: captured.append(status)
    widget.set_enabled(True)
    widget.set_enabled(False)
    widget.set_enabled(False)  # no-op

    assert captured == [True, False]
    assert widget.is_enabled() is False


def test_get_display_name_falls_back_to_class_name(qtbot, fake_user_settings):
    widget = BaseWidget(None)
    qtbot.addWidget(widget)
    assert widget.get_display_name() == "BaseWidget"


def test_get_display_name_uses_explicit_attribute(qtbot, fake_user_settings):
    class NamedWidget(BaseWidget):
        display_name = "My Plugin"

    widget = NamedWidget(None)
    qtbot.addWidget(widget)
    assert widget.get_display_name() == "My Plugin"


def test_is_toggleable_reflects_constructor_arg(qtbot, fake_user_settings):
    on = BaseWidget(None, is_toggleable=True)
    off = BaseWidget(None, is_toggleable=False)
    qtbot.addWidget(on)
    qtbot.addWidget(off)

    assert on.is_toggleable() is True
    assert off.is_toggleable() is False


def test_enabled_state_persists_via_user_settings(qtbot, fake_user_settings):
    class _Persisted(BaseWidget):
        pass

    w1 = _Persisted(None)
    qtbot.addWidget(w1)
    assert w1.is_enabled() is True  # default

    w1.set_enabled(False)
    assert w1.is_enabled() is False
    assert fake_user_settings.get_bool('plugin_enabled__Persisted', default=True) is False

    # New instance picks up the persisted value.
    w2 = _Persisted(None)
    qtbot.addWidget(w2)
    assert w2.is_enabled() is False


def test_enabled_state_normalises_string_values(qtbot, fake_user_settings):
    """QSettings on Windows returns booleans as the strings 'true' / 'false'."""
    class _StrBool(BaseWidget):
        pass

    fake_user_settings.set('plugin_enabled__StrBool', 'false')
    w = _StrBool(None)
    qtbot.addWidget(w)
    assert w.is_enabled() is False


def test_set_enabled_no_change_does_not_invoke_status_changed(qtbot, fake_user_settings):
    class _Spy(BaseWidget):
        def __init__(self, parent):
            super().__init__(parent)
            self.calls: list[bool] = []

        def status_changed(self, status: bool) -> None:
            self.calls.append(status)

    w = _Spy(None)
    qtbot.addWidget(w)
    w.set_enabled(True)  # already True
    assert w.calls == []

    w.set_enabled(False)
    assert w.calls == [False]


def test_health_defaults_to_ok_with_empty_message(qtbot, fake_user_settings):
    from swiss_windows_knife.base.health import HealthReport, HealthState
    widget = BaseWidget(None)
    qtbot.addWidget(widget)
    assert widget.health() == HealthReport(HealthState.OK, "")


def test_set_health_updates_current_health(qtbot, fake_user_settings):
    from swiss_windows_knife.base.health import HealthReport, HealthState
    widget = BaseWidget(None)
    qtbot.addWidget(widget)
    widget._set_health(HealthState.WARNING, "broker down")
    assert widget.health() == HealthReport(HealthState.WARNING, "broker down")


def test_health_returns_disabled_for_toggleable_off(qtbot, fake_user_settings):
    from swiss_windows_knife.base.health import HealthReport, HealthState
    widget = BaseWidget(None, is_toggleable=True, is_enabled=False)
    qtbot.addWidget(widget)
    widget._set_health(HealthState.WARNING, "ignored while off")
    assert widget.health() == HealthReport(HealthState.DISABLED, "Disabled")


def test_health_ignores_is_enabled_for_non_toggleable_widget(qtbot, fake_user_settings):
    from swiss_windows_knife.base.health import HealthReport, HealthState
    widget = BaseWidget(None, is_toggleable=False, is_enabled=False)
    qtbot.addWidget(widget)
    widget._set_health(HealthState.OK, "running")
    assert widget.health() == HealthReport(HealthState.OK, "running")


def test_health_changed_emits_on_state_change(qtbot, fake_user_settings):
    from swiss_windows_knife.base.health import HealthState
    widget = BaseWidget(None)
    qtbot.addWidget(widget)

    fired: list[None] = []
    widget.health_changed.connect(lambda: fired.append(None))

    widget._set_health(HealthState.WARNING, "x")
    assert fired == [None]


def test_health_changed_emits_on_message_change(qtbot, fake_user_settings):
    from swiss_windows_knife.base.health import HealthState
    widget = BaseWidget(None)
    qtbot.addWidget(widget)
    widget._set_health(HealthState.OK, "Auto")

    fired: list[None] = []
    widget.health_changed.connect(lambda: fired.append(None))

    widget._set_health(HealthState.OK, "Manual 60")
    assert fired == [None]


def test_health_changed_does_not_emit_on_noop(qtbot, fake_user_settings):
    from swiss_windows_knife.base.health import HealthState
    widget = BaseWidget(None)
    qtbot.addWidget(widget)
    widget._set_health(HealthState.OK, "Auto")

    fired: list[None] = []
    widget.health_changed.connect(lambda: fired.append(None))

    widget._set_health(HealthState.OK, "Auto")  # same value
    assert fired == []


def test_health_changed_emits_on_set_enabled_transition(qtbot, fake_user_settings):
    widget = BaseWidget(None, is_toggleable=True, is_enabled=True)
    qtbot.addWidget(widget)

    fired: list[None] = []
    widget.health_changed.connect(lambda: fired.append(None))

    widget.set_enabled(False)
    assert fired == [None]


def test_health_changed_does_not_emit_on_set_enabled_noop(qtbot, fake_user_settings):
    widget = BaseWidget(None, is_toggleable=True, is_enabled=True)
    qtbot.addWidget(widget)

    fired: list[None] = []
    widget.health_changed.connect(lambda: fired.append(None))

    widget.set_enabled(True)  # already True
    assert fired == []
