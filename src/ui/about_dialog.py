from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ..app_info import APP_INFO


class AboutDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f'About {APP_INFO.APP_NAME}')
        self.setWindowIcon(QIcon(':/icons/coat-of-arms.ico'))

        icon_label = QLabel()
        icon_label.setPixmap(QIcon(':/icons/coat-of-arms.ico').pixmap(64, 64))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        info_label = QLabel(
            f"<h2 style='margin:0'>{APP_INFO.APP_NAME}</h2>"
            f"<p style='color:gray;margin:4px 24px'>{APP_INFO.APP_TAGLINE}</p>"
            f"<p>Version {APP_INFO.APP_VERSION}</p>"
            f"<p>{APP_INFO.APP_AUTHOR}<br>"
            f"Released under the {APP_INFO.APP_LICENSE} License</p>"
            f"<p><a href='{APP_INFO.APP_URL}'>{APP_INFO.APP_URL}</a></p>"
        )
        info_label.setWordWrap(True)
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setTextFormat(Qt.TextFormat.RichText)
        info_label.setOpenExternalLinks(True)
        info_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(icon_label)
        layout.addWidget(info_label)
        layout.addWidget(button_box)
