import sys
import signal

from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon
from tray_widget import TrayWidget
import logging

if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, "Systray", "I couldn't detect any system tray on this system.")
        sys.exit(1)

    log_format = "%(asctime)s %(levelname)-8s [%(thread)s %(threadName)s] %(name)s: %(message)s"
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format=log_format)

    logger = logging.getLogger(__name__)
    logger.info("Starting widget..")

    widget = TrayWidget()
    sys.exit(app.exec())
