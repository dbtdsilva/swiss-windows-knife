from PySide6.QtWidgets import QWidget, QMenu
import logging


class BaseWidget(QWidget):

    def __init__(self, parent: QWidget, is_toggleable=True, is_enabled=True) -> None:
        super().__init__(parent)
        self._is_toggleable = is_toggleable
        self._is_enabled = is_enabled

    def toggle_status(self):
        self._is_enabled = not self._is_enabled
        self.status_changed(self._is_enabled)
        logging.info(f'Plugin {self.__class__.__name__} is enabled: {self._is_enabled}')

    def is_enabled(self):
        return self._is_enabled

    def is_toggleable(self):
        return self._is_toggleable

    def retrieve_menus(self) -> list[QMenu]:
        return []

    def status_changed(self, status: bool) -> None:
        return None
