from unittest.mock import patch

import pytest


@pytest.fixture
def checker(qtbot, fake_user_settings):
    from swiss_windows_knife.components.update_checker import UpdateChecker
    with patch.object(UpdateChecker, "check_updates"):
        c = UpdateChecker(parent=None)
        qtbot.addWidget(c)
    return c


def test_updates_menu_has_check_and_auto_toggle(checker):
    menus = checker.retrieve_menus()
    assert len(menus) == 1
    menu = menus[0]
    assert menu.title() == 'Updates'
    texts = [a.text() for a in menu.actions()]
    assert 'Automatic updates' in texts
    auto = next(a for a in menu.actions() if a.text() == 'Automatic updates')
    assert auto.isCheckable()
    assert auto.isChecked() is False


def test_auto_toggle_reflects_persisted_setting(checker, fake_user_settings):
    fake_user_settings.set('update_automatic', True)
    menu = checker.retrieve_menus()[0]
    auto = next(a for a in menu.actions() if a.text() == 'Automatic updates')
    assert auto.isChecked() is True


def test_toggling_auto_updates_persists_setting(checker, fake_user_settings):
    menu = checker.retrieve_menus()[0]
    auto = next(a for a in menu.actions() if a.text() == 'Automatic updates')
    auto.setChecked(True)
    assert fake_user_settings.get('update_automatic', bool, False) is True
