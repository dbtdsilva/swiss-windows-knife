from typing import Optional
from PySide6.QtCore import Slot, QCoreApplication, Qt
from PySide6.QtGui import QAction, QIcon, QPixmap, QPainter, QWindow
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QVBoxLayout, QMainWindow, QWidget

import rc_systray
from device_listener import DeviceListener


class TrayWindow(QWindow):
    def __init__(self):
        super().__init__()