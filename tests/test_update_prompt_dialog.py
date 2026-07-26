from PySide6.QtWidgets import QCheckBox, QDialog, QTextBrowser


def test_dialog_renders_all_changelog_entries(qtbot):
    from swiss_windows_knife.components.update_prompt_dialog import UpdatePromptDialog
    d = UpdatePromptDialog(
        "1.21.0", [("v1.21.0", "New shiny"), ("v1.20.0", "Older fix")])
    qtbot.addWidget(d)
    text = d.findChild(QTextBrowser).toPlainText()
    assert "1.21.0" in text and "New shiny" in text
    assert "1.20.0" in text and "Older fix" in text


def test_dialog_handles_empty_changelog(qtbot):
    from swiss_windows_knife.components.update_prompt_dialog import UpdatePromptDialog
    d = UpdatePromptDialog("1.21.0", [])
    qtbot.addWidget(d)
    assert d.findChild(QTextBrowser) is not None


def test_skip_defaults_to_false(qtbot):
    from swiss_windows_knife.components.update_prompt_dialog import UpdatePromptDialog
    d = UpdatePromptDialog("1.21.0", [])
    qtbot.addWidget(d)
    assert d.skip_checked() is False


def test_dont_ask_again_button_sets_skip_and_rejects(qtbot):
    from swiss_windows_knife.components.update_prompt_dialog import UpdatePromptDialog
    d = UpdatePromptDialog("1.21.0", [])
    qtbot.addWidget(d)
    d._skip_button.click()
    assert d.skip_checked() is True
    assert d.result() == QDialog.DialogCode.Rejected


def test_install_button_accepts_without_skip(qtbot):
    from swiss_windows_knife.components.update_prompt_dialog import UpdatePromptDialog
    d = UpdatePromptDialog("1.21.0", [])
    qtbot.addWidget(d)
    d._install_button.click()
    assert d.result() == QDialog.DialogCode.Accepted
    assert d.skip_checked() is False


def test_no_dont_ask_again_checkbox_present(qtbot):
    # The old checkbox is gone; the skip choice is now a button.
    from swiss_windows_knife.components.update_prompt_dialog import UpdatePromptDialog
    d = UpdatePromptDialog("1.21.0", [])
    qtbot.addWidget(d)
    assert d.findChild(QCheckBox) is None
    assert d._install_button.text() == 'Install now'
    assert d._skip_button.text() == "Don't ask again for this version"
