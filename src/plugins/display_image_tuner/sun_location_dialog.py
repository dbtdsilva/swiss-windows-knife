from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QMessageBox, QWidget,
)
import pytz


class SunLocationDialog(QDialog):

    def __init__(
        self,
        parent: QWidget | None,
        latitude: float,
        longitude: float,
        timezone: str,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Sun-strength location")

        layout = QFormLayout(self)

        self.latitude_field = QLineEdit(str(latitude), self)
        layout.addRow("Latitude:", self.latitude_field)

        self.longitude_field = QLineEdit(str(longitude), self)
        layout.addRow("Longitude:", self.longitude_field)

        self.timezone_field = QLineEdit(timezone, self)
        self.timezone_field.setPlaceholderText("e.g. Europe/Zurich")
        layout.addRow("Timezone (IANA):", self.timezone_field)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        try:
            latitude = float(self.latitude_field.text())
            longitude = float(self.longitude_field.text())
        except ValueError:
            QMessageBox.warning(self, "Invalid input", "Latitude and longitude must be numeric.")
            return
        if not -90.0 <= latitude <= 90.0:
            QMessageBox.warning(self, "Invalid input", "Latitude must be between -90 and 90.")
            return
        if not -180.0 <= longitude <= 180.0:
            QMessageBox.warning(self, "Invalid input", "Longitude must be between -180 and 180.")
            return
        try:
            pytz.timezone(self.timezone_field.text())
        except pytz.UnknownTimeZoneError:
            QMessageBox.warning(
                self, "Invalid input",
                f"Unknown IANA timezone: {self.timezone_field.text()!r}",
            )
            return
        self.accept()

    def values(self) -> tuple[float, float, str]:
        return (
            float(self.latitude_field.text()),
            float(self.longitude_field.text()),
            self.timezone_field.text(),
        )
