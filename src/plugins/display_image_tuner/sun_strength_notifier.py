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

        request = datetime.now().astimezone(timezone)
        altitude = solar.get_altitude(latitude, longitude, request) + ALTITUDE_OFFSET_DEG
        power = radiation.get_radiation_direct(request.astimezone(pytz.utc).replace(tzinfo=None), altitude)

        current_value = int(power / 6.0) if power < 600 else int(100)
        self.sun_strength_changed.emit(current_value)

        logging.debug(f'Sun strength has changed to {current_value}')

    def closeEvent(self, event):
        self.timer.stop()
        event.accept()
