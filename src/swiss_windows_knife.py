import inspect
import sys
import signal

from PySide6.QtWidgets import QApplication
from src.ui.tray_widget import TrayWidget
import logging


class SwissWindowsKnife:

    def __init__(self) -> None:
        self.init_logging()

        signal.signal(signal.SIGINT, signal.SIG_DFL)
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)

        logging.info("Starting widget..")

        widget = TrayWidget()
        widget.hide()

        sys.exit(app.exec())

    def init_logging(self):
        class LoggingModuleNameFilter(logging.Filter):
            def filter(self, record):
                frame = inspect.currentframe()
                if frame is None:
                    return True

                frame = frame.f_back
                while frame is not None:
                    module = inspect.getmodule(frame)
                    if module and module != logging:
                        record.name = module.__name__
                        break
                    frame = frame.f_back
                return True

        handler = logging.StreamHandler(sys.stdout)
        handler.addFilter(LoggingModuleNameFilter())
        logging.basicConfig(format='[%(asctime)s %(name)s-%(threadName)s %(levelname)s] %(message)s',
                            level=logging.INFO,
                            handlers=[handler])


if __name__ == '__main__':
    SwissWindowsKnife()
