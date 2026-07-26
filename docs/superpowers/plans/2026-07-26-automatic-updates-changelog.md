# Automatic Updates + Multi-Version Changelog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in "Automatic updates" toggle that installs silently in the background, and show the release notes for every version between the installed one and the target when prompting.

**Architecture:** Extend `components/update_checker.py`: a pure `_releases_above` helper does the version math over GitHub's `/releases` list; `_CheckThread` emits `(target, installer_url, changelog)`; `_on_check_finished` branches on a new `update_automatic` setting (silent + tray notification vs. a new `UpdatePromptDialog` with scrollable markdown changelog). A new `notification_requested` signal is relayed to the tray balloon by `TrayWidget`.

**Tech Stack:** Python 3.12, PySide6 (Qt), pytest + pytest-qt, `requests`. Dev venv at `./env/`. Tests run with `QT_QPA_PLATFORM=offscreen`.

---

## File Structure

- **Modify** `swiss_windows_knife/components/update_checker.py` — `/releases` fetch, `_releases_above` helper, `Updates` submenu with checkable toggle, `notification_requested` signal, auto/manual branch, `_start_download` extraction, `_confirm_update(target, changelog)`.
- **Create** `swiss_windows_knife/components/update_prompt_dialog.py` — `UpdatePromptDialog`, the manual prompt with a `QTextBrowser` changelog.
- **Modify** `swiss_windows_knife/ui/tray_widget.py` — connect `notification_requested` → tray balloon.
- **Create** `tests/test_update_checker_releases.py` — pure `_releases_above` tests.
- **Create** `tests/test_update_checker_menu.py` — `Updates` submenu / toggle tests.
- **Create** `tests/test_update_prompt_dialog.py` — dialog rendering / checkbox tests.
- **Modify** `tests/test_update_checker_workers.py` — new `/releases` result shape.
- **Modify** `tests/test_update_checker_health.py` — new 3-tuple result shape + auto/manual branch + confirm tests.

Conventions: no comments unless they explain non-obvious intent; **no `Co-Authored-By` trailer** in commits; angular conventional commit tags.

---

### Task 1: Pure `_releases_above` version/release helper

**Files:**
- Modify: `swiss_windows_knife/components/update_checker.py` (add function + `RELEASES_URL` constant near `LATEST_RELEASE_URL:16`)
- Test: `tests/test_update_checker_releases.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_update_checker_releases.py`:

```python
from swiss_windows_knife.components.update_checker import _releases_above


def _exe(v):
    return {"name": f"Installer-{v}.exe",
            "browser_download_url": f"https://example/{v}.exe"}


def test_releases_above_filters_drafts_and_prereleases():
    releases = [
        {"tag_name": "2.0.0", "draft": True, "assets": [_exe("2.0.0")]},
        {"tag_name": "1.5.0", "prerelease": True, "assets": [_exe("1.5.0")]},
        {"tag_name": "1.4.0", "body": "notes", "assets": [_exe("1.4.0")]},
    ]
    target, url, changelog = _releases_above(releases, "1.0.0")
    assert target == "1.4.0"
    assert url == "https://example/1.4.0.exe"
    assert [t for t, _ in changelog] == ["1.4.0"]


def test_releases_above_lists_all_versions_above_current_newest_first():
    releases = [
        {"tag_name": "1.4.0", "body": "c", "assets": [_exe("1.4.0")]},
        {"tag_name": "1.2.0", "body": "a", "assets": []},
        {"tag_name": "1.3.0", "body": "b", "assets": []},
    ]
    target, url, changelog = _releases_above(releases, "1.1.0")
    assert target == "1.4.0"
    assert changelog == [("1.4.0", "c"), ("1.3.0", "b"), ("1.2.0", "a")]


def test_releases_above_excludes_current_and_older():
    releases = [
        {"tag_name": "1.1.0", "body": "x", "assets": [_exe("1.1.0")]},
        {"tag_name": "1.0.0", "body": "old", "assets": []},
    ]
    target, url, changelog = _releases_above(releases, "1.1.0")
    assert target == "1.1.0"
    assert changelog == []


def test_releases_above_none_when_target_has_no_installer():
    releases = [{"tag_name": "2.0.0", "assets": [{"name": "notes.txt"}]}]
    assert _releases_above(releases, "1.0.0") == (None, None, [])


def test_releases_above_none_when_empty():
    assert _releases_above([], "1.0.0") == (None, None, [])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./env/Scripts/python.exe -m pytest tests/test_update_checker_releases.py -q`
