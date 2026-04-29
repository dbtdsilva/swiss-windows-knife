from datetime import datetime
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import QTimer, Signal
import pytz
from ...base.base_widget import BaseWidget
from ...base.user_settings import UserSettings
from pysolar import solar, radiation
import logging


DEFAULT_LATITUDE = 46.521410
DEFAULT_LONGITUDE = 6.632273
DEFAULT_TIMEZONE = 'Europe/Zurich'
ALTITUDE_OFFSET_DEG = 5


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

    def _resolve_location(self) -> tuple[float, float, "pytz.tzinfo.BaseTzInfo"]:
        try:
            latitude = float(self.user_settings.get('sun_latitude'))  # type: ignore[arg-type]
            longitude = float(self.user_settings.get('sun_longitude'))  # type: ignore[arg-type]
            timezone = pytz.timezone(str(self.user_settings.get('sun_timezone')))
            return latitude, longitude, timezone
        except (TypeError, ValueError, pytz.UnknownTimeZoneError):
            logging.warning("Invalid sun-strength settings, falling back to defaults")
            return DEFAULT_LATITUDE, DEFAULT_LONGITUDE, pytz.timezone(DEFAULT_TIMEZONE)

    def calculate_sun_strength(self):
        latitude, longitude, timezone = self._resolve_location()
        when = datetime.now().astimezone(timezone)
        current_value = compute_sun_strength(when, latitude, longitude)
        self.sun_strength_changed.emit(current_value)
        logging.debug(f'Sun strength has changed to {current_value}')

    def closeEvent(self, event):
        self.timer.stop()
        event.accept()
