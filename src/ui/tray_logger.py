import logging

from PySide6.QtCore import QSize
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPlainTextEdit, QVBoxLayout

from ..base.persistent_dialog import PersistentSizeDialog
from ..base.user_settings import UserSettings


class QTextEditLogger(logging.Handler):
    def __init__(self, parent):
        super().__init__()
        self.widget = QPlainTextEdit(parent)
        self.widget.setReadOnly(True)

    def emit(self, record):
        msg = self.format(record)
        self.widget.appendPlainText(msg)


class TrayLogger(PersistentSizeDialog):

    size_settings_prefix = "logs_dialog"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Logs")
        QShortcut(QKeySequence(QKeySequence.StandardKey.Cancel), self, self.close)

        # logger widget
        logger_text_box = QTextEditLogger(self)
        logger_text_box.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)-8s [%(thread)s %(threadName)s] %(name)s: %(message)s"))

        logging.getLogger().addHandler(logger_text_box)
        logging.getLogger().setLevel(logging.DEBUG)

        # dropdown for log level
        self.user_settings = UserSettings.instance()
        if not self.user_settings.has_key('logging_level'):
            self.user_settings.set('logging_level', 'INFO')

        default_logging_level = self.user_settings.get_str('logging_level', 'INFO')
        self.level_selector = QComboBox()
        self.level_selector.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.level_selector.setCurrentText(default_logging_level)
        self.level_selector.currentTextChanged.connect(self.change_log_level)
        self.change_log_level(default_logging_level)

        level_layout = QHBoxLayout()
        level_layout.addWidget(QLabel("Log Level:"))
        level_layout.addWidget(self.level_selector)

        # main layout
        layout = QVBoxLayout()
        layout.addLayout(level_layout)
        layout.addWidget(logger_text_box.widget)

        self.setLayout(layout)
        self.restore_size(QSize(800, 700))

    def change_log_level(self, level_str: str):
        level = getattr(logging, level_str)
        logging.getLogger().setLevel(level)
        logging.info(f"Log level changed to {level_str}")
        self.user_settings.set('logging_level', level_str)