Expected: FAIL — `ImportError: cannot import name '_releases_above'`.

- [ ] **Step 3: Implement the helper**

In `swiss_windows_knife/components/update_checker.py`, add a `RELEASES_URL` constant next to `LATEST_RELEASE_URL` (line 16) and the function just below `_parse_version` (after line 35):

```python
RELEASES_URL = 'https://api.github.com/repos/dbtdsilva/swiss-windows-knife/releases'
```

```python
def _releases_above(releases, current):
    """From a GitHub /releases list, return
    (target_tag, installer_url, changelog_entries).

    Drafts and prereleases are ignored. `target_tag` is the highest stable
    version; `installer_url` is its first `.exe` asset; `changelog_entries`
    are (tag, body) for every stable release strictly newer than `current`,
    newest-first. Returns (None, None, []) when no stable release carries an
    installer asset.
    """
    current_v = _parse_version(current)
    stable = [
        r for r in releases
        if not r.get('draft') and not r.get('prerelease') and 'tag_name' in r
    ]
    if not stable:
        return None, None, []
    target = max(stable, key=lambda r: _parse_version(r['tag_name']))
    installer_url = None
    for asset in target.get('assets', []):
        name = asset.get('name', '')
        if name.endswith('.exe') and 'browser_download_url' in asset:
            installer_url = asset['browser_download_url']
            break
    if installer_url is None:
        return None, None, []
    newer = [r for r in stable if _parse_version(r['tag_name']) > current_v]
    newer.sort(key=lambda r: _parse_version(r['tag_name']), reverse=True)
    changelog = [(r['tag_name'], r.get('body', '') or '') for r in newer]
    return target['tag_name'], installer_url, changelog
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./env/Scripts/python.exe -m pytest tests/test_update_checker_releases.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add swiss_windows_knife/components/update_checker.py tests/test_update_checker_releases.py
git commit -m "feat: add _releases_above helper for multi-version update math"
```

---

### Task 2: `UpdatePromptDialog` with scrollable changelog

**Files:**
- Create: `swiss_windows_knife/components/update_prompt_dialog.py`
- Test: `tests/test_update_prompt_dialog.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_update_prompt_dialog.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `QT_QPA_PLATFORM=offscreen ./env/Scripts/python.exe -m pytest tests/test_update_prompt_dialog.py -q`
Expected: FAIL — `ModuleNotFoundError: ...update_prompt_dialog`.

- [ ] **Step 3: Implement the dialog**

Create `swiss_windows_knife/components/update_prompt_dialog.py`:

```python
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QLabel, QTextBrowser, QVBoxLayout,
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `QT_QPA_PLATFORM=offscreen ./env/Scripts/python.exe -m pytest tests/test_update_prompt_dialog.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add swiss_windows_knife/components/update_prompt_dialog.py tests/test_update_prompt_dialog.py
git commit -m "feat: add UpdatePromptDialog with scrollable multi-version changelog"
```

---

### Task 3: `Updates` submenu with checkable `Automatic updates`

**Files:**
- Modify: `swiss_windows_knife/components/update_checker.py` (`retrieve_menus:128-132`, constants near line 22-24, imports line 9)
- Test: `tests/test_update_checker_menu.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_update_checker_menu.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `QT_QPA_PLATFORM=offscreen ./env/Scripts/python.exe -m pytest tests/test_update_checker_menu.py -q`
Expected: FAIL — the menu returns a bare action, not an `Updates` menu with a toggle.

- [ ] **Step 3: Implement the submenu**

In `update_checker.py`, add near the constants (after line 24):

```python
AUTO_UPDATE_KEY = 'update_automatic'
```

Change `CHECK_LABEL_IDLE` (line 23) to include an ellipsis:

```python
CHECK_LABEL_IDLE = 'Check for updates…'
```

Replace `retrieve_menus` (lines 128-132) with:

```python
    def retrieve_menus(self) -> list[QMenu | QAction]:
        menu = QMenu('Updates', self)

        self._check_action = QAction(CHECK_LABEL_IDLE, self)
        self._check_action.setEnabled(not self._busy)
        self._check_action.triggered.connect(
            lambda: self.check_updates(interactive=True))
        menu.addAction(self._check_action)

        auto_action = QAction('Automatic updates', self)
        auto_action.setCheckable(True)
        auto_action.setChecked(
            self.user_settings.get(AUTO_UPDATE_KEY, bool, False))
        auto_action.toggled.connect(self._on_auto_toggled)
        menu.addAction(auto_action)

        return [menu]

    def _on_auto_toggled(self, checked: bool) -> None:
        self.user_settings.set(AUTO_UPDATE_KEY, checked)
        logging.info("Automatic updates set to %s", checked)
