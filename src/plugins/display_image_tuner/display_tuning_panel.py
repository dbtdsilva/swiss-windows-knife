from __future__ import annotations

from calendar import isleap
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import pytz
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QSlider,
    QVBoxLayout, QWidget,
)

from ...base.config_panel import ConfigPanel
from ...base.user_settings import UserSettings
from .curve import compute_keyframe_value
from .sun_strength_notifier import (
    DEFAULT_LATITUDE, DEFAULT_LONGITUDE, DEFAULT_TIMEZONE, find_sun_events,
)


def _make_value_label(text: str, sample: str) -> QLabel:
    """A right-aligned readout label whose width is fixed to fit `sample`,
    so the slider next to it doesn't shift as the displayed text changes."""
    label = QLabel(text)
    label.setMinimumWidth(label.fontMetrics().horizontalAdvance(sample) + 4)
    label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return label


SAMPLES_PER_DAY = 96  # 15-minute resolution
COLOR_BRIGHTNESS = QColor(255, 191, 0)
COLOR_CONTRAST = QColor(64, 156, 255)
COLOR_AXIS = QColor(120, 120, 120)
COLOR_GRID = QColor(60, 60, 60)
COLOR_NOW = QColor(220, 80, 80)
COLOR_SUNRISE = QColor(255, 140, 0)
COLOR_SUNSET = QColor(180, 80, 200)


@dataclass
class AxisRender:
    """One axis of the preview: either an auto curve definition or a flat
    fixed value. Renderer plots whichever applies."""
    fixed_value: int | None
    night_level: int
    day_level: int


@dataclass
class SharedRamp:
    sunrise_offset_min: float
    sunset_offset_min: float
    duration_min: float
    smoothness: float


