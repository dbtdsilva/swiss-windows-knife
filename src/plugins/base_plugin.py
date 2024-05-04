from typing import Optional
from PySide6 import QtCore
import logging


class BasePlugin(QtCore.QObject):

    def __init__(self, depends_on=[], parent: Optional[QtCore.QObject] = None) -> None:
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)

        self.enabled = True
        self.depends_on = depends_on

    def toggle_status(self):
        self.enabled = not self.enabled
        logging.info(f'Plugin {self.__class__.__name__} is enabled: {self.enabled}')

    def is_enabled(self):
        return all(plugin.is_enabled() for plugin in self.depends_on) and self.enabled
