from typing import Optional
from PySide6.QtCore import Slot, QCoreApplication, QObject
from PySide6.QtGui import QAction, QIcon, QActionGroup
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget, QMessageBox

from ..components.update_checker import UpdateChecker
from ..plugins.base_plugin import BasePlugin
from ..plugins.image_tuner_plugin import ImageTunerPlugin
from ..plugins.device_display_mapper_plugin import DeviceDisplayMapperPlugin
from ..plugins.sun_strenght_plugin import SunStrenghtPlugin
from .. import resources # noqa: F401,E261

from ..app_info import APP_INFO
from ..plugins.device_listener import DeviceListener
from .tray_logger import TrayLogger
import sys


class TrayWidget(QWidget):

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent=None)

        if not QSystemTrayIcon.isSystemTrayAvailable():
            QMessageBox.critical(self, "Systray", "I couldn't detect any system tray on this system.")
            sys.exit(1)

        self.logger_window = TrayLogger(self)
        self.logger_window.hide()

        self.plugins: list[BasePlugin] = [
            ImageTunerPlugin(self, SunStrenghtPlugin(self)),
            DeviceDisplayMapperPlugin(self, DeviceListener(self)),
            UpdateChecker(self)
        ]

        self._tray_icon = QSystemTrayIcon(parent=parent)
        self._tray_icon.setContextMenu(self.createMainMenu())
        self._tray_icon.setToolTip(APP_INFO.APP_NAME)
        self._tray_icon.setIcon(QIcon(":/icons/coat-of-arms.ico"))
        self._tray_icon.show()

    def createMenu(self, menu) -> QMenu:
        tray_icon_menu = QMenu(self)
        group = QActionGroup(self)
        group.setExclusive(True)
        for title, trigger, checkable in menu:
            if title is None:
                tray_icon_menu.addSeparator()
            elif type(trigger) is not list:
                action = QAction(title, self)
                action.triggered.connect(trigger)
                action.setCheckable(checkable)
                group.addAction(action)
                tray_icon_menu.addAction(action)
            else:
                sub_menu = self.createMenu(trigger)
                sub_menu.setTitle(title)
                tray_icon_menu.addMenu(sub_menu)
        return tray_icon_menu

    def createPluginsMenu(self):
        menu = QMenu('Plugins', self)
        for plugin in self.plugins:
            action = QAction(plugin.__class__.__name__, self)
            action.setCheckable(True)
            action.triggered.connect(plugin.toggle_status)
            if plugin.is_enabled():
                action.setChecked(True)
            menu.addAction(action)
        return menu

    def createMainMenu(self) -> QMenu:
        menu = QMenu(self)
        menu.addMenu(self.createPluginsMenu())
        menu.addSeparator()

        for plugin in self.plugins:
            for plugin_menu in plugin.retrieve_menus():
                menu.addMenu(plugin_menu)
        menu.addSeparator()

        logs_action = QAction('View logs', self)
        logs_action.triggered.connect(self.open_logs_window)
        menu.addAction(logs_action)
        menu.addSeparator()
        quit_action = QAction('Quit', self)
        quit_action.triggered.connect(self.close_slot)
        menu.addAction(quit_action)
        return menu

    @Slot()
    def close_slot(self):
        self.close()

    def closeEvent(self, event):
        for plugin in self.plugins:
            plugin.close()
        QCoreApplication.exit()

    @Slot()
    def open_logs_window(self):
        self.logger_window.show()