class DisplayTuningPreview(QWidget):
    """Plots brightness and contrast curves through a single day."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(480, 220)

        self._brightness = AxisRender(None, 0, 100)
        self._contrast = AxisRender(None, 0, 100)
        self._ramp = SharedRamp(0.0, 0.0, 60.0, 0.0)
        self._date: datetime | None = None
        self._sun_events: tuple[float | None, float | None] = (None, None)
        self._show_now_marker = False

    def set_brightness(self, axis: AxisRender) -> None:
        self._brightness = axis
        self.update()

    def set_contrast(self, axis: AxisRender) -> None:
        self._contrast = axis
        self.update()

    def set_ramp(self, ramp: SharedRamp) -> None:
        self._ramp = ramp
        self.update()

    def set_date(self, day_start_local: datetime, *, show_now_marker: bool) -> None:
        self._date = day_start_local
        self._show_now_marker = show_now_marker
        self.update()

    def set_sun_events(self, sunrise_h: float | None, sunset_h: float | None) -> None:
        self._sun_events = (sunrise_h, sunset_h)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: D401
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        plot_rect = self._plot_rect()
        self._draw_axes_and_grid(painter, plot_rect)

        sunrise_h, sunset_h = self._sun_events
        if sunrise_h is not None:
            self._draw_event_marker(painter, plot_rect, sunrise_h, "sunrise", COLOR_SUNRISE)
        if sunset_h is not None:
            self._draw_event_marker(painter, plot_rect, sunset_h, "sunset", COLOR_SUNSET)

        b_path = self._build_axis_path(plot_rect, self._brightness)
        c_path = self._build_axis_path(plot_rect, self._contrast)

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

        for y_pct in (0, 50, 100):
            y = rect.bottom() - rect.height() * (y_pct / 100.0)
            painter.drawText(QPointF(4, y + 4), str(y_pct))
        for hour in (0, 6, 12, 18, 24):
            x = rect.left() + rect.width() * (hour / 24.0)
            painter.drawText(QPointF(x - 6, rect.bottom() + 16), f"{hour}h")

    def _build_axis_path(self, rect: QRectF, axis: AxisRender) -> QPainterPath:
        sunrise_h, sunset_h = self._sun_events
        path = QPainterPath()
        for i in range(SAMPLES_PER_DAY + 1):
            hour_fraction = i / SAMPLES_PER_DAY
            when_h = hour_fraction * 24.0
            if axis.fixed_value is not None:
                value = float(axis.fixed_value)
            else:
                value = compute_keyframe_value(
                    when_h,
                    sunrise_hours=sunrise_h,
                    sunset_hours=sunset_h,
                    night_level=axis.night_level,
                    day_level=axis.day_level,
                    sunrise_offset_minutes=self._ramp.sunrise_offset_min,
                    sunset_offset_minutes=self._ramp.sunset_offset_min,
                    ramp_duration_minutes=self._ramp.duration_min,
                    ramp_smoothness=self._ramp.smoothness,
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

    def _draw_event_marker(
        self, painter: QPainter, rect: QRectF, hour: float, label: str, color: QColor,
    ) -> None:
        x = rect.left() + rect.width() * (hour / 24.0)
        painter.setPen(QPen(color, 1.0, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
        painter.setPen(QPen(color, 1.0))
        painter.drawText(QPointF(x + 3, rect.top() + 12), label)

    def _draw_now_marker(self, painter: QPainter, rect: QRectF) -> None:
        now = datetime.now().astimezone()
        hour_fraction = (now.hour + now.minute / 60.0) / 24.0
        x = rect.left() + rect.width() * hour_fraction
        painter.setPen(QPen(COLOR_NOW, 1.0, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))


SMOOTHNESS_SLIDER_RANGE = 100
RAMP_OFFSET_RANGE_MIN = -120
RAMP_OFFSET_RANGE_MAX = 120
RAMP_DURATION_RANGE_MAX = 240


def smoothness_from_slider(pos: int) -> float:
    pos = max(0, min(SMOOTHNESS_SLIDER_RANGE, int(pos)))
    return (pos - SMOOTHNESS_SLIDER_RANGE / 2) / (SMOOTHNESS_SLIDER_RANGE / 2)


def slider_from_smoothness(smoothness: float) -> int:
    s = max(-1.0, min(1.0, float(smoothness)))
    return int(round((s + 1.0) * SMOOTHNESS_SLIDER_RANGE / 2))


class _AxisControls:
    """Per-axis control bundle: mode picker + fixed value + night + day."""

    def __init__(self, settings: UserSettings, axis: str) -> None:
        self._settings = settings
        self._axis = axis

        self.mode = QComboBox()
        self.mode.addItems(["Auto", "Fixed"])

        current = settings.get(axis)
        is_fixed = current is not None
        self.mode.setCurrentIndex(1 if is_fixed else 0)

        self.fixed = QSlider(Qt.Orientation.Horizontal)
        self.fixed.setRange(0, 100)
        self.fixed.setValue(int(current) if is_fixed else 50)
        self.fixed_label = _make_value_label(str(self.fixed.value()), "100")

        self.night = QSlider(Qt.Orientation.Horizontal)
        self.night.setRange(0, 100)
        self.night.setValue(self._read_int(f'{axis}_night_level', 0))
        self.night_label = _make_value_label(str(self.night.value()), "100")

        self.day = QSlider(Qt.Orientation.Horizontal)
        self.day.setRange(0, 100)
        self.day.setValue(self._read_int(f'{axis}_day_level', 100))
        self.day_label = _make_value_label(str(self.day.value()), "100")

        self.fixed.valueChanged.connect(lambda v: self.fixed_label.setText(str(v)))
        self.night.valueChanged.connect(lambda v: self.night_label.setText(str(v)))
        self.day.valueChanged.connect(lambda v: self.day_label.setText(str(v)))

        self.mode.currentIndexChanged.connect(self._update_enabled)
        self._update_enabled()

    def _update_enabled(self) -> None:
        is_fixed = self.is_fixed()
        self.fixed.setEnabled(is_fixed)
        self.fixed_label.setEnabled(is_fixed)
        self.night.setEnabled(not is_fixed)
        self.night_label.setEnabled(not is_fixed)
        self.day.setEnabled(not is_fixed)
        self.day_label.setEnabled(not is_fixed)

    def is_fixed(self) -> bool:
        return self.mode.currentIndex() == 1

    def render(self) -> AxisRender:
        return AxisRender(
            fixed_value=self.fixed.value() if self.is_fixed() else None,
            night_level=self.night.value(),
            day_level=self.day.value(),
        )

    def apply(self) -> None:
        if self.is_fixed():
            self._settings.set(self._axis, self.fixed.value())
        else:
            self._settings.set(self._axis, None)
        self._settings.set(f'{self._axis}_night_level', self.night.value())
        self._settings.set(f'{self._axis}_day_level', self.day.value())

    def build_group(self, title: str) -> QGroupBox:
        box = QGroupBox(title)
        form = QFormLayout(box)
        form.addRow("Mode", self.mode)
        form.addRow("Fixed value", self._with_label(self.fixed, self.fixed_label))
        form.addRow("Night level", self._with_label(self.night, self.night_label))
        form.addRow("Day level", self._with_label(self.day, self.day_label))
        return box

    def _with_label(self, slider: QSlider, label: QLabel) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(slider)
        row.addWidget(label)
        return row

    def _read_int(self, key: str, default: int) -> int:
        try:
            return int(self._settings.get(key))
        except (TypeError, ValueError):
            return default


class DisplayTuningConfigPanel(ConfigPanel):

    title = "Display tuning"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._user_settings = UserSettings.instance()

        self._brightness_ctrl = _AxisControls(self._user_settings, 'brightness')
        self._contrast_ctrl = _AxisControls(self._user_settings, 'contrast')

        self._sunrise_offset = QSlider(Qt.Orientation.Horizontal)
        self._sunrise_offset.setRange(RAMP_OFFSET_RANGE_MIN, RAMP_OFFSET_RANGE_MAX)
        self._sunrise_offset.setValue(self._read_int('auto_sunrise_offset_minutes', 0))
        self._sunrise_offset_label = _make_value_label(
            self._format_minutes(self._sunrise_offset.value()), "+120 min")

        self._sunset_offset = QSlider(Qt.Orientation.Horizontal)
        self._sunset_offset.setRange(RAMP_OFFSET_RANGE_MIN, RAMP_OFFSET_RANGE_MAX)
        self._sunset_offset.setValue(self._read_int('auto_sunset_offset_minutes', 0))
        self._sunset_offset_label = _make_value_label(
            self._format_minutes(self._sunset_offset.value()), "+120 min")

        self._ramp_duration = QSlider(Qt.Orientation.Horizontal)
        self._ramp_duration.setRange(0, RAMP_DURATION_RANGE_MAX)
        self._ramp_duration.setValue(self._read_int('auto_ramp_duration_minutes', 60))
        self._ramp_duration_label = _make_value_label(
            self._format_minutes(self._ramp_duration.value()), "+120 min")

        self._ramp_smoothness = QSlider(Qt.Orientation.Horizontal)
        self._ramp_smoothness.setRange(0, SMOOTHNESS_SLIDER_RANGE)
        self._ramp_smoothness.setValue(slider_from_smoothness(
            self._read_float('auto_ramp_smoothness', 0.0)
        ))
        self._ramp_smoothness_label = _make_value_label(
            self._format_smoothness(self._ramp_smoothness.value()), "ease-out -0.50")

        self._day = QSlider(Qt.Orientation.Horizontal)
        self._day.setRange(1, 366)
        self._day.setValue(date.today().timetuple().tm_yday)
        self._day_label = _make_value_label(self._format_day(self._day.value()), "Sep 30")

        self._preview = DisplayTuningPreview()

        for ctrl in (self._brightness_ctrl, self._contrast_ctrl):
            ctrl.mode.currentIndexChanged.connect(self._refresh_preview)
            ctrl.fixed.valueChanged.connect(self._refresh_preview)
            ctrl.night.valueChanged.connect(self._refresh_preview)
            ctrl.day.valueChanged.connect(self._refresh_preview)
        self._sunrise_offset.valueChanged.connect(self._refresh_preview)
        self._sunrise_offset.valueChanged.connect(
            lambda v: self._sunrise_offset_label.setText(self._format_minutes(v))
        )
        self._sunset_offset.valueChanged.connect(self._refresh_preview)
        self._sunset_offset.valueChanged.connect(
            lambda v: self._sunset_offset_label.setText(self._format_minutes(v))
        )
        self._ramp_duration.valueChanged.connect(self._refresh_preview)
        self._ramp_duration.valueChanged.connect(
            lambda v: self._ramp_duration_label.setText(self._format_minutes(v))
        )
        self._ramp_smoothness.valueChanged.connect(self._refresh_preview)
        self._ramp_smoothness.valueChanged.connect(
            lambda v: self._ramp_smoothness_label.setText(self._format_smoothness(v))
        )
        self._day.valueChanged.connect(self._refresh_preview)
        self._day.valueChanged.connect(lambda v: self._day_label.setText(self._format_day(v)))

        layout = QVBoxLayout(self)
        layout.addWidget(self._brightness_ctrl.build_group("Brightness"))
        layout.addWidget(self._contrast_ctrl.build_group("Contrast"))
        layout.addWidget(self._preview)

        ramp_box = QGroupBox("Ramp (shared)")
        ramp_form = QFormLayout(ramp_box)
        ramp_form.addRow("Sunrise offset", self._row(self._sunrise_offset, self._sunrise_offset_label))
        ramp_form.addRow("Sunset offset", self._row(self._sunset_offset, self._sunset_offset_label))
        ramp_form.addRow("Duration", self._row(self._ramp_duration, self._ramp_duration_label))
        ramp_form.addRow("Smoothness", self._row(self._ramp_smoothness, self._ramp_smoothness_label))
        ramp_form.addRow("Preview day", self._row(self._day, self._day_label))
        layout.addWidget(ramp_box)

        self._refresh_preview()

    @staticmethod
    def _row(slider: QSlider, label: QLabel) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(slider)
        row.addWidget(label)
        return row

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

    def _format_day(self, day_of_year: int) -> str:
        d = date(2024, 1, 1) + timedelta(days=day_of_year - 1)
        return d.strftime("%b %d")

    def _format_minutes(self, minutes: int) -> str:
        sign = "+" if minutes > 0 else ""
        return f"{sign}{minutes} min"

    def _format_smoothness(self, slider_pos: int) -> str:
        s = smoothness_from_slider(slider_pos)
        if abs(s) < 0.05:
            return "linear"
        if s > 0:
            return f"ease-in {s:+.2f}"
        return f"ease-out {s:+.2f}"

    def _refresh_preview(self) -> None:
        latitude, longitude, tz = self._resolve_location()
        year = date.today().year
        last_day = 366 if isleap(year) else 365
        day_int = min(self._day.value(), last_day)
        day = date(year, 1, 1) + timedelta(days=day_int - 1)
        day_start = tz.localize(datetime(day.year, day.month, day.day, 0, 0))
        is_today = day == date.today()

        sunrise_h, sunset_h = find_sun_events(day_start, latitude, longitude)
        self._preview.set_sun_events(sunrise_h, sunset_h)
        self._preview.set_date(day_start, show_now_marker=is_today)
        self._preview.set_ramp(SharedRamp(
            sunrise_offset_min=float(self._sunrise_offset.value()),
            sunset_offset_min=float(self._sunset_offset.value()),
            duration_min=float(self._ramp_duration.value()),
            smoothness=smoothness_from_slider(self._ramp_smoothness.value()),
        ))
        self._preview.set_brightness(self._brightness_ctrl.render())
        self._preview.set_contrast(self._contrast_ctrl.render())

    def apply(self) -> bool:
        self._brightness_ctrl.apply()
        self._contrast_ctrl.apply()
        self._user_settings.set('auto_sunrise_offset_minutes', self._sunrise_offset.value())
        self._user_settings.set('auto_sunset_offset_minutes', self._sunset_offset.value())
        self._user_settings.set('auto_ramp_duration_minutes', self._ramp_duration.value())
        self._user_settings.set('auto_ramp_smoothness',
                                smoothness_from_slider(self._ramp_smoothness.value()))
        return True
