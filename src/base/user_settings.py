from PySide6.QtCore import QSettings
import logging

import threading

from ..app_info import APP_INFO


class UserSettings:

    logger = logging.getLogger(__name__)

    _instance = None
    _lock = threading.Lock()

    @classmethod
    def instance(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
        return cls._instance

    def __init__(self):
        if UserSettings._instance is not None:
            raise Exception("This class is a singleton, it cannot be instantiated.")
        else:
            UserSettings._instance = self

        self._settings = QSettings(APP_INFO.APP_NAME, 'UserSettings')
        logging.info(f"UserSettings loaded from {self._settings.fileName()}")

    def get(self, key) -> object:
        return self._settings.value(key)

    def has_key(self, key) -> bool:
        return self._settings.contains(key)

    def set(self, key, value) -> None:
        logging.info(f'Setting {key} to {value}')
        self._settings.setValue(key, value)
