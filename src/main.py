import sys
import signal

from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon, QMainWindow
from PySide6.QtCore import Qt
from tray_widget import TrayWidget

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_UseHighDpiPixmaps)
    app.setQuitOnLastWindowClosed(False)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, "Systray", "I couldn't detect any system tray on this system.")
        sys.exit(1)

    widget = TrayWidget()
    sys.exit(app.exec())
