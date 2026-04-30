from swiss_windows_knife.base.health import HealthState


def test_icon_for_state_returns_qicon(qtbot):
    from swiss_windows_knife.ui.health_icons import icon_for_state

    for state in HealthState:
        icon = icon_for_state(state)
        assert not icon.isNull(), f"icon for {state} is null"


def test_icon_is_cached_per_state(qtbot):
    from swiss_windows_knife.ui.health_icons import icon_for_state

    a = icon_for_state(HealthState.OK)
    b = icon_for_state(HealthState.OK)
    assert a is b


def test_tray_icon_for_state_returns_non_null(qtbot):
    # Resources must be loaded so :/icons/coat-of-arms.ico resolves.
    from swiss_windows_knife import resources  # noqa: F401
    from swiss_windows_knife.ui.health_icons import tray_icon_for_state

    for state in HealthState:
        icon = tray_icon_for_state(state)
        assert not icon.isNull(), f"tray icon for {state} is null"


def test_tray_icon_for_state_is_cached(qtbot):
    from swiss_windows_knife import resources  # noqa: F401
    from swiss_windows_knife.ui.health_icons import tray_icon_for_state

    a = tray_icon_for_state(HealthState.OK)
    b = tray_icon_for_state(HealthState.OK)
    assert a is b
