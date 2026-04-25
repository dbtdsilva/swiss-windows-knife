from PySide6.QtWidgets import QFormLayout, QLineEdit, QWidget

from ...base.config_panel import ConfigPanel
from ...base.user_settings import UserSettings
from .mqtt_config import MqttConfig


class MqttConfigPanel(ConfigPanel):

    title = "Home Assistant (MQTT)"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._user_settings = UserSettings.instance()
        config = MqttConfig.load_from_settings(self._user_settings)

        layout = QFormLayout(self)

        self.login_field = QLineEdit(self)
        if config.username is not None:
            self.login_field.setText(str(config.username))
        layout.addRow("Login:", self.login_field)

        self.password_field = QLineEdit(self)
        self.password_field.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        if config.password is not None:
            self.password_field.setText(str(config.password))
        layout.addRow("Password:", self.password_field)

        self.host_field = QLineEdit(self)
        if config.host is not None:
            self.host_field.setText(str(config.host))
        layout.addRow("Host:", self.host_field)

        self.port_field = QLineEdit(self)
        if config.port is not None:
            self.port_field.setText(str(config.port))
        layout.addRow("Port:", self.port_field)

        self.client_id_field = QLineEdit(self)
        if config.client_id is not None:
            self.client_id_field.setText(str(config.client_id))
        layout.addRow("Client ID:", self.client_id_field)

    def apply(self) -> bool:
        config = MqttConfig(
            host=self.host_field.text(),
            port=self.port_field.text(),
            username=self.login_field.text(),
            password=self.password_field.text(),
            client_id=self.client_id_field.text(),
        )
        config.save_to_settings(self._user_settings)
        return True
