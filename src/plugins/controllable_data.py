from PySide6.QtCore import QSettings
import monitorcontrol
import logging

from app_info import APP_INFO


class ControllableData:

    logger = logging.getLogger(__name__)

    def __init__(self) -> None:
        self._settings = QSettings(APP_INFO.APP_NAME, 'ControllableData')
        self.logger.info(f"ControllableData object loaded into {self._settings.fileName()}")

        self._input_on_disconnect = self._settings.value('input_on_disconnect') \
            if self._settings.contains('input_on_disconnect') else monitorcontrol.InputSource.HDMI1
        self._input_on_connect = self._settings.value('input_on_connect') \
            if self._settings.contains('input_on_connect') else monitorcontrol.InputSource.DP1

        self._brightness = self._settings.value('brightness') if self._settings.contains('brightness') else None
        self._contrast = self._settings.value('contrast') if self._settings.contains('contrast') else 90

        self.logger.info(f"Starting with the 'input_on_connect' set to {self.input_on_disconnect}")
        self.logger.info(f"Starting with the 'input_on_disconnect' set to {self.input_on_disconnect}")
        self.logger.info(f"Starting with the 'brightness' set to {self.brightness}")
        self.logger.info(f"Starting with the 'contrast' set to {self.contrast}")

    @property
    def brightness(self):
        return self._brightness

    @brightness.setter
    def brightness(self, brightness):
        self.logger.info(f'Setting brightness to {brightness}')
        self._brightness = brightness
        self._settings.setValue('brightness', brightness)

    @property
    def contrast(self):
        return self._contrast

    @contrast.setter
    def contrast(self, contrast):
        self.logger.info(f'Setting contrast to {contrast}')
        self._contrast = contrast
        self._settings.setValue('contrast', contrast)

    @property
    def input_on_disconnect(self):
        return self._input_on_disconnect

    @input_on_disconnect.setter
    def input_on_disconnect(self, input_on_disconnect):
        self._input_on_disconnect = input_on_disconnect
        self._settings.setValue('input_on_disconnect', input_on_disconnect)

    @property
    def input_on_connect(self):
        return self._input_on_connect

    @input_on_connect.setter
    def input_on_connect(self, input_on_connect):
        self._input_on_connect = input_on_connect
        self._settings.setValue('input_on_connect', input_on_connect)
