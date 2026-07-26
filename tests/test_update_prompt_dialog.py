from PySide6.QtWidgets import QTextBrowser


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


def test_dialog_skip_checkbox_reports_state(qtbot):
    from swiss_windows_knife.components.update_prompt_dialog import UpdatePromptDialog
    d = UpdatePromptDialog("1.21.0", [])
    qtbot.addWidget(d)
    assert d.skip_checked() is False
    d._skip_checkbox.setChecked(True)
    assert d.skip_checked() is True
