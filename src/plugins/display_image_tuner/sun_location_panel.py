from PySide6.QtWidgets import QFormLayout, QLineEdit, QMessageBox, QWidget
import pytz

from ...base.config_panel import ConfigPanel
from ...base.user_settings import UserSettings
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

        layout = QFormLayout(self)

        try:
            latitude = float(self._user_settings.get('sun_latitude'))  # type: ignore[arg-type]
            longitude = float(self._user_settings.get('sun_longitude'))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            latitude, longitude = DEFAULT_LATITUDE, DEFAULT_LONGITUDE
        timezone = str(self._user_settings.get('sun_timezone') or DEFAULT_TIMEZONE)

        self.latitude_field = QLineEdit(str(latitude), self)
        layout.addRow("Latitude:", self.latitude_field)

        self.longitude_field = QLineEdit(str(longitude), self)
        layout.addRow("Longitude:", self.longitude_field)

        self.timezone_field = QLineEdit(timezone, self)
        self.timezone_field.setPlaceholderText("e.g. Europe/Zurich")
        layout.addRow("Timezone (IANA):", self.timezone_field)

    def apply(self) -> bool:
        try:
            latitude = float(self.latitude_field.text())
            longitude = float(self.longitude_field.text())
        except ValueError:
            QMessageBox.warning(self, "Invalid input", "Latitude and longitude must be numeric.")
            return False
        if not -90.0 <= latitude <= 90.0:
            QMessageBox.warning(self, "Invalid input", "Latitude must be between -90 and 90.")
            return False
        if not -180.0 <= longitude <= 180.0:
            QMessageBox.warning(self, "Invalid input", "Longitude must be between -180 and 180.")
            return False
        try:
            pytz.timezone(self.timezone_field.text())
        except pytz.UnknownTimeZoneError:
            QMessageBox.warning(
                self, "Invalid input",
                f"Unknown IANA timezone: {self.timezone_field.text()!r}",
            )
            return False

        self._user_settings.set('sun_latitude', latitude)
        self._user_settings.set('sun_longitude', longitude)
        self._user_settings.set('sun_timezone', self.timezone_field.text())
        self._sun_strength.calculate_sun_strength()
        return True
