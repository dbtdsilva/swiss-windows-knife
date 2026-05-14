import ctypes
import faulthandler
import inspect
import logging
import os
import signal
import sys
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from swiss_windows_knife.app_info import APP_INFO
from swiss_windows_knife.base.color_scheme import apply_persisted_preference
from swiss_windows_knife.ui.tray_widget import TrayWidget


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
        self.init_diagnostics()

        signal.signal(signal.SIGINT, signal.SIG_DFL)
        _set_windows_app_user_model_id()
        app = QApplication(sys.argv)
        app.setApplicationName(APP_INFO.APP_NAME)
        app.setQuitOnLastWindowClosed(False)
        app.setWindowIcon(QIcon(":/icons/coat-of-arms.ico"))
        apply_persisted_preference()

        logging.info("Starting widget..")

        widget = TrayWidget(dev_mode)
        widget.hide()
        sys.excepthook = SwissWindowsKnife.excepthook

        sys.exit(app.exec())

    @staticmethod
    def excepthook(exc_type, exc_value, exc_tb):
        tb = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logging.error("Unhandled exception: \n%s", tb)

    def init_diagnostics(self) -> None:
        local_appdata = os.environ.get('LOCALAPPDATA')
        base = Path(local_appdata) if local_appdata else Path.home() / 'AppData' / 'Local'
        logs_dir = base / APP_INFO.APP_NAME / 'logs'
        logs_dir.mkdir(parents=True, exist_ok=True)

        # Route faulthandler to a file because Win32GUI cx_Freeze builds have
        # `sys.stderr is None`; otherwise native crashes (Qt stack overflows,
        # ctypes segfaults) leave only a one-line Windows Event Log entry.
        # The handle is stored on self so the fd outlives this method.
        self._fault_log = open(logs_dir / 'faulthandler.log', 'ab', buffering=0)
        faulthandler.enable(file=self._fault_log, all_threads=True)

        self.init_logging(logs_dir)

    def init_logging(self, logs_dir: Path) -> None:
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

        module_name_filter = LoggingModuleNameFilter()
        handlers: list[logging.Handler] = []

        file_handler = RotatingFileHandler(
            logs_dir / 'swiss-windows-knife.log',
            maxBytes=5_000_000, backupCount=3, encoding='utf-8',
        )
        file_handler.addFilter(module_name_filter)
        handlers.append(file_handler)

        # Skip StreamHandler when stdout is None (Win32GUI frozen build) —
        # it would silently swallow every record.
        if sys.stdout is not None:
            stream_handler = logging.StreamHandler(sys.stdout)
            stream_handler.addFilter(module_name_filter)
            handlers.append(stream_handler)

        logging.basicConfig(format='[%(asctime)s %(name)s-%(threadName)s %(levelname)s] %(message)s',
                            level=logging.INFO,
                            handlers=handlers)


if __name__ == '__main__':
    SwissWindowsKnife(dev_mode=not getattr(sys, 'frozen', False))
