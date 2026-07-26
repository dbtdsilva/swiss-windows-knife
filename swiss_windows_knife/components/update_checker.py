import logging
import os
import subprocess
import tempfile

import requests
from PySide6.QtCore import QCoreApplication, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QDialog, QMenu, QMessageBox, QWidget

from ..app_info import APP_INFO
from ..base.health import HealthState
from ..base.health_reporter import HealthReporter
from ..base.user_settings import UserSettings
from .update_prompt_dialog import UpdatePromptDialog

RELEASES_URL = 'https://api.github.com/repos/dbtdsilva/swiss-windows-knife/releases'
CHECK_INTERVAL_MS = 1000 * 30 * 60
CONNECT_TIMEOUT_S = 5
READ_TIMEOUT_S = 15
DOWNLOAD_TIMEOUT_S = 120
WATCHDOG_MS = 30_000
SKIP_VERSION_KEY = 'update_skip_version'
CHECK_LABEL_IDLE = 'Check for updates…'
CHECK_LABEL_CHECKING = 'Checking…'
AUTO_UPDATE_KEY = 'update_automatic'


def _parse_version(text: str) -> tuple[int, ...]:
    parts = text.lstrip('v').split('.')
    out: list[int] = []
    for p in parts:
        try:
            out.append(int(p))
        except ValueError:
            break
    return tuple(out)


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


class _CheckThread(QThread):
    """Fetches the latest release metadata from GitHub on its own thread.

    Subclasses `QThread` directly (rather than the worker-as-QObject +
    `moveToThread` + `started.connect(run)` pattern) because, in the frozen
    cx_Freeze build, the latter pattern was reproducibly failing to invoke
    the worker's `run()` slot — the thread started, but the started→run
    signal-slot connection never fired. Putting the work in `QThread.run`
    bypasses that connection entirely; the thread's main function IS the
    worker code.
    """

    result_ready = Signal(object)

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


class _DownloadThread(QThread):
    """Streams the installer to disk on its own thread. Same QThread-subclass
    rationale as `_CheckThread`."""

    result_ready = Signal(object)

    def __init__(self, url: str, dest_dir: str, parent=None) -> None:
        super().__init__(parent)
        self._url = url
        self._dest_dir = dest_dir

    def run(self) -> None:
        path = os.path.join(self._dest_dir, os.path.basename(self._url))
        logging.info("Update-download worker started; fetching %s", self._url)
        try:
            with requests.get(self._url, stream=True, timeout=DOWNLOAD_TIMEOUT_S) as r:
                r.raise_for_status()
                with open(path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            logging.info(f"Downloaded installer to {path}")
            self.result_ready.emit(path)
        except Exception:
            logging.exception("Failed to download installer")
            self.result_ready.emit(None)


class UpdateChecker(HealthReporter):

    display_name = "Auto-updater"

    notification_requested = Signal(str, str)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)

        self.user_settings = UserSettings.instance()
        self._busy = False
        self._interactive = False
        self._check_action: QAction | None = None
        self._active_thread: QThread | None = None

        self._set_health(HealthState.OK, "Checking…")

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_updates)
        self.timer.start(CHECK_INTERVAL_MS)

        QTimer.singleShot(0, self.check_updates)

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

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        if self._check_action is not None:
            self._check_action.setEnabled(not busy)

    def check_updates(self, interactive: bool = False) -> None:
        if self._busy:
            return
        self._interactive = interactive
        self._set_busy(True)
        if interactive and self._check_action is not None:
            self._check_action.setText(CHECK_LABEL_CHECKING)
        logging.info("Spawning update-check worker (interactive=%s)", interactive)
        thread = _CheckThread(self)
        thread.result_ready.connect(self._on_check_finished)
        thread.finished.connect(thread.deleteLater)
        self._active_thread = thread
        thread.start()
        QTimer.singleShot(WATCHDOG_MS, self._check_watchdog)

    def _check_watchdog(self) -> None:
        # If the worker thread wedged (e.g. requests.get blocked on a
        # network path that ignores its own timeout), `_busy` would stay
        # True forever and the menu item would stay greyed out. Force a
        # recovery so the user can try again instead of having to restart
        # the app. A late-returning orphan worker is harmless — the
        # stale-result guard in `_on_check_finished` ignores its result.
        if not self._busy:
            return
        logging.warning(
            "Update check did not finish within %s ms; forcing recovery.",
            WATCHDOG_MS,
        )
        if self._check_action is not None:
            self._check_action.setText(CHECK_LABEL_IDLE)
        self._set_busy(False)
        self._set_health(HealthState.WARNING, "Check timed out")
        if self._interactive:
            QMessageBox.warning(
                self, 'Update check timed out',
                f'No response within {WATCHDOG_MS // 1000} seconds. '
                'See logs for details.',
            )

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

    @Slot(object)
    def _on_download_finished(self, path) -> None:
        self._set_busy(False)
        if path is None:
            return
        self._launch_installer(path)

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

    def _launch_installer(self, installer_file: str) -> None:
        if not os.path.exists(installer_file):
            logging.error(f'Installer not found at: {installer_file}')
            return

        logging.info(f'Launching installer {installer_file} and quitting application')
        subprocess.Popen(
            [installer_file, '/silent', '/mergetasks=startafterinstall'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        QCoreApplication.quit()

    def closeEvent(self, event):
        self.timer.stop()
        event.accept()
