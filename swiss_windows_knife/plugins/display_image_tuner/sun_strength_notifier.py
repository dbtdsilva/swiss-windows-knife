import logging
from datetime import datetime, timedelta

import pytz
from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QWidget
from pysolar import radiation, solar

from ...base.base_widget import BaseWidget
from ...base.user_settings import UserSettings

DEFAULT_LATITUDE = 46.521410
DEFAULT_LONGITUDE = 6.632273
DEFAULT_TIMEZONE = 'Europe/Zurich'
ALTITUDE_OFFSET_DEG = 5
SUN_EVENT_SAMPLES_PER_DAY = 144  # 10-minute resolution


def compute_sun_strength(when: datetime, latitude: float, longitude: float) -> int:
    """Compute 0-100 sun strength at `when` for `(latitude, longitude)`.

    Mirrors the original mapping: solar altitude (with a 5deg offset for
    horizon haze) feeds into pysolar's direct-radiation model; the 0-600
    W/m^2 band is linearly mapped to 0-100 and capped at 100.

    `when` MUST be timezone-aware. The function converts to UTC internally.
    """
    altitude = solar.get_altitude(latitude, longitude, when) + ALTITUDE_OFFSET_DEG
    utc_naive = when.astimezone(pytz.utc).replace(tzinfo=None)
    power = radiation.get_radiation_direct(utc_naive, altitude)
    return int(power / 6.0) if power < 600 else 100


def find_sun_events(
    day_start_local: datetime,
    latitude: float,
    longitude: float,
    *,
    n_samples: int = SUN_EVENT_SAMPLES_PER_DAY,
) -> tuple[float | None, float | None]:
    """Find sunrise / sunset hours-of-day for the local day starting at
    `day_start_local`. Returns (sunrise_hour, sunset_hour); either may be
    None if the corresponding transition does not occur on the day.
    """
    sunrise_h: float | None = None
    sunset_h: float | None = None
    prev = compute_sun_strength(day_start_local, latitude, longitude)
    for i in range(1, n_samples + 1):
        t = day_start_local + timedelta(hours=24 * i / n_samples)
        curr = compute_sun_strength(t, latitude, longitude)
        h_mid = (i - 0.5) / n_samples * 24.0
        if prev == 0 and curr > 0 and sunrise_h is None:
            sunrise_h = h_mid
        if prev > 0 and curr == 0:
            sunset_h = h_mid
        prev = curr
    return sunrise_h, sunset_h


class SunStrengthNotifier(BaseWidget):

    sun_strength_changed = Signal(int)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.user_settings = UserSettings.instance()
        self._ensure_defaults()

        self.timer = QTimer()
        self.timer.timeout.connect(self.calculate_sun_strength)
        self.timer.start(1000 * 60)
        self.calculate_sun_strength()

    def _ensure_defaults(self) -> None:
        if not self.user_settings.has_key('sun_latitude'):
            self.user_settings.set('sun_latitude', DEFAULT_LATITUDE)
        if not self.user_settings.has_key('sun_longitude'):
            self.user_settings.set('sun_longitude', DEFAULT_LONGITUDE)
        if not self.user_settings.has_key('sun_timezone'):
            self.user_settings.set('sun_timezone', DEFAULT_TIMEZONE)

    def resolve_location(self) -> tuple[float, float, "pytz.tzinfo.BaseTzInfo"]:
        latitude = self.user_settings.get('sun_latitude', float)
        longitude = self.user_settings.get('sun_longitude', float)
        timezone_name = self.user_settings.get('sun_timezone', str, DEFAULT_TIMEZONE)
        if latitude is None or longitude is None:
            logging.warning("Invalid sun-strength settings, falling back to defaults")
            return DEFAULT_LATITUDE, DEFAULT_LONGITUDE, pytz.timezone(DEFAULT_TIMEZONE)
        try:
            return latitude, longitude, pytz.timezone(timezone_name)
        except pytz.UnknownTimeZoneError:
            logging.warning("Invalid sun-strength settings, falling back to defaults")
            return DEFAULT_LATITUDE, DEFAULT_LONGITUDE, pytz.timezone(DEFAULT_TIMEZONE)

    def calculate_sun_strength(self):
        latitude, longitude, timezone = self.resolve_location()
        when = datetime.now().astimezone(timezone)
        current_value = compute_sun_strength(when, latitude, longitude)
        self.sun_strength_changed.emit(current_value)
        logging.debug(f'Sun strength has changed to {current_value}')

    def closeEvent(self, event):
        self.timer.stop()
        event.accept()
