from __future__ import annotations

from calendar import isleap
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Callable

import pytz
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFormLayout, QGroupBox, QHBoxLayout, QLabel, QSlider, QVBoxLayout, QWidget

from ...base.config_panel import ConfigPanel
from ...base.user_settings import UserSettings
from .curve import compute_target, gamma_from_slider, slider_from_gamma
from .sun_strength_notifier import (
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


class DisplayTuningConfigPanel(ConfigPanel):

    title = "Display tuning"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._user_settings = UserSettings.instance()

        self._brightness_min = self._make_value_slider()
        self._brightness_max = self._make_value_slider()
        self._brightness_gamma = self._make_gamma_slider()
        self._brightness_min.setValue(self._read_int('brightness_auto_min', 0))
        self._brightness_max.setValue(self._read_int('brightness_auto_max', 100))
        self._brightness_gamma.setValue(slider_from_gamma(self._read_float('brightness_auto_gamma', 1.0)))

        self._contrast_min = self._make_value_slider()
        self._contrast_max = self._make_value_slider()
        self._contrast_gamma = self._make_gamma_slider()
        self._contrast_min.setValue(self._read_int('contrast_auto_min', 0))
        self._contrast_max.setValue(self._read_int('contrast_auto_max', 100))
        self._contrast_gamma.setValue(slider_from_gamma(self._read_float('contrast_auto_gamma', 1.0)))

        self._smoothing = QSlider(Qt.Orientation.Horizontal)
        self._smoothing.setRange(0, 60)
        self._smoothing.setValue(self._read_int('auto_smoothing_seconds', 0))

        self._day = QSlider(Qt.Orientation.Horizontal)
        self._day.setRange(1, 366)
        self._day.setValue(date.today().timetuple().tm_yday)
        self._day_label = QLabel(self._format_day(self._day.value()))

        self._preview = DisplayTuningPreview()
        self._preview.set_sun_callable(self._sun_strength_at)

        # Wire change signals -> preview refresh
        for w in (
            self._brightness_min, self._brightness_max, self._brightness_gamma,
            self._contrast_min, self._contrast_max, self._contrast_gamma,
            self._day,
        ):
            w.valueChanged.connect(self._refresh_preview)
        self._brightness_min.valueChanged.connect(
            lambda v: self._brightness_max.setValue(max(self._brightness_max.value(), v))
        )
        self._brightness_max.valueChanged.connect(
            lambda v: self._brightness_min.setValue(min(self._brightness_min.value(), v))
        )
        self._contrast_min.valueChanged.connect(
            lambda v: self._contrast_max.setValue(max(self._contrast_max.value(), v))
        )
        self._contrast_max.valueChanged.connect(
            lambda v: self._contrast_min.setValue(min(self._contrast_min.value(), v))
        )
        self._day.valueChanged.connect(lambda v: self._day_label.setText(self._format_day(v)))

        layout = QVBoxLayout(self)
        layout.addWidget(self._build_axis_group("Brightness", self._brightness_min,
                                                self._brightness_max, self._brightness_gamma))
        layout.addWidget(self._build_axis_group("Contrast", self._contrast_min,
                                                self._contrast_max, self._contrast_gamma))
        layout.addWidget(self._preview)

        shared = QGroupBox("Shared")
        shared_form = QFormLayout(shared)
        shared_form.addRow("Smoothing (s)", self._smoothing)
        day_row = QHBoxLayout()
        day_row.addWidget(self._day)
        day_row.addWidget(self._day_label)
        shared_form.addRow("Day of year", day_row)
        layout.addWidget(shared)

        self._refresh_preview()

    def _make_value_slider(self) -> QSlider:
        s = QSlider(Qt.Orientation.Horizontal)
        s.setRange(0, 100)
        return s

    def _make_gamma_slider(self) -> QSlider:
        s = QSlider(Qt.Orientation.Horizontal)
        s.setRange(0, 100)
        return s

    def _build_axis_group(self, title, min_w, max_w, gamma_w) -> QGroupBox:
        box = QGroupBox(title)
        form = QFormLayout(box)
        form.addRow("Min", min_w)
        form.addRow("Max", max_w)
        form.addRow("Curve (γ)", gamma_w)
        return box

    def _read_int(self, key: str, default: int) -> int:
        try:
            return int(self._user_settings.get(key))
        except (TypeError, ValueError):
            return default

    def _read_float(self, key: str, default: float) -> float:
        try:
            return float(self._user_settings.get(key))
        except (TypeError, ValueError):
            return default

    def _resolve_location(self) -> tuple[float, float, "pytz.tzinfo.BaseTzInfo"]:
        try:
            latitude = float(self._user_settings.get('sun_latitude'))
            longitude = float(self._user_settings.get('sun_longitude'))
            timezone = pytz.timezone(str(self._user_settings.get('sun_timezone')))
            return latitude, longitude, timezone
        except (TypeError, ValueError, pytz.UnknownTimeZoneError):
            return DEFAULT_LATITUDE, DEFAULT_LONGITUDE, pytz.timezone(DEFAULT_TIMEZONE)

    def _sun_strength_at(self, when):
        lat, lng, _ = self._resolve_location()
        return compute_sun_strength(when, lat, lng)

    def _format_day(self, day_of_year: int) -> str:
        # Use 2024 (leap year) so day=366 is always valid for the label.
        d = date(2024, 1, 1) + timedelta(days=day_of_year - 1)
        return d.strftime("%b %d")

    def _refresh_preview(self) -> None:
        _, _, tz = self._resolve_location()
        year = date.today().year
        last_day = 366 if isleap(year) else 365
        day_int = min(self._day.value(), last_day)
        day = date(year, 1, 1) + timedelta(days=day_int - 1)
        day_start = tz.localize(datetime(day.year, day.month, day.day, 0, 0))
        is_today = day == date.today()
        self._preview.set_date(day_start, show_now_marker=is_today)

        self._preview.set_brightness(AxisCurveSettings(
            min_value=self._brightness_min.value(),
            max_value=self._brightness_max.value(),
            gamma=gamma_from_slider(self._brightness_gamma.value()),
        ))
        self._preview.set_contrast(AxisCurveSettings(
            min_value=self._contrast_min.value(),
            max_value=self._contrast_max.value(),
            gamma=gamma_from_slider(self._contrast_gamma.value()),
        ))

    def apply(self) -> bool:
        self._user_settings.set('brightness_auto_min', self._brightness_min.value())
        self._user_settings.set('brightness_auto_max', self._brightness_max.value())
        self._user_settings.set('brightness_auto_gamma',
                                gamma_from_slider(self._brightness_gamma.value()))
        self._user_settings.set('contrast_auto_min', self._contrast_min.value())
        self._user_settings.set('contrast_auto_max', self._contrast_max.value())
        self._user_settings.set('contrast_auto_gamma',
                                gamma_from_slider(self._contrast_gamma.value()))
        self._user_settings.set('auto_smoothing_seconds', self._smoothing.value())
        return True
