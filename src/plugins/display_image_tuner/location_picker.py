from __future__ import annotations

from PySide6.QtCore import QFile, QIODevice, QObject, QUrl, Signal, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QFormLayout, QLabel, QVBoxLayout, QWidget

from timezonefinder import TimezoneFinder


_QWEBCHANNEL_JS_PATH = ":/qtwebchannel/qwebchannel.js"
_TILE_URL = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
_LEAFLET_CSS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
_LEAFLET_JS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"

_tz_finder: TimezoneFinder | None = None


def coordinates_to_timezone(latitude: float, longitude: float) -> str | None:
    """Resolve an IANA timezone name from coordinates, or None if no match."""
    global _tz_finder
    if _tz_finder is None:
        _tz_finder = TimezoneFinder()
    return _tz_finder.timezone_at(lat=latitude, lng=longitude)


def _read_qwebchannel_js() -> str:
    f = QFile(_QWEBCHANNEL_JS_PATH)
    if not f.open(QIODevice.OpenModeFlag.ReadOnly | QIODevice.OpenModeFlag.Text):
        raise RuntimeError(f"Could not open {_QWEBCHANNEL_JS_PATH}")
    try:
        return bytes(f.readAll()).decode("utf-8")
    finally:
        f.close()


def _build_html(initial_lat: float, initial_lng: float, qwebchannel_js: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <link rel="stylesheet" href="{_LEAFLET_CSS}" />
  <style>
    html, body, #map {{ height: 100%; margin: 0; }}
    #map {{ background: #1e1e1e; }}
  </style>
</head>
<body>
  <div id="map"></div>
  <script>{qwebchannel_js}</script>
  <script src="{_LEAFLET_JS}"></script>
  <script>
    const map = L.map('map').setView([{initial_lat}, {initial_lng}], 6);
    L.tileLayer('{_TILE_URL}', {{
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 18,
    }}).addTo(map);
    let marker = L.marker([{initial_lat}, {initial_lng}]).addTo(map);

    new QWebChannel(qt.webChannelTransport, function(channel) {{
      const bridge = channel.objects.bridge;
      map.on('click', function(e) {{
        marker.setLatLng(e.latlng);
        bridge.set_coordinates(e.latlng.lat, e.latlng.lng);
      }});
    }});
  </script>
</body>
</html>"""


class _MapBridge(QObject):
    coordinates_picked = Signal(float, float)

    @Slot(float, float)
    def set_coordinates(self, lat: float, lng: float) -> None:
        self.coordinates_picked.emit(lat, lng)


class LocationPickerWidget(QWidget):
    """Interactive OpenStreetMap-backed coordinate + timezone picker.

    Emits `location_changed(lat, lng, timezone)` when the user clicks a
    new location on the map. `timezone` is the IANA name resolved from
    the coordinates (empty string if no match).
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

        self._view = QWebEngineView(self)
        self._view.setMinimumHeight(360)

        self._channel = QWebChannel(self._view.page())
        self._bridge = _MapBridge(self)
        self._bridge.coordinates_picked.connect(self._on_coordinates_picked)
        self._channel.registerObject("bridge", self._bridge)
        self._view.page().setWebChannel(self._channel)

        html = _build_html(self._lat, self._lng, _read_qwebchannel_js())
        self._view.setHtml(html, QUrl("https://maps.local/"))

        layout = QVBoxLayout(self)
        layout.addWidget(self._view, 1)
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
        return f"{lat:.5f}, {lng:.5f}"
