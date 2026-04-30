from functools import cache

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap

from ..base.health import HealthState

_COLORS: dict[HealthState, QColor] = {
    HealthState.OK: QColor(76, 175, 80),       # green
    HealthState.WARNING: QColor(255, 152, 0),  # amber
    HealthState.ERROR: QColor(244, 67, 54),    # red
    HealthState.DISABLED: QColor(158, 158, 158),  # grey
}

_ICON_SIZE = QSize(12, 12)


@cache
def icon_for_state(state: HealthState) -> QIcon:
    pix = QPixmap(_ICON_SIZE)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setBrush(_COLORS[state])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, _ICON_SIZE.width(), _ICON_SIZE.height())
    finally:
        painter.end()
    return QIcon(pix)
