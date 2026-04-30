import ctypes
import faulthandler
import inspect
import logging
import signal
import sys
import traceback

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from src.app_info import APP_INFO
from src.ui.tray_widget import TrayWidget


def _set_windows_app_user_model_id() -> None:
    """Tell Windows this process is its own app, not Python.

    Without this, the Windows taskbar groups by the host `python.exe` (in
    dev runs) or by the frozen exe path (in cx_Freeze builds), and shows
    Python's icon and "python" title rather than ours. Setting an
    explicit AppUserModelID makes Windows use the QApplication icon and
    window titles instead. No-op on non-Windows.
    """
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            f"com.dbtdsilva.{APP_INFO.APP_NAME}".lower().replace(" ", "-"),
        )
    except (AttributeError, OSError):
        pass


class SwissWindowsKnife:

    def __init__(self, dev_mode: bool = False) -> None:
        self.init_logging()
        # Native crashes print a C-stack to stderr — but cx_Freeze with
        # `base='Win32GUI'` builds the frozen exe without a console, so
        # `sys.stderr` is None and `faulthandler.enable()` raises
        # `RuntimeError: sys.stderr is None`. Skip it in that case.
        if sys.stderr is not None:
            faulthandler.enable()

        signal.signal(signal.SIGINT, signal.SIG_DFL)
        _set_windows_app_user_model_id()
        app = QApplication(sys.argv)
        app.setApplicationName(APP_INFO.APP_NAME)
        app.setQuitOnLastWindowClosed(False)
        app.setWindowIcon(QIcon(":/icons/coat-of-arms.ico"))

        logging.info("Starting widget..")

        widget = TrayWidget(dev_mode)
        widget.hide()
        sys.excepthook = SwissWindowsKnife.excepthook

        sys.exit(app.exec())

    @staticmethod
    def excepthook(exc_type, exc_value, exc_tb):
        tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logging.error("Unhandled exception: \n%s", tb)

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
