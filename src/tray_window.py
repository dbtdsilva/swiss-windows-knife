from PySide6.QtGui import QWindow


class TrayWindow(QWindow):
    def __init__(self):
        super().__init__()