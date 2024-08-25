from typing import Optional

from PySide6.QtWidgets import QWidget, QMessageBox, QCheckBox
from PySide6.QtCore import QTimer

from ..app_info import APP_INFO
from ..plugins.base_plugin import BasePlugin
from ..base.user_settings import UserSettings

import requests
import os
import subprocess
import tempfile
import sys
import logging


class UpdateChecker(BasePlugin):

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)

        self.user_settings = UserSettings.instance()

        self.timer = QTimer()
        self.timer.timeout.connect(self.check_updates)
        self.timer.start(1000 * 60 * 30)
        self.check_updates()

    def check_updates(self):
        latest_version_url = 'https://api.github.com/repos/dbtdsilva/monitor-controller-kvm/releases/latest'
        current_version = APP_INFO.APP_VERSION

        response = requests.get(latest_version_url)

        if response.status_code != 200:
            logging.warn(f'Failed to retrieve version to update: {response.text}')
            return

        installer_url = self.retrieve_installer_remote_url(response.json())
        if installer_url is None:
            logging.warn(f'Failed to retrieve installer url from response: {response.json()}')
            return

        remote_version = response.json()['tag_name']
        if current_version >= remote_version:
            return

        logging.info(f'Application will retrieve user to update version from {current_version} to {remote_version}')
        if not self.update_confirmation():
            return
        self.update_application(installer_url)

    def retrieve_installer_remote_url(self, response):
        if 'assets' not in response:
            return None

        for asset in response['assets']:
            if 'name' not in asset or not asset['name'].endswith('.exe'):
                continue

            if 'browser_download_url' in asset:
                return asset['browser_download_url']
        return None

    def update_confirmation(self):
        last_option = self.get_last_remember_selection()
        if last_option is not None:
            return last_option

        # Create a message box
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setWindowTitle('Update Available')
        msg_box.setText('A new update is available. Would you like to install it now?')

        # Add buttons for user response
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.Yes)

        remember_option_checkbox = QCheckBox('Remember my selection')
        msg_box.setCheckBox(remember_option_checkbox)

        # Show the message box and get the user's response
        response = msg_box.exec()

        update_accepted = response == QMessageBox.StandardButton.Yes
        remember_selection = remember_option_checkbox.isChecked()
        if remember_selection:
            self.set_last_remember_selection(update_accepted)

        return update_accepted

    def get_last_remember_selection(self) -> bool | None:
        if not self.user_settings.has_key('update_last_remember_selection'):
            return None
        return bool(self.user_settings.get('update_last_remember_selection'))

    def set_last_remember_selection(self, value: bool) -> None:
        self.user_settings.set('update_last_remember_selection', int(value))

    def update_application(self, url):
        temp_dir = tempfile.TemporaryDirectory()
        installer_file = self.download_file(url, temp_dir)
        installed = self.run_installer(installer_file)
        temp_dir.cleanup()

        if installed:
            self.close_application_and_run()

    def close_application_and_run(self):
        # TODO: Properly shutdown QtApplication instead of forcing
        sys.exit(0)

    def download_file(self, url: str, destination: tempfile.TemporaryDirectory) -> Optional[str]:
        temp_file_path = os.path.join(destination.name, os.path.basename(url))
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(temp_file_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        logging.info(f'Downloaded file saved as: {temp_file_path}')
        return temp_file_path

    def run_installer(self, installer_file):
        if not installer_file or not os.path.exists(installer_file):
            logging.error(f'Installer not found at: {installer_file}')
            return False

        result = subprocess.run([installer_file, '/silent'], check=True)

        if result.returncode != 0:
            logging.error(f'Installer failed with return code: {result.returncode}')
            return False

        logging.info('Installer successfully updated application')
        return True
