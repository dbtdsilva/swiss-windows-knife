from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTextBrowser,
    QVBoxLayout,
)


class UpdatePromptDialog(QDialog):
    """Asks whether to install `target_version`, showing the concatenated
    release notes for every version being skipped. `skip_checked()` reports
    whether the user chose 'Don't ask again for this version' (vs. simply
    dismissing the dialog, which declines but re-prompts next check)."""

    def __init__(self, target_version, changelog_entries, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Update Available')

        self._skip = False

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            f'Version {target_version} is available. Install now?'))

        browser = QTextBrowser(self)
        browser.setOpenExternalLinks(True)
        browser.setMarkdown(self._render_markdown(changelog_entries))
        browser.setMinimumSize(480, 320)
        layout.addWidget(browser)

        buttons = QDialogButtonBox(self)
        self._install_button = buttons.addButton(
            'Install now', QDialogButtonBox.ButtonRole.AcceptRole)
        self._skip_button = buttons.addButton(
            "Don't ask again for this version",
            QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.accept)
        self._skip_button.clicked.connect(self._decline_and_skip)
        layout.addWidget(buttons)

    def _decline_and_skip(self) -> None:
        self._skip = True
        self.reject()

    @staticmethod
    def _render_markdown(changelog_entries) -> str:
        if not changelog_entries:
            return "_No release notes available._"
        blocks = []
        for tag, body in changelog_entries:
            text = (body or "").strip() or "_No notes for this release._"
            blocks.append(f"## {tag}\n\n{text}")
        return "\n\n---\n\n".join(blocks)

    def skip_checked(self) -> bool:
        return self._skip
