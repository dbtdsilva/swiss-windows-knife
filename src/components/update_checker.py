import logging
import os
import subprocess
import tempfile
from collections.abc import Callable

import requests
from PySide6.QtCore import QCoreApplication, QObject, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QCheckBox, QMenu, QMessageBox, QWidget

from ..app_info import APP_INFO
from ..base.base_widget import BaseWidget
from ..base.user_settings import UserSettings

LATEST_RELEASE_URL = 'https://api.github.com/repos/dbtdsilva/swiss-windows-knife/releases/latest'
CHECK_INTERVAL_MS = 1000 * 30 * 60
NETWORK_TIMEOUT_S = 15
DOWNLOAD_TIMEOUT_S = 120
SKIP_VERSION_KEY = 'update_skip_version'
CHECK_LABEL_IDLE = 'Check for updates...'
CHECK_LABEL_CHECKING = 'Checking…'


def _parse_version(text: str) -> tuple[int, ...]:
    parts = text.lstrip('v').split('.')
    out: list[int] = []
    for p in parts:
        try:
            out.append(int(p))
        except ValueError:
            break
    return tuple(out)


class _CheckWorker(QObject):
    finished = Signal(object)

    @Slot()
    def run(self) -> None:
        # `finished` MUST be emitted on every exit path so that the caller's
        # `_busy` flag is cleared. We catch a broad Exception (rather than only
        # `requests.RequestException` / `ValueError`) because frozen builds
        # have surfaced unexpected error types from inside requests / urllib3
        # / SSL — when one escaped this method, the worker thread died
        # without emitting `finished`, leaving subsequent clicks silently
        # no-oping for the lifetime of the process.
        try:
            response = requests.get(LATEST_RELEASE_URL, timeout=NETWORK_TIMEOUT_S)
            response.raise_for_status()
            data = response.json()

            installer_url: str | None = None
            for asset in data.get('assets', []):
                name = asset.get('name', '')
                if name.endswith('.exe') and 'browser_download_url' in asset:
                    installer_url = asset['browser_download_url']
                    break

            if installer_url is None or 'tag_name' not in data:
                logging.warning("No installer asset in latest release")
                self.finished.emit(None)
                return

            self.finished.emit((data['tag_name'], installer_url))
        except Exception:
            logging.exception("Failed to query for updates")
            self.finished.emit(None)


class _DownloadWorker(QObject):
    finished = Signal(object)

    def __init__(self, url: str, dest_dir: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._url = url
        self._dest_dir = dest_dir

    @Slot()
    def run(self) -> None:
        path = os.path.join(self._dest_dir, os.path.basename(self._url))
        try:
            with requests.get(self._url, stream=True, timeout=DOWNLOAD_TIMEOUT_S) as r:
                r.raise_for_status()
                with open(path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
            logging.info(f"Downloaded installer to {path}")
            self.finished.emit(path)
        except Exception:
            # Same defensive-broad-except rationale as `_CheckWorker.run`.
            logging.exception("Failed to download installer")
            self.finished.emit(None)


class UpdateChecker(BaseWidget):

    display_name = "Auto-updater"

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent, is_toggleable=False)

        self.user_settings = UserSettings.instance()
        self._busy = False
        self._interactive = False
        self._check_action: QAction | None = None

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_updates)
        self.timer.start(CHECK_INTERVAL_MS)

        QTimer.singleShot(0, self.check_updates)

    def retrieve_menus(self) -> list[QMenu | QAction]:
        self._check_action = QAction(CHECK_LABEL_IDLE, self)
        self._check_action.setEnabled(not self._busy)
        self._check_action.triggered.connect(lambda: self.check_updates(interactive=True))
        return [self._check_action]

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
        self._spawn_worker(_CheckWorker(), self._on_check_finished)

    def _spawn_worker(self, worker: QObject, on_finished: Callable[[object], None]) -> None:
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)  # type: ignore[attr-defined]
        worker.finished.connect(on_finished)  # type: ignore[attr-defined]
        worker.finished.connect(thread.quit)  # type: ignore[attr-defined]
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.start()

    @Slot(object)
    def _on_check_finished(self, result) -> None:
        if self._check_action is not None:
            self._check_action.setText(CHECK_LABEL_IDLE)

        if result is None:
            if self._interactive:
                QMessageBox.warning(
                    self, 'Update check failed',
                    'Could not check for updates. See logs for details.')
            self._set_busy(False)
            return
        remote_version, installer_url = result
        if _parse_version(remote_version) <= _parse_version(APP_INFO.APP_VERSION):
            logging.info(f'No update is needed. Remote: {remote_version}, Local: {APP_INFO.APP_VERSION}')
            if self._interactive:
                QMessageBox.information(
                    self, 'No update available',
                    f'You are on the latest version ({APP_INFO.APP_VERSION}).')
            self._set_busy(False)
            return

        logging.info(f'Update available: {APP_INFO.APP_VERSION} -> {remote_version}')
        if not self._confirm_update(remote_version):
            self._set_busy(False)
            return

        dest_dir = tempfile.mkdtemp(prefix='swk-update-')
        self._spawn_worker(_DownloadWorker(installer_url, dest_dir), self._on_download_finished)

    @Slot(object)
    def _on_download_finished(self, path) -> None:
        self._set_busy(False)
        if path is None:
            return
        self._launch_installer(path)

    def _confirm_update(self, remote_version: str) -> bool:
        skipped = self.user_settings.get(SKIP_VERSION_KEY)
        if skipped is not None and str(skipped) == remote_version:
            logging.info(f"User previously chose to skip version {remote_version}")
            return False

        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setWindowTitle('Update Available')
        msg_box.setText(f'Version {remote_version} is available. Install now?')
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.Yes)

        skip_checkbox = QCheckBox(f"Don't ask again for version {remote_version}")
        msg_box.setCheckBox(skip_checkbox)

        accepted = msg_box.exec() == QMessageBox.StandardButton.Yes
        if not accepted and skip_checkbox.isChecked():
            self.user_settings.set(SKIP_VERSION_KEY, remote_version)
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
