import sys
import signal

from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon
from PySide6 import QtCore
from window import Window
from device_listener import DeviceConnect, DeviceDisconnect

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication()

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, "Systray", "I couldn't detect any system tray on this system.")
        sys.exit(1)

    QApplication.setQuitOnLastWindowClosed(False)
    
    thread_connect = QtCore.QThread()
    device_connect = DeviceConnect()
    device_connect.moveToThread(thread_connect)
    thread_connect.started.connect(device_connect.run)

    thread_disconnect = QtCore.QThread()
    device_disconnect = DeviceDisconnect()
    device_disconnect.moveToThread(thread_disconnect)
    thread_disconnect.started.connect(device_disconnect.run)

    thread_connect.start()
    thread_disconnect.start()

    window = Window()
    sys.exit(app.exec())
