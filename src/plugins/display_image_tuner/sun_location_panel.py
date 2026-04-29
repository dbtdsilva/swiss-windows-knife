from PySide6.QtWidgets import QMessageBox, QVBoxLayout, QWidget
import pytz

from ...base.config_panel import ConfigPanel
from ...base.user_settings import UserSettings
from .location_picker import LocationPickerWidget
from .sun_strength_notifier import (
    DEFAULT_LATITUDE, DEFAULT_LONGITUDE, DEFAULT_TIMEZONE, SunStrengthNotifier,
)


class SunLocationConfigPanel(ConfigPanel):

    title = "Sun strength"

    def __init__(
        self,
        sun_strength_notifier: SunStrengthNotifier,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._sun_strength = sun_strength_notifier
        self._user_settings = UserSettings.instance()

        try:
            latitude = float(self._user_settings.get('sun_latitude'))  # type: ignore[arg-type]
            longitude = float(self._user_settings.get('sun_longitude'))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            latitude, longitude = DEFAULT_LATITUDE, DEFAULT_LONGITUDE
        timezone = str(self._user_settings.get('sun_timezone') or DEFAULT_TIMEZONE)

        self.picker = LocationPickerWidget(latitude, longitude, timezone, self)

        layout = QVBoxLayout(self)
        layout.addWidget(self.picker)

    def apply(self) -> bool:
        latitude = self.picker.latitude()
        longitude = self.picker.longitude()
        timezone = self.picker.timezone()

        if not timezone:
            QMessageBox.warning(
                self, "Invalid input",
                "No timezone could be resolved for the selected coordinates. "
                "Pick a different point on the map.",
            )
            return False
        try:
            pytz.timezone(timezone)
        except pytz.UnknownTimeZoneError:
            QMessageBox.warning(
                self, "Invalid input",
                f"Unknown IANA timezone: {timezone!r}",
            )
            return False

        self._user_settings.set('sun_latitude', latitude)
        self._user_settings.set('sun_longitude', longitude)
        self._user_settings.set('sun_timezone', timezone)
        self._sun_strength.calculate_sun_strength()
        return True
