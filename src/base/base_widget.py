from PySide6.QtWidgets import QWidget, QMenu
from PySide6.QtGui import QAction
import logging


class BaseWidget(QWidget):

    display_name: str = ""

    def __init__(self, parent: QWidget, is_toggleable: bool = True, is_enabled: bool = True) -> None:
        super().__init__(parent)
        self._is_toggleable = is_toggleable
        self._is_enabled = is_enabled

    def get_display_name(self) -> str:
        return self.display_name or self.__class__.__name__

    def set_enabled(self, enabled: bool) -> None:
        if self._is_enabled == enabled:
            return
        self._is_enabled = enabled
        logging.info(f'Plugin {self.__class__.__name__} is enabled: {enabled}')
        self.status_changed(enabled)

    def is_enabled(self) -> bool:
        return self._is_enabled

    def is_toggleable(self) -> bool:
        return self._is_toggleable

    def retrieve_menus(self) -> list[QMenu | QAction]:
        return []

    def status_changed(self, status: bool) -> None:
        return None
