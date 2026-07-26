from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTextBrowser,
    QVBoxLayout,
)


class UpdatePromptDialog(QDialog):
    """Asks whether to install `target_version`, showing the concatenated
    release notes for every version being skipped. `skip_checked()` lets the
    caller persist a per-version skip when the user declines."""

    def __init__(self, target_version, changelog_entries, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Update Available')

        self._skip_checkbox = QCheckBox(
            f"Don't ask again for version {target_version}")

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            f'Version {target_version} is available. Install now?'))

        browser = QTextBrowser(self)
        browser.setOpenExternalLinks(True)
        browser.setMarkdown(self._render_markdown(changelog_entries))
        browser.setMinimumSize(480, 320)
        layout.addWidget(browser)

        layout.addWidget(self._skip_checkbox)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Yes
            | QDialogButtonBox.StandardButton.No)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

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
        return self._skip_checkbox.isChecked()
