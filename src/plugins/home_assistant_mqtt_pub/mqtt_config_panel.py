from PySide6.QtWidgets import (
    QFormLayout, QGroupBox, QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from ...base.config_panel import ConfigPanel
from ...base.user_settings import UserSettings
from .mqtt_config import MqttConfig


class MqttConfigPanel(ConfigPanel):

    title = "Home Assistant (MQTT)"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._user_settings = UserSettings.instance()
        self._plugin = parent  # may be None in tests
        cfg = MqttConfig.load_from_settings(self._user_settings)

        outer = QVBoxLayout(self)

        broker_box = QGroupBox("Broker", self)
        bform = QFormLayout(broker_box)
        self.login_field = QLineEdit(broker_box)
        if cfg.username is not None:
            self.login_field.setText(str(cfg.username))
        bform.addRow("Login:", self.login_field)
        self.password_field = QLineEdit(broker_box)
        self.password_field.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        if cfg.password is not None:
            self.password_field.setText(str(cfg.password))
        bform.addRow("Password:", self.password_field)
        self.host_field = QLineEdit(broker_box)
        if cfg.host is not None:
            self.host_field.setText(str(cfg.host))
        bform.addRow("Host:", self.host_field)
        self.port_field = QLineEdit(broker_box)
        if cfg.port is not None:
            self.port_field.setText(str(cfg.port))
        bform.addRow("Port:", self.port_field)
        self.client_id_field = QLineEdit(broker_box)
        if cfg.client_id is not None:
            self.client_id_field.setText(str(cfg.client_id))
        bform.addRow("Client ID:", self.client_id_field)
        outer.addWidget(broker_box)

        device_box = QGroupBox("Device", self)
        dform = QFormLayout(device_box)
        self.device_name_field = QLineEdit(device_box)
        if cfg.device_name is not None:
            self.device_name_field.setText(str(cfg.device_name))
        dform.addRow("Name:", self.device_name_field)
        self.forget_button = QPushButton("Forget device in Home Assistant", device_box)
        self.forget_button.clicked.connect(self._on_forget_device)
        dform.addRow(self.forget_button)
        outer.addWidget(device_box)

    def apply(self) -> bool:
        port_text = self.port_field.text().strip()
        try:
            port_int = int(port_text)
        except ValueError:
            QMessageBox.warning(self, "Invalid port", "Port must be an integer.")
            return False
        device_name = self.device_name_field.text().strip()
        if not device_name:
            QMessageBox.warning(self, "Invalid device name", "Device name cannot be empty.")
            return False

        cfg = MqttConfig(
            host=self.host_field.text(),
            port=port_int,
            username=self.login_field.text(),
            password=self.password_field.text(),
            client_id=self.client_id_field.text(),
            device_name=device_name,
        )
        cfg.save_to_settings(self._user_settings)
        if self._plugin is not None and hasattr(self._plugin, "reload_session"):
            self._plugin.reload_session()
        return True

    def _on_forget_device(self) -> None:
        confirm = QMessageBox.question(
            self, "Forget device?",
            "This will remove the device and all its entities from Home Assistant.\n"
            "Continue?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        if self._plugin is None:
            return
        publisher = getattr(self._plugin, "_publisher", None)
        if publisher is None:
            return
        publisher.delete_all_for_current_device()
        from .entity_settings import EntitySettings
        es = EntitySettings(self._user_settings)
        for entity in getattr(self._plugin, "_entities", []):
            es.set_publish_enabled(entity.key, False)
