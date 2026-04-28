from src.base.base_widget import BaseWidget


def test_set_enabled_is_noop_when_state_unchanged(qtbot):
    widget = BaseWidget(None, is_enabled=True)
    qtbot.addWidget(widget)

    captured: list[bool] = []
    widget.status_changed = lambda status: captured.append(status)
    widget.set_enabled(True)

    assert captured == []
    assert widget.is_enabled() is True


def test_set_enabled_transitions_and_notifies(qtbot):
    widget = BaseWidget(None, is_enabled=False)
    qtbot.addWidget(widget)

    captured: list[bool] = []
    widget.status_changed = lambda status: captured.append(status)
    widget.set_enabled(True)

    assert widget.is_enabled() is True
    assert captured == [True]


def test_set_enabled_round_trip(qtbot):
    widget = BaseWidget(None, is_enabled=False)
    qtbot.addWidget(widget)

    captured: list[bool] = []
    widget.status_changed = lambda status: captured.append(status)
    widget.set_enabled(True)
    widget.set_enabled(False)
    widget.set_enabled(False)  # no-op

    assert captured == [True, False]
    assert widget.is_enabled() is False


def test_get_display_name_falls_back_to_class_name(qtbot):
    widget = BaseWidget(None)
    qtbot.addWidget(widget)
    assert widget.get_display_name() == "BaseWidget"


def test_get_display_name_uses_explicit_attribute(qtbot):
    class NamedWidget(BaseWidget):
        display_name = "My Plugin"

    widget = NamedWidget(None)
    qtbot.addWidget(widget)
    assert widget.get_display_name() == "My Plugin"


def test_is_toggleable_reflects_constructor_arg(qtbot):
    on = BaseWidget(None, is_toggleable=True)
    off = BaseWidget(None, is_toggleable=False)
    qtbot.addWidget(on)
    qtbot.addWidget(off)

    assert on.is_toggleable() is True
    assert off.is_toggleable() is False
