from typing import Optional
from PySide6.QtCore import Slot, QCoreApplication, QObject
from PySide6.QtGui import QAction, QIcon, QActionGroup
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget, QMessageBox

from ..components.update_checker import UpdateChecker
from ..base.base_widget import BaseWidget
from ..plugins.display_image_tuner.image_tuner_plugin import DisplayImagePlugin
from ..plugins.device_display_mapper.device_display_mapper_plugin import DeviceDisplayMapperPlugin
from ..plugins.home_assistant_mqtt_pub.home_assistant_mqtt_pub_plugin import HomeAssistantMqttPubPlugin
from .. import resources # noqa: F401,E261

from ..app_info import APP_INFO
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

        self.child_components: list[BaseWidget] = [
            DisplayImagePlugin(self),
            DeviceDisplayMapperPlugin(self),
            HomeAssistantMqttPubPlugin(self),
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
        for child_component in self.child_components:
            action = QAction(child_component.__class__.__name__, self)

            action.setCheckable(True)
            if child_component.is_enabled():
                action.setChecked(True)

            toggleable = child_component.is_toggleable()
            if toggleable:
                action.triggered.connect(child_component.toggle_status)
            else:
                action.setDisabled(True)

            menu.addAction(action)
        return menu

    def createMainMenu(self) -> QMenu:
        menu = QMenu(self)
        menu.addMenu(self.createPluginsMenu())
        menu.addSeparator()

        for plugin in self.child_components:
            for plugin_menu_action in plugin.retrieve_menus():
                if isinstance(plugin_menu_action, QMenu):
                    menu.addMenu(plugin_menu_action)
                elif isinstance(plugin_menu_action, QAction):
                    menu.addAction(plugin_menu_action)
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
        for child_component in self.child_components:
            child_component.close()
        QCoreApplication.exit()

    @Slot()
    def open_logs_window(self):
        self.logger_window.show()
