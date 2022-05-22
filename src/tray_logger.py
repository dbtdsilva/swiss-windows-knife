from PySide6.QtWidgets import QDialog, QPlainTextEdit, QVBoxLayout, QPushButton
import logging


class QTextEditLogger(logging.Handler):
    def __init__(self, parent):
        super().__init__()
        self.widget = QPlainTextEdit(parent)
        self.widget.setReadOnly(True)

    def emit(self, record):
        msg = self.format(record)
        self.widget.appendPlainText(msg)


class TrayLogger(QDialog, QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)

        logger_text_box = QTextEditLogger(self)
        logger_text_box.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s [%(thread)s %(threadName)s] %(name)s: %(message)s"))

        logging.getLogger().addHandler(logger_text_box)
        logging.getLogger().setLevel(logging.DEBUG)

        layout = QVBoxLayout()
        layout.addWidget(logger_text_box.widget)

        self.setLayout(layout)
        self.resize(800, 700)
        