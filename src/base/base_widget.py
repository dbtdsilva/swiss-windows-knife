from PySide6.QtWidgets import QWidget, QMenu
import logging


class BaseWidget(QWidget):

    def __init__(self, parent: QWidget, depends_on=[], is_toggleable=True) -> None:
        super().__init__(parent)
        self.enabled = True
        self.depends_on = depends_on
        self._is_toggleable = is_toggleable

    def toggle_status(self):
        self.enabled = not self.enabled
        logging.info(f'Plugin {self.__class__.__name__} is enabled: {self.enabled}')

    def is_enabled(self):
        return all(plugin.is_enabled() for plugin in self.depends_on) and self.enabled

    def is_toggleable(self):
        return self._is_toggleable

    def retrieve_menus(self) -> list[QMenu]:
        return []