```

`QMenu` and `QAction` are already imported (lines 8-9).

- [ ] **Step 4: Run tests to verify they pass**

Run: `QT_QPA_PLATFORM=offscreen ./env/Scripts/python.exe -m pytest tests/test_update_checker_menu.py -q`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add swiss_windows_knife/components/update_checker.py tests/test_update_checker_menu.py
git commit -m "feat: add Updates submenu with Automatic updates toggle"
```

---

### Task 4: Integrate — `/releases` fetch, 3-tuple result, auto/manual branch

This task flips the worker and handler together so the runtime stays coherent. It also adds `notification_requested` and rewires `_confirm_update` to the new dialog.

**Files:**
- Modify: `swiss_windows_knife/components/update_checker.py` (`_CheckThread.run:52-77`, class signal, `_on_check_finished:178-218`, `_confirm_update:227-246`, imports lines 9, 11)
- Modify: `tests/test_update_checker_workers.py` (result shape)
- Modify: `tests/test_update_checker_health.py` (result shape + branches)

- [ ] **Step 1: Update the worker tests to the new shape**

In `tests/test_update_checker_workers.py`, replace the two release-body tests (lines 37-70) with:

```python
def test_check_thread_emits_none_when_release_has_no_installer_asset(qtbot, check_thread):
    class _FakeResp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return [{"tag_name": "9.9.9", "assets": []}]

    with patch('swiss_windows_knife.components.update_checker.requests.get', return_value=_FakeResp()):
        args = _wait_result(qtbot, check_thread)
    assert args == [None]


def test_check_thread_emits_release_tuple_on_success(qtbot, check_thread):
    class _FakeResp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return [{
                "tag_name": "9.9.9",
                "body": "shiny notes",
                "assets": [
                    {"name": "irrelevant.zip"},
                    {"name": "Installer-9.9.9.exe",
                     "browser_download_url": "https://example/9.9.9.exe"},
                ],
            }]

    with patch('swiss_windows_knife.components.update_checker.requests.get', return_value=_FakeResp()):
        args = _wait_result(qtbot, check_thread)
    assert args == [("9.9.9", "https://example/9.9.9.exe", [("9.9.9", "shiny notes")])]
```

- [ ] **Step 2: Run worker tests to verify they fail**

Run: `QT_QPA_PLATFORM=offscreen ./env/Scripts/python.exe -m pytest tests/test_update_checker_workers.py -q`
Expected: FAIL — success test still gets the old 2-tuple; the no-installer test's dict (not list) no longer matches the new list-based code path once implemented (fails now on shape mismatch).

- [ ] **Step 3: Rewrite `_CheckThread.run` to fetch `/releases` and emit the triple**

Replace `_CheckThread.run` (lines 52-77) with:

```python
    def run(self) -> None:
        logging.info("Update-check worker started; fetching %s", RELEASES_URL)
        try:
            response = requests.get(
                RELEASES_URL, timeout=(CONNECT_TIMEOUT_S, READ_TIMEOUT_S),
            )
            logging.info("Update-check HTTP status: %s", response.status_code)
            response.raise_for_status()
            releases = response.json()

            target, installer_url, changelog = _releases_above(
                releases, APP_INFO.APP_VERSION)
            if target is None:
                logging.warning("No stable release with an installer asset")
                self.result_ready.emit(None)
                return

            self.result_ready.emit((target, installer_url, changelog))
        except Exception:
            logging.exception("Failed to query for updates")
            self.result_ready.emit(None)
```

- [ ] **Step 4: Run worker tests to verify they pass**

Run: `QT_QPA_PLATFORM=offscreen ./env/Scripts/python.exe -m pytest tests/test_update_checker_workers.py -q`
Expected: PASS (the exception tests, no-installer, and success test all pass).

- [ ] **Step 5: Add the signal, auto/manual branch, and `_start_download`**

In `update_checker.py`:

Add to the imports at line 11 (`from .update_prompt_dialog import UpdatePromptDialog`) and add `QDialog` to the `PySide6.QtWidgets` import (line 9); remove `QCheckBox` from that import (it moves into the dialog):

