from __future__ import annotations

import logging

import requests
from PySide6.QtCore import QFile, QIODevice, QObject, Qt, QThread, QUrl, Signal, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QFormLayout, QLabel, QMessageBox, QVBoxLayout, QWidget
from timezonefinder import TimezoneFinder

_QWEBCHANNEL_JS_PATH = ":/qtwebchannel/qwebchannel.js"
_TILE_URL = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
_LEAFLET_CSS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
_LEAFLET_JS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
_IPAPI_URL = "https://ipinfo.io/json"
_IPAPI_TIMEOUT_S = 5

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


def _build_html(initial_lat: float, initial_lng: float, initial_zoom: int, qwebchannel_js: str) -> str:
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <link rel="stylesheet" href="{_LEAFLET_CSS}" />
  <style>
    html, body, #map {{ height: 100%; margin: 0; }}
    #map {{ background: #1e1e1e; }}
    .swk-detect-button {{
      background: white;
      border: 2px solid rgba(0, 0, 0, 0.2);
      border-radius: 4px;
      cursor: pointer;
      padding: 4px 8px;
      font: 12px/1.4 system-ui, sans-serif;
      box-shadow: 0 1px 2px rgba(0,0,0,0.2);
    }}
    .swk-detect-button:hover {{ background: #f4f4f4; }}
    .swk-detect-button:disabled {{ color: #888; cursor: progress; }}
  </style>
</head>
<body>
  <div id="map"></div>
  <script>{qwebchannel_js}</script>
  <script src="{_LEAFLET_JS}"></script>
  <script>
    const map = L.map('map').setView([{initial_lat}, {initial_lng}], {initial_zoom});
    L.tileLayer('{_TILE_URL}', {{
      attribution: '&copy; OpenStreetMap contributors',
      maxZoom: 18,
    }}).addTo(map);
    let marker = L.marker([{initial_lat}, {initial_lng}]).addTo(map);

    // Detect-from-IP control. The button is a real Leaflet control so it
    // sits cleanly with the zoom controls and follows the map's chrome.
    const DetectControl = L.Control.extend({{
      onAdd: function() {{
        const btn = L.DomUtil.create('button', 'swk-detect-button');
        btn.id = 'swk-detect';
        btn.type = 'button';
        btn.textContent = '📍 Detect';
        btn.title = 'Detect my location from IP';
        L.DomEvent.disableClickPropagation(btn);
        L.DomEvent.on(btn, 'click', function() {{
          if (window._swkBridge) window._swkBridge.request_geolocate();
        }});
        return btn;
      }},
      onRemove: function() {{}}
    }});
    new DetectControl({{ position: 'topright' }}).addTo(map);

    new QWebChannel(qt.webChannelTransport, function(channel) {{
      const bridge = channel.objects.bridge;
      window._swkBridge = bridge;
      map.on('click', function(e) {{
        marker.setLatLng(e.latlng);
        bridge.set_coordinates(e.latlng.lat, e.latlng.lng);
      }});
    }});

    // Helpers callable from Python via runJavaScript.
    window.swkSetMarker = function(lat, lng) {{
      marker.setLatLng([lat, lng]);
      map.setView([lat, lng], Math.max(map.getZoom(), 11));
    }};
    window.swkSetDetectButtonState = function(enabled, label) {{
      const btn = document.getElementById('swk-detect');
      if (!btn) return;
      btn.disabled = !enabled;
      btn.textContent = label;
    }};
  </script>
</body>
</html>"""


class _MapBridge(QObject):
    coordinates_picked = Signal(float, float)
    geolocate_requested = Signal()

    @Slot(float, float)
    def set_coordinates(self, lat: float, lng: float) -> None:
        self.coordinates_picked.emit(lat, lng)

    @Slot()
    def request_geolocate(self) -> None:
        self.geolocate_requested.emit()


class _IpGeolocateWorker(QObject):
    finished = Signal(object)

    @Slot()
    def run(self) -> None:
        try:
            response = requests.get(_IPAPI_URL, timeout=_IPAPI_TIMEOUT_S)
            response.raise_for_status()
            data = response.json()
            # ipinfo.io returns lat/lng as a single "lat,lng" string under
            # the `loc` key.
            loc = str(data["loc"])
            lat_s, lng_s = loc.split(",", 1)
            lat = float(lat_s)
            lng = float(lng_s)
            tz = str(data.get("timezone") or "")
        except Exception:
            logging.exception("IP geolocation failed")
            self.finished.emit(None)
            return
        self.finished.emit((lat, lng, tz))


class LocationPickerWidget(QWidget):
    """Interactive OpenStreetMap-backed coordinate + timezone picker.

    Uses QWebEngineView + Leaflet (loaded from a CDN) to render the map
    and capture clicks; the page talks to Python via QWebChannel. A
    "📍 Detect" Leaflet control kicks off an IP-based geolocation lookup
    that updates the marker without leaving the map.

    The QWebEngineView is constructed eagerly in `__init__` rather than
    lazily on first `showEvent`. Lazy construction during a QTabWidget
    tab switch hangs the GUI on Windows for any heavy native sub-window;
    eager construction sidesteps that race.
    """

    location_changed = Signal(float, float, str)

    def __init__(
        self,
        initial_lat: float,
        initial_lng: float,
        initial_timezone: str,
        parent: QWidget | None = None,
        initial_zoom: int = 6,
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
        self._bridge.geolocate_requested.connect(self._on_geolocate_requested)
        self._channel.registerObject("bridge", self._bridge)
        self._view.page().setWebChannel(self._channel)

        html = _build_html(self._lat, self._lng, int(initial_zoom), _read_qwebchannel_js())
        self._view.setHtml(html, QUrl("https://maps.local/"))

        self._geolocate_thread: QThread | None = None

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

    def set_location(self, lat: float, lng: float, timezone: str | None = None) -> None:
        """Programmatically move the marker (also pans the Leaflet map)."""
        self._lat = float(lat)
        self._lng = float(lng)
        if timezone:
            self._timezone = str(timezone)
        else:
            self._timezone = coordinates_to_timezone(self._lat, self._lng) or ""
        self._coords_label.setText(self._format_coords(self._lat, self._lng))
        self._timezone_label.setText(self._timezone or "(unknown)")
        self._view.page().runJavaScript(f"window.swkSetMarker({self._lat}, {self._lng});")
        self.location_changed.emit(self._lat, self._lng, self._timezone)

    @Slot(float, float)
    def _on_coordinates_picked(self, lat: float, lng: float) -> None:
        self._lat = lat
        self._lng = lng
        self._timezone = coordinates_to_timezone(lat, lng) or ""
        self._coords_label.setText(self._format_coords(lat, lng))
        self._timezone_label.setText(self._timezone or "(unknown)")
        self.location_changed.emit(lat, lng, self._timezone)

    @Slot()
    def _on_geolocate_requested(self) -> None:
        if self._geolocate_thread is not None:
            return  # already in flight
        self._set_detect_button_state(False, "📍 Detecting…")

        thread = QThread(self)
        worker = _IpGeolocateWorker()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_geolocate_finished, Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        # Anchor the worker against PySide6 GC: signal connections are
        # weak-ref'd, so without this the worker can be collected before
        # `started` fires and `run` would silently never execute.
        thread._geolocate_worker_anchor = worker  # type: ignore[attr-defined]
        thread.start()
        self._geolocate_thread = thread

    @Slot(object)
    def _on_geolocate_finished(self, result) -> None:
        self._set_detect_button_state(True, "📍 Detect")
        self._geolocate_thread = None
        if result is None:
            QMessageBox.warning(
                self, "Couldn't detect location",
                "Failed to look up your location from the network. "
                "See logs for details.",
            )
            return
        lat, lng, tz = result
        self.set_location(lat, lng, tz)

    def _set_detect_button_state(self, enabled: bool, label: str) -> None:
        # Single-quoted JS string literal; sanitise: the label is hard-coded
        # so no escaping needed here, but keep the call defensive.
        safe_label = label.replace("\\", "\\\\").replace("'", "\\'")
        js = f"window.swkSetDetectButtonState({'true' if enabled else 'false'}, '{safe_label}');"
        self._view.page().runJavaScript(js)

    @staticmethod
    def _format_coords(lat: float, lng: float) -> str:
        return f"{lat:.5f}, {lng:.5f}"
