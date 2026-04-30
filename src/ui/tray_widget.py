import sys

from PySide6.QtCore import QCoreApplication, QObject, Slot
from PySide6.QtGui import QAction, QActionGroup, QIcon
from PySide6.QtWidgets import QMenu, QMessageBox, QSystemTrayIcon, QWidget

from .. import resources  # noqa: F401,E261
from ..app_info import APP_INFO
from ..base.base_widget import BaseWidget
from ..components.update_checker import UpdateChecker
from ..plugins.device_display_mapper.device_display_mapper_plugin import DeviceDisplayMapperPlugin
from ..plugins.display_image_tuner.image_tuner_plugin import DisplayImageTunerPlugin
from ..plugins.home_assistant_mqtt_pub.home_assistant_mqtt_pub_plugin import HomeAssistantMqttPubPlugin
from .about_dialog import AboutDialog
from .configuration_dialog import ConfigurationDialog
from .tray_logger import TrayLogger


class TrayWidget(QWidget):

    def __init__(self, dev_mode: bool = False, parent: QObject | None = None) -> None:
        super().__init__(parent=None)

        if not QSystemTrayIcon.isSystemTrayAvailable():
            QMessageBox.critical(self, "Systray", "I couldn't detect any system tray on this system.")
            sys.exit(1)

        self._config_dialog: ConfigurationDialog | None = None

        # Dialogs use `parent=None` so Windows treats them as top-level
        # owned-by-nothing — required for them to get their own taskbar
        # entry and the app icon. With a parent, the OS treats them as
        # owned by the (hidden) TrayWidget and hides them from the taskbar.
        self.logger_window = TrayLogger(None)
        self.logger_window.hide()

        self.child_components: list[BaseWidget] = [
            DisplayImageTunerPlugin(self),
            DeviceDisplayMapperPlugin(self),
            HomeAssistantMqttPubPlugin(self),
        ]

        if not dev_mode:
            self.child_components.append(UpdateChecker(self))

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
            action = QAction(child_component.get_display_name(), self)
            action.setCheckable(True)
            action.setChecked(child_component.is_enabled())
            if child_component.is_toggleable():
                action.toggled.connect(child_component.set_enabled)
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

        config_action = QAction('Configuration...', self)
        config_action.triggered.connect(self.open_configuration_dialog)
        menu.addAction(config_action)
        menu.addSeparator()

        logs_action = QAction('View Logs', self)
        logs_action.triggered.connect(self.open_logs_window)
        menu.addAction(logs_action)

        about_action = QAction('About...', self)
        about_action.triggered.connect(self.open_about_dialog)
        menu.addAction(about_action)
        menu.addSeparator()
        quit_action = QAction('Quit', self)
        quit_action.triggered.connect(self.close_slot)
        menu.addAction(quit_action)
        return menu

    @Slot()
    def open_configuration_dialog(self) -> None:
        if self._config_dialog is not None:
            self._config_dialog.raise_()
            self._config_dialog.activateWindow()
            return
        self._config_dialog = ConfigurationDialog(None, self.child_components)
        try:
            self._config_dialog.exec()
        finally:
            self._config_dialog = None

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

    @Slot()
    def open_about_dialog(self) -> None:
        AboutDialog(None).exec()
