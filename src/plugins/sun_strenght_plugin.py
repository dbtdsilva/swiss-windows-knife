

from datetime import datetime
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import QTimer, Signal
import pytz
from .base_plugin import BasePlugin
from pysolar import solar, radiation
import logging


class SunStrenghtPlugin(BasePlugin):

    sun_strength_changed = Signal(int)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.timer = QTimer()
        self.timer.timeout.connect(self.calculate_sun_strenght)
        self.timer.start(1000 * 60)

    def calculate_sun_strenght(self):
        # Apply functions based on the location and sun strenght
        request = datetime.now().astimezone(pytz.timezone('Europe/Zurich'))
        altitude = solar.get_altitude(46.521410, 6.632273, request) + 5
        power = radiation.get_radiation_direct(request, altitude)

        current_value = int(power / 6.0) if power < 600 else int(100)
        self.sun_strength_changed.emit(current_value)

        logging.debug(f'Sun strenght has changed to {current_value}')