```python
from PySide6.QtWidgets import QDialog, QMenu, QMessageBox, QWidget
```
```python
from ..app_info import APP_INFO
from .update_prompt_dialog import UpdatePromptDialog
```

Add the signal inside `class UpdateChecker` (just below `display_name = "Auto-updater"`, line 109):

```python
    notification_requested = Signal(str, str)
```

Replace `_on_check_finished` (lines 178-218) with:

```python
    @Slot(object)
    def _on_check_finished(self, result) -> None:
        if not self._busy:
            logging.info("Ignoring stale update-check result (watchdog already fired)")
            return
        if self._check_action is not None:
            self._check_action.setText(CHECK_LABEL_IDLE)

        if result is None:
            if self._interactive:
                QMessageBox.warning(
                    self, 'Update check failed',
                    'Could not check for updates. See logs for details.')
            self._set_health(HealthState.WARNING, "Check failed")
            self._set_busy(False)
            return

        target, installer_url, changelog = result
        if _parse_version(target) <= _parse_version(APP_INFO.APP_VERSION):
            logging.info('No update is needed. Remote: %s, Local: %s',
                         target, APP_INFO.APP_VERSION)
            if self._interactive:
                QMessageBox.information(
                    self, 'No update available',
                    f'You are on the latest version ({APP_INFO.APP_VERSION}).')
            self._set_health(HealthState.OK, "Up to date")
            self._set_busy(False)
            return

        logging.info('Update available: %s -> %s', APP_INFO.APP_VERSION, target)
        self._set_health(HealthState.OK, f"Update available {target}")

        if self.user_settings.get(AUTO_UPDATE_KEY, bool, False):
            self.notification_requested.emit(
                APP_INFO.APP_NAME, f"Updating to {target}…")
            self._start_download(installer_url)
            return

        if not self._confirm_update(target, changelog):
            self._set_busy(False)
            return
        self._start_download(installer_url)

    def _start_download(self, installer_url: str) -> None:
        dest_dir = tempfile.mkdtemp(prefix='swk-update-')
        thread = _DownloadThread(installer_url, dest_dir, self)
        thread.result_ready.connect(self._on_download_finished)
        thread.finished.connect(thread.deleteLater)
        self._active_thread = thread
        thread.start()
```

Replace `_confirm_update` (lines 227-246) with:

```python
    def _confirm_update(self, target_version: str, changelog_entries) -> bool:
        skipped = self.user_settings.get(SKIP_VERSION_KEY, str, "")
        if skipped == target_version:
            logging.info("User previously chose to skip version %s", target_version)
            return False

        dialog = UpdatePromptDialog(target_version, changelog_entries, self)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        if not accepted and dialog.skip_checked():
            self.user_settings.set(SKIP_VERSION_KEY, target_version)
        return accepted
```

> Note: the old `_on_check_finished` body that inlined the `tempfile.mkdtemp` + `_DownloadThread` block (lines 213-218) is now fully replaced by `_start_download`; do not leave a duplicate.

- [ ] **Step 6: Update health tests to the new shape and add branch tests**

In `tests/test_update_checker_health.py`, change the two `_on_check_finished` calls to 3-tuples:
- line 41: `checker._on_check_finished(("1.0.0", "https://example/installer.exe", []))`
- line 55: `c._on_check_finished(("9.9.9", "https://example/installer.exe", [("9.9.9", "notes")]))`

Append these tests to the file:

