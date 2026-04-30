import logging
import sys

from PySide6.QtCore import QCoreApplication, QObject, Slot
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QMessageBox, QSystemTrayIcon, QWidget

from .. import resources  # noqa: F401,E261
from ..app_info import APP_INFO
from ..base.base_widget import BaseWidget
from ..base.health import HealthReport, HealthState
from ..components.update_checker import UpdateChecker
from ..plugins.device_display_mapper.device_display_mapper_plugin import DeviceDisplayMapperPlugin
from ..plugins.display_image_tuner.image_tuner_plugin import DisplayImageTunerPlugin
from ..plugins.home_assistant_mqtt_pub.home_assistant_mqtt_pub_plugin import HomeAssistantMqttPubPlugin
from .about_dialog import AboutDialog
from .configuration_dialog import ConfigurationDialog
from .health_icons import icon_for_state, tray_icon_for_state
from .tray_logger import TrayLogger


def aggregate_health(reports: list[HealthReport]) -> tuple[HealthState, str]:
    """Compute (worst-state, summary-text) for the tray top line.

    Reports in DISABLED state are ignored entirely. When no plugins are
    in WARNING or ERROR, the summary is "Health: All OK"; otherwise it's
    "Health: N warning(s), M error(s)".
    """
    n_warning = sum(1 for r in reports if r.state is HealthState.WARNING)
    n_error = sum(1 for r in reports if r.state is HealthState.ERROR)
    if n_error > 0:
        return HealthState.ERROR, f"Health: {n_warning} warning(s), {n_error} error(s)"
    if n_warning > 0:
        return HealthState.WARNING, f"Health: {n_warning} warning(s), {n_error} error(s)"
    return HealthState.OK, "Health: All OK"


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
        self._wire_health_signals()
        self._refresh_tray_icon()

    def createMainMenu(self) -> QMenu:
        menu = QMenu(self)
        menu.aboutToShow.connect(lambda m=menu: self._populate_main_menu(m))
        return menu

    def _wire_health_signals(self) -> None:
        for plugin in self.child_components:
            plugin.health_changed.connect(self._refresh_tray_icon)

    @Slot()
    def _refresh_tray_icon(self) -> None:
        reports: list[HealthReport] = []
        for plugin in self.child_components:
            try:
                reports.append(plugin.health())
            except Exception:
                logging.exception("plugin %s health() raised", plugin.__class__.__name__)
                reports.append(HealthReport(HealthState.WARNING, "health() failed"))
        worst_state, _ = aggregate_health(reports)
        self._tray_icon.setIcon(tray_icon_for_state(worst_state))

    def _populate_main_menu(self, menu: QMenu) -> None:
        menu.clear()

        reports: list[tuple[BaseWidget, HealthReport]] = []
        for plugin in self.child_components:
            try:
                reports.append((plugin, plugin.health()))
            except Exception:
                logging.exception("plugin %s health() raised", plugin.__class__.__name__)
                reports.append((plugin, HealthReport(HealthState.WARNING, "health() failed")))

        worst_state, summary_text = aggregate_health([r for _, r in reports])
        health_submenu = QMenu(summary_text, menu)
        health_submenu.setIcon(icon_for_state(worst_state))
        for plugin, report in reports:
            row = QAction(f"{plugin.get_display_name()} — {report.message}", self)
            row.setIcon(icon_for_state(report.state))
            row.setEnabled(False)
            health_submenu.addAction(row)
        menu.addMenu(health_submenu)
        menu.addSeparator()

        for plugin, _ in reports:
            if plugin.is_toggleable() and not plugin.is_enabled():
                continue
            for action in plugin.retrieve_menus():
                if isinstance(action, QMenu):
                    menu.addMenu(action)
                elif isinstance(action, QAction):
                    menu.addAction(action)
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
