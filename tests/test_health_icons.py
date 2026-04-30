from src.base.health import HealthState


def test_icon_for_state_returns_qicon(qtbot):
    from src.ui.health_icons import icon_for_state

    for state in HealthState:
        icon = icon_for_state(state)
        assert not icon.isNull(), f"icon for {state} is null"


def test_icon_is_cached_per_state(qtbot):
    from src.ui.health_icons import icon_for_state

    a = icon_for_state(HealthState.OK)
    b = icon_for_state(HealthState.OK)
    assert a is b