```python
def test_auto_mode_skips_dialog_and_downloads(qtbot, fake_user_settings):
    from swiss_windows_knife.components.update_checker import UpdateChecker
    fake_user_settings.set('update_automatic', True)
    with patch.object(UpdateChecker, "check_updates"):
        c = UpdateChecker(parent=None)
        qtbot.addWidget(c)
    c._busy = True
    with patch("swiss_windows_knife.components.update_checker.APP_INFO") as app_info, \
         patch.object(c, "_confirm_update") as confirm, \
         patch.object(c, "_start_download") as start_dl:
        app_info.APP_NAME = "SWK"
        app_info.APP_VERSION = "1.0.0"
        with qtbot.waitSignal(c.notification_requested, timeout=500):
            c._on_check_finished(
                ("2.0.0", "https://example/2.0.0.exe", [("2.0.0", "notes")]))
    confirm.assert_not_called()
    start_dl.assert_called_once_with("https://example/2.0.0.exe")


def test_auto_mode_ignores_skip_version(qtbot, fake_user_settings):
    from swiss_windows_knife.components.update_checker import UpdateChecker
    fake_user_settings.set('update_automatic', True)
    fake_user_settings.set('update_skip_version', "2.0.0")
    with patch.object(UpdateChecker, "check_updates"):
        c = UpdateChecker(parent=None)
        qtbot.addWidget(c)
    c._busy = True
    with patch("swiss_windows_knife.components.update_checker.APP_INFO") as app_info, \
         patch.object(c, "_start_download") as start_dl:
        app_info.APP_NAME = "SWK"
        app_info.APP_VERSION = "1.0.0"
        c._on_check_finished(("2.0.0", "https://example/2.0.0.exe", []))
    start_dl.assert_called_once_with("https://example/2.0.0.exe")


def test_manual_mode_calls_dialog_and_downloads_on_accept(qtbot, fake_user_settings):
    from swiss_windows_knife.components.update_checker import UpdateChecker
    with patch.object(UpdateChecker, "check_updates"):
        c = UpdateChecker(parent=None)
        qtbot.addWidget(c)
    c._busy = True
    with patch("swiss_windows_knife.components.update_checker.APP_INFO") as app_info, \
         patch.object(c, "_confirm_update", return_value=True) as confirm, \
         patch.object(c, "_start_download") as start_dl:
        app_info.APP_VERSION = "1.0.0"
        c._on_check_finished(
            ("2.0.0", "https://example/2.0.0.exe", [("2.0.0", "n")]))
    confirm.assert_called_once_with("2.0.0", [("2.0.0", "n")])
    start_dl.assert_called_once_with("https://example/2.0.0.exe")


def test_confirm_update_skips_prompt_when_version_skipped(qtbot, fake_user_settings):
    from swiss_windows_knife.components.update_checker import UpdateChecker
    with patch.object(UpdateChecker, "check_updates"):
        c = UpdateChecker(parent=None)
        qtbot.addWidget(c)
    fake_user_settings.set('update_skip_version', "2.0.0")
    with patch("swiss_windows_knife.components.update_checker.UpdatePromptDialog") as D:
        result = c._confirm_update("2.0.0", [])
    assert result is False
    D.assert_not_called()


def test_confirm_update_stores_skip_on_decline_with_checkbox(qtbot, fake_user_settings):
    from PySide6.QtWidgets import QDialog
    from swiss_windows_knife.components.update_checker import UpdateChecker
    with patch.object(UpdateChecker, "check_updates"):
        c = UpdateChecker(parent=None)
        qtbot.addWidget(c)
    fake_dialog = MagicMock()
    fake_dialog.exec.return_value = QDialog.DialogCode.Rejected
    fake_dialog.skip_checked.return_value = True
    with patch("swiss_windows_knife.components.update_checker.UpdatePromptDialog",
               return_value=fake_dialog):
        result = c._confirm_update("2.0.0", [])
    assert result is False
    assert fake_user_settings.get('update_skip_version', str, "") == "2.0.0"
```

Add `MagicMock` to the imports at the top of `tests/test_update_checker_health.py` (line 1):

```python
from unittest.mock import MagicMock, patch
```

- [ ] **Step 7: Run the update-checker test suite**

Run: `QT_QPA_PLATFORM=offscreen ./env/Scripts/python.exe -m pytest tests/test_update_checker_health.py tests/test_update_checker_workers.py tests/test_update_checker_releases.py tests/test_update_checker_menu.py tests/test_update_prompt_dialog.py -q`
Expected: PASS (all).

- [ ] **Step 8: Commit**

```bash
git add swiss_windows_knife/components/update_checker.py tests/test_update_checker_workers.py tests/test_update_checker_health.py
git commit -m "feat: silent auto-update path and multi-version changelog prompt"
```

---

### Task 5: Relay `notification_requested` to the tray balloon

**Files:**
- Modify: `swiss_windows_knife/ui/tray_widget.py` (`update_checker` creation, lines 63-65; add slot)

- [ ] **Step 1: Wire the signal and add the slot**

In `tray_widget.py`, after the `update_checker` creation (lines 63-65), add the connection:

```python
        self.update_checker: UpdateChecker | None = (
            None if dev_mode else UpdateChecker(self)
        )
        if self.update_checker is not None:
            self.update_checker.notification_requested.connect(
                self._show_tray_message)
```

