from operator import truediv
from PySide6.QtCore import Slot, QCoreApplication
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (QDialog, QMenu, QSystemTrayIcon, QVBoxLayout)

import rc_systray


class Window(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self._minimize_action = QAction()
        self._maximize_action = QAction()
        self._restore_action = QAction()
        self._quit_action = QAction()

        self._tray_icon = QSystemTrayIcon()
        self._tray_icon_menu = QMenu()

        self.create_actions()
        self.create_tray_icon()

        self._tray_icon.activated.connect(self.icon_activated)

        self._main_layout = QVBoxLayout()
        self.setLayout(self._main_layout)

        self.setWindowTitle("Systray")
        self.setWindowIcon(QIcon(":/images/heart.png"))
        self.resize(400, 300)

    def setVisible(self, visible):
        self._minimize_action.setEnabled(visible)
        self._maximize_action.setEnabled(not self.isMaximized())
        self._restore_action.setEnabled(self.isMaximized() or not visible)
        super().setVisible(visible)

    def closeEvent(self, event):
        if not event.spontaneous() or not self.isVisible():
            return
        self.hide()
        event.ignore()

    @Slot(str)
    def icon_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            pass
        if reason == QSystemTrayIcon.DoubleClick:
            self.setVisible(not self.isVisible())
        if reason == QSystemTrayIcon.MiddleClick:
            self.middle_click()

    @Slot()
    def middle_click(self):
        pass

    def create_actions(self):
        self._minimize_action = QAction("Minimize", self)
        self._minimize_action.triggered.connect(self.hide)

        self._maximize_action = QAction("Maximize", self)
        self._maximize_action.triggered.connect(self.showMaximized)

        self._restore_action = QAction("Restore", self)
        self._restore_action.triggered.connect(self.showNormal)

        self._quit_action = QAction("Quit", self)
        self._quit_action.triggered.connect(QCoreApplication.quit)

    def create_tray_icon(self):
        self._tray_icon_menu = QMenu(self)
        self._tray_icon_menu.addAction(self._minimize_action)
        self._tray_icon_menu.addAction(self._maximize_action)
        self._tray_icon_menu.addAction(self._restore_action)
        self._tray_icon_menu.addSeparator()
        self._tray_icon_menu.addAction(self._quit_action)

        self._tray_icon = QSystemTrayIcon(self)
        self._tray_icon.setContextMenu(self._tray_icon_menu)
        
        self._tray_icon.setIcon(QIcon(":/images/heart.png"))
        self._tray_icon.setToolTip("Heart")
        self._tray_icon.show()
