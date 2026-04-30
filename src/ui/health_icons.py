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

_TRAY_ICON_SIZE = QSize(64, 64)
_TRAY_DOT_RECT = (40, 0, 24, 24)  # x, y, width, height — top-right


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
    icon = QIcon()
    # Health rows and the summary line are disabled QActions, so Qt would
    # auto-grey a single-mode icon. Register the coloured pixmap for both
    # Normal and Disabled modes so the dot keeps its colour either way.
    icon.addPixmap(pix, QIcon.Mode.Normal)
    icon.addPixmap(pix, QIcon.Mode.Disabled)
    return icon


@cache
def tray_icon_for_state(state: HealthState) -> QIcon:
    """Return the app's tray icon overlaid with a coloured dot for `state`.

    The dot sits in the top-right corner of a 64x64 composed pixmap;
    Windows downsamples for the systray slot. Cached per state.
    """
    base = QIcon(":/icons/coat-of-arms.ico").pixmap(_TRAY_ICON_SIZE)
    composed = QPixmap(_TRAY_ICON_SIZE)
    composed.fill(Qt.GlobalColor.transparent)
    painter = QPainter(composed)
    try:
        painter.drawPixmap(0, 0, base)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setBrush(_COLORS[state])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(*_TRAY_DOT_RECT)
    finally:
        painter.end()
    icon = QIcon()
    icon.addPixmap(composed, QIcon.Mode.Normal)
    icon.addPixmap(composed, QIcon.Mode.Disabled)
    return icon
