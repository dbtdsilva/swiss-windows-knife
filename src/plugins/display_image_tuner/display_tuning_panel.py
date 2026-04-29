from __future__ import annotations

from calendar import isleap  # noqa: F401
from dataclasses import dataclass
from datetime import date, datetime, timedelta  # noqa: F401
from typing import Callable

import pytz  # noqa: F401
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFormLayout, QGroupBox, QHBoxLayout, QLabel, QSlider, QVBoxLayout, QWidget  # noqa: F401

from ...base.config_panel import ConfigPanel  # noqa: F401
from ...base.user_settings import UserSettings  # noqa: F401
from .curve import compute_target, gamma_from_slider, slider_from_gamma  # noqa: F401
from .sun_strength_notifier import (  # noqa: F401
    DEFAULT_LATITUDE, DEFAULT_LONGITUDE, DEFAULT_TIMEZONE, compute_sun_strength,
)


SAMPLES_PER_DAY = 96  # 15-minute resolution
COLOR_BRIGHTNESS = QColor(255, 191, 0)   # amber
COLOR_CONTRAST = QColor(64, 156, 255)    # blue
COLOR_AXIS = QColor(120, 120, 120)
COLOR_GRID = QColor(60, 60, 60)
COLOR_NOW = QColor(220, 80, 80)


@dataclass
class AxisCurveSettings:
    min_value: int
    max_value: int
    gamma: float


SunStrengthAt = Callable[[datetime], int]


class DisplayTuningPreview(QWidget):
    """Plots brightness and contrast curves through a single day."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(480, 220)

        self._brightness = AxisCurveSettings(0, 100, 1.0)
        self._contrast = AxisCurveSettings(0, 100, 1.0)
        self._date: datetime | None = None
        self._sun_at: SunStrengthAt | None = None
        self._show_now_marker = False

    def set_brightness(self, settings: AxisCurveSettings) -> None:
        self._brightness = settings
        self.update()

    def set_contrast(self, settings: AxisCurveSettings) -> None:
        self._contrast = settings
        self.update()

    def set_date(self, day_start_local: datetime, *, show_now_marker: bool) -> None:
        self._date = day_start_local
        self._show_now_marker = show_now_marker
        self.update()

    def set_sun_callable(self, sun_at: SunStrengthAt) -> None:
        self._sun_at = sun_at
        self.update()

    def paintEvent(self, event) -> None:  # noqa: D401
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        plot_rect = self._plot_rect()
        self._draw_axes_and_grid(painter, plot_rect)

        if self._date is None or self._sun_at is None:
            painter.end()
            return

        b_path = self._build_path(plot_rect, self._brightness)
        c_path = self._build_path(plot_rect, self._contrast)

        painter.setPen(QPen(COLOR_BRIGHTNESS, 2.0))
        painter.drawPath(b_path)
        painter.setPen(QPen(COLOR_CONTRAST, 2.0))
        painter.drawPath(c_path)

        self._draw_legend(painter, plot_rect)

        if self._show_now_marker:
            self._draw_now_marker(painter, plot_rect)

        painter.end()

    def _plot_rect(self) -> QRectF:
        margin_left = 32
        margin_right = 12
        margin_top = 12
        margin_bottom = 24
        return QRectF(
            margin_left, margin_top,
            self.width() - margin_left - margin_right,
            self.height() - margin_top - margin_bottom,
        )

    def _draw_axes_and_grid(self, painter: QPainter, rect: QRectF) -> None:
        painter.setPen(QPen(COLOR_GRID, 1.0))
        for y_pct in (0, 25, 50, 75, 100):
            y = rect.bottom() - rect.height() * (y_pct / 100.0)
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
        for hour in (0, 6, 12, 18, 24):
            x = rect.left() + rect.width() * (hour / 24.0)
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))

        painter.setPen(QPen(COLOR_AXIS, 1.0))
        painter.drawRect(rect)

        painter.setPen(QPen(COLOR_AXIS, 1.0))
        for y_pct in (0, 50, 100):
            y = rect.bottom() - rect.height() * (y_pct / 100.0)
            painter.drawText(QPointF(4, y + 4), str(y_pct))
        for hour in (0, 6, 12, 18, 24):
            x = rect.left() + rect.width() * (hour / 24.0)
            painter.drawText(QPointF(x - 6, rect.bottom() + 16), f"{hour}h")

    def _build_path(self, rect: QRectF, settings: AxisCurveSettings) -> QPainterPath:
        assert self._date is not None and self._sun_at is not None
        path = QPainterPath()
        for i in range(SAMPLES_PER_DAY + 1):
            hour_fraction = i / SAMPLES_PER_DAY
            t = self._date + timedelta(hours=24 * hour_fraction)
            sun = self._sun_at(t)
            value = compute_target(
                sun,
                min_value=settings.min_value,
                max_value=settings.max_value,
                gamma=settings.gamma,
            )
            x = rect.left() + rect.width() * hour_fraction
            y = rect.bottom() - rect.height() * (value / 100.0)
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        return path

    def _draw_legend(self, painter: QPainter, rect: QRectF) -> None:
        x = rect.right() - 130
        y = rect.top() + 14
        painter.setPen(QPen(COLOR_BRIGHTNESS, 3.0))
        painter.drawLine(QPointF(x, y), QPointF(x + 18, y))
        painter.setPen(QPen(COLOR_AXIS, 1.0))
        painter.drawText(QPointF(x + 24, y + 4), "Brightness")
        y += 14
        painter.setPen(QPen(COLOR_CONTRAST, 3.0))
        painter.drawLine(QPointF(x, y), QPointF(x + 18, y))
        painter.setPen(QPen(COLOR_AXIS, 1.0))
        painter.drawText(QPointF(x + 24, y + 4), "Contrast")

    def _draw_now_marker(self, painter: QPainter, rect: QRectF) -> None:
        now = datetime.now().astimezone()
        hour_fraction = (now.hour + now.minute / 60.0) / 24.0
        x = rect.left() + rect.width() * hour_fraction
        painter.setPen(QPen(COLOR_NOW, 1.0, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
