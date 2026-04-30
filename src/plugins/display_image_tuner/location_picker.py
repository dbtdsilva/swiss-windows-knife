from __future__ import annotations

from PySide6.QtCore import QUrl, Signal, Slot
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QFormLayout, QLabel, QVBoxLayout, QWidget
from timezonefinder import TimezoneFinder

_QML_URL = QUrl("qrc:/qml/MapPicker.qml")

_tz_finder: TimezoneFinder | None = None


def coordinates_to_timezone(latitude: float, longitude: float) -> str | None:
    """Resolve an IANA timezone name from coordinates, or None if no match."""
    global _tz_finder
    if _tz_finder is None:
        _tz_finder = TimezoneFinder()
    return _tz_finder.timezone_at(lat=latitude, lng=longitude)


class LocationPickerWidget(QWidget):
    """Interactive OpenStreetMap-backed coordinate + timezone picker.

    Embeds a small Qt Quick scene (`MapPicker.qml`, baked into the qrc
    resources) via `QQuickWidget`. The QML uses Qt's native QtLocation /
    QtPositioning — no Chromium, no QWebChannel, no separate process.
    QML emits `coordinatesPicked(lat, lng)` on tap; we propagate as
    `location_changed(lat, lng, timezone)` after timezone resolution.
    The Qt Quick scene is built lazily on first show so headless tests
    can construct the widget without instantiating it.
    """

    location_changed = Signal(float, float, str)

    def __init__(
        self,
        initial_lat: float,
        initial_lng: float,
        initial_timezone: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._lat = float(initial_lat)
        self._lng = float(initial_lng)
        self._timezone = str(initial_timezone)

        self._coords_label = QLabel(self._format_coords(self._lat, self._lng))
        self._timezone_label = QLabel(self._timezone or "(unknown)")

        self._quick = QQuickWidget(self)
        self._quick.setMinimumHeight(360)
        self._quick.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
        self._quick.statusChanged.connect(self._on_quick_status_changed)
        self._quick.setSource(_QML_URL)

        layout = QVBoxLayout(self)
        layout.addWidget(self._quick, 1)
        info = QFormLayout()
        info.addRow("Coordinates:", self._coords_label)
        info.addRow("Timezone:", self._timezone_label)
        layout.addLayout(info)

    def latitude(self) -> float:
        return self._lat

    def longitude(self) -> float:
        return self._lng

    def timezone(self) -> str:
        return self._timezone

    def _on_quick_status_changed(self, status: QQuickWidget.Status) -> None:
        if status != QQuickWidget.Status.Ready:
            return
        root = self._quick.rootObject() if self._quick is not None else None
        if root is None:
            return
        root.setProperty("markerLat", self._lat)
        root.setProperty("markerLng", self._lng)
        root.coordinatesPicked.connect(self._on_coordinates_picked)

    @Slot(float, float)
    def _on_coordinates_picked(self, lat: float, lng: float) -> None:
        self._lat = lat
        self._lng = lng
        self._timezone = coordinates_to_timezone(lat, lng) or ""
        self._coords_label.setText(self._format_coords(lat, lng))
        self._timezone_label.setText(self._timezone or "(unknown)")
        self.location_changed.emit(lat, lng, self._timezone)

    @staticmethod
    def _format_coords(lat: float, lng: float) -> str:
        return f"{lat:.4f}, {lng:.4f}"
