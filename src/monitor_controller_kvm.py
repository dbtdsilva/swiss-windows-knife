import sys
import signal

from PySide6.QtWidgets import QApplication
from .ui.tray_widget import TrayWidget
import logging


class MonitorControllerKvm:

    def __init__(self) -> None:
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)

        log_format = "%(asctime)s %(levelname)-8s [%(thread)s %(threadName)s] %(name)s: %(message)s"
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG, format=log_format)

        logger = logging.getLogger(__name__)
        logger.info("Starting widget..")

        widget = TrayWidget()
        widget.hide()

        sys.exit(app.exec())
