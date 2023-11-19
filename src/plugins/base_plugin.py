from typing import Optional, List
from PySide6 import QtCore

class BasePlugin(QtCore.QObject):

    def __init__(self, depends_on = [], parent: Optional[QtCore.QObject] = None) -> None:
        super().__init__(parent)

        self.enabled = True
        self.depends_on = depends_on

    def change_status(self, enabled: bool):
        self.enabled = enabled

    def is_enabled(self):
        return all(plugin.is_enabled() for plugin in self.depends_on) and self.enabled
