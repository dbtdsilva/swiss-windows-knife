import pytz
from PySide6.QtWidgets import QMessageBox, QVBoxLayout, QWidget

from ...base.config_panel import ConfigPanel
from ...base.user_settings import UserSettings
from .location_picker import LocationPickerWidget
from .sun_strength_notifier import (
    DEFAULT_LATITUDE,
    DEFAULT_LONGITUDE,
    DEFAULT_TIMEZONE,
    SunStrengthNotifier,
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

        has_saved_location = (
            self._user_settings.has_key('sun_latitude')
            and self._user_settings.has_key('sun_longitude')
        )
        latitude = self._user_settings.get_optional_float('sun_latitude')
        longitude = self._user_settings.get_optional_float('sun_longitude')
        if latitude is None or longitude is None:
            latitude, longitude = DEFAULT_LATITUDE, DEFAULT_LONGITUDE
            has_saved_location = False
        timezone = self._user_settings.get_str('sun_timezone', DEFAULT_TIMEZONE)

        # If the user has previously saved a location, open zoomed in so
        # they can see the placed marker in context. Otherwise show a
        # wider view to make the initial picking easier.
        initial_zoom = 11 if has_saved_location else 6
        self.picker = LocationPickerWidget(latitude, longitude, timezone, self, initial_zoom=initial_zoom)

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
