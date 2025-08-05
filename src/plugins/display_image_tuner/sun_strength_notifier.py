

from datetime import datetime
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import QTimer, Signal
import pytz
from ...base.base_widget import BaseWidget
from pysolar import solar, radiation
import logging


class SunStrengthNotifier(BaseWidget):

    sun_strength_changed = Signal(int)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.timer = QTimer()
        self.timer.timeout.connect(self.calculate_sun_strength)
        self.timer.start(1000 * 60)

    def calculate_sun_strength(self):
        request = datetime.now().astimezone(pytz.timezone('Europe/Zurich'))
        altitude = solar.get_altitude(46.521410, 6.632273, request) + 5
        power = radiation.get_radiation_direct(request.astimezone(pytz.utc).replace(tzinfo=None), altitude)

        current_value = int(power / 6.0) if power < 600 else int(100)
        self.sun_strength_changed.emit(current_value)

        logging.debug(f'Sun strength has changed to {current_value}')

    def closeEvent(self, event):
        self.timer.stop()
        event.accept()