Add this slot to `TrayWidget` (place it next to `_refresh_tray_icon`, near line 91). Confirm `QSystemTrayIcon` is imported at the top of the file (it is used for `self._tray_icon`); reuse that import:

```python
    @Slot(str, str)
    def _show_tray_message(self, title: str, message: str) -> None:
        self._tray_icon.showMessage(
            title, message, QSystemTrayIcon.MessageIcon.Information)
```

`Slot` is already imported (used by `_refresh_tray_icon`). `self._tray_icon` is created later in `__init__` (line 67-71); the signal only fires during an async update check that starts after the event loop is running, so the icon always exists by emit time.

- [ ] **Step 2: Verify import + syntax**

Run: `./env/Scripts/python.exe -c "import swiss_windows_knife.ui.tray_widget"`
Expected: no output, exit 0.

- [ ] **Step 3: Run the full suite + ruff**

Run: `QT_QPA_PLATFORM=offscreen ./env/Scripts/python.exe -m pytest tests/ -q`
Expected: PASS (all).

Run: `./env/Scripts/python.exe -m ruff check swiss_windows_knife/ tests/`
Expected: `All checks passed!`

- [ ] **Step 4: Commit**

```bash
git add swiss_windows_knife/ui/tray_widget.py
git commit -m "feat: relay update notifications to a tray balloon"
```

> Testing note: the tray relay is a one-line signal connect plus a passthrough slot. Constructing `TrayWidget` in a unit test spins up every plugin and a live `QSystemTrayIcon`, which is heavy and flaky under offscreen Qt, so this wiring is verified live in Task 6 rather than with a fragile unit test. This is a deliberate, scoped exception — not blanket "no tests".

---

### Task 6: Manual verification in the running app

**Files:** none (runtime check).

- [ ] **Step 1: Restart the tray app**

Kill any running instance, then relaunch:

```bash
# PowerShell:
Get-Process | Where-Object { $_.Path -like "*swiss-windows-knife\env\Scripts\python.exe" } | Stop-Process -Force
./env/Scripts/python.exe -m swiss_windows_knife
```

- [ ] **Step 2: Verify the menu**

Open the tray menu → confirm an **Updates** submenu with **Check for updates…** and a checkable **Automatic updates** (unchecked by default). Toggle it on, reopen the menu, confirm it stays checked (persisted to registry `HKCU\Software\Swiss Windows Knife\UserSettings\update_automatic`).

- [ ] **Step 3: Verify the manual prompt**

With **Automatic updates** off, click **Check for updates…**. Because the local version is current, expect the "You are on the latest version" info box (interactive). Check the Logs window for `Update-check HTTP status: 200` and no exceptions. (If a newer stable release exists, confirm the changelog dialog renders release notes and the skip checkbox.)

- [ ] **Step 4: Confirm no errors in logs**

In the Logs window, confirm no `Failed to query for updates` traceback and that toggling produced `Automatic updates set to True/False`.

- [ ] **Step 5: Final commit if any fixups were needed**

If Steps 2-4 required code changes, commit them with an appropriate `fix:`/`feat:` message. Otherwise nothing to commit.

---

## Self-Review

**Spec coverage:**
- Automatic updates toggle → Task 3 (menu) + Task 4 (branch). ✓
- Default off → Task 3 (`get(..., bool, False)`), Task 6 verification. ✓
- Silent install + tray notification → Task 4 (auto branch, `notification_requested`) + Task 5 (relay). ✓
- Multi-version changelog, newest-first → Task 1 (`_releases_above`) + Task 2 (dialog render) + Task 4 (flow). ✓
- Per-version skip retained, manual-only → Task 4 (`_confirm_update`, auto branch bypasses it). ✓
- Prereleases/drafts excluded → Task 1 (filter) + test. ✓
- `/releases` endpoint → Task 1 (`RELEASES_URL`) + Task 4 (worker). ✓

**Placeholder scan:** No TBD/TODO; every code step has complete code. ✓

**Type consistency:** `_releases_above` returns `(target, installer_url, changelog)` everywhere it appears (Task 1 def, Task 4 worker, tests). `_confirm_update(target_version, changelog_entries)` matches its call in `_on_check_finished` and the tests. `notification_requested = Signal(str, str)` emitted with two strings and relayed by a `(str, str)` slot. `AUTO_UPDATE_KEY`/`SKIP_VERSION_KEY` used consistently. ✓
