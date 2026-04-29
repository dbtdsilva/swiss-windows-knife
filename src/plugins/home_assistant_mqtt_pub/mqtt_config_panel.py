from PySide6.QtCore import Qt, QObject, Signal
from PySide6.QtWidgets import (
    QCheckBox, QFormLayout, QGridLayout, QGroupBox, QLabel,
    QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from ...base.config_panel import ConfigPanel
from ...base.user_settings import UserSettings
from .entities import build_entity_registry
from .entities.base import SampleResult
from .entity_settings import EntitySettings
from .mqtt_config import MqttConfig
from .sampler_runner import SamplerRunner


class _EntityRow(QObject):
    sample_arrived = Signal(object)

    def __init__(self, parent, entity, settings: EntitySettings) -> None:
        super().__init__(parent)
        self.entity = entity
        self.value_label = QLabel("Loading…", parent)
        self.unit_label = QLabel("", parent)
        self.publish_checkbox = QCheckBox(parent)
        self.publish_checkbox.setChecked(settings.is_publish_enabled(entity.key, entity.default_enabled))
        self.interval_field = QLineEdit(parent)
        if entity.is_event_driven:
            self.interval_field.setText("Event-driven")
            self.interval_field.setEnabled(False)
        else:
            self.interval_field.setText(str(settings.interval_s(entity.key, entity.default_interval_s or 30)))
        self.sample_arrived.connect(self._on_sample, Qt.ConnectionType.QueuedConnection)

    def _on_sample(self, result: SampleResult) -> None:
        if result.is_available:
            self.value_label.setText(str(result.value))
            self.unit_label.setText(result.unit)
        else:
            self.value_label.setText("Not available")
            self.publish_checkbox.setChecked(False)
            self.publish_checkbox.setEnabled(False)


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

        self._entity_settings = EntitySettings(self._user_settings)
        self._sampler = SamplerRunner()
        self.entity_rows: dict[str, _EntityRow] = {}

        entities_box = QGroupBox("Entities", self)
        grid = QGridLayout(entities_box)
        grid.addWidget(QLabel("Name", entities_box), 0, 0)
        grid.addWidget(QLabel("Value", entities_box), 0, 1)
        grid.addWidget(QLabel("Unit", entities_box), 0, 2)
        grid.addWidget(QLabel("Publish", entities_box), 0, 3)
        grid.addWidget(QLabel("Interval (s)", entities_box), 0, 4)

        for row_idx, entity in enumerate(build_entity_registry(), start=1):
            row = _EntityRow(entities_box, entity, self._entity_settings)
            self.entity_rows[entity.key] = row
            grid.addWidget(QLabel(entity.display_name, entities_box), row_idx, 0)
            grid.addWidget(row.value_label, row_idx, 1)
            grid.addWidget(row.unit_label, row_idx, 2)
            grid.addWidget(row.publish_checkbox, row_idx, 3)
            grid.addWidget(row.interval_field, row_idx, 4)
            self._sample_into_row(row)

        refresh = QPushButton("Refresh values", entities_box)
        refresh.clicked.connect(self._refresh_all)
        grid.addWidget(refresh, len(self.entity_rows) + 1, 0, 1, 5)
        outer.addWidget(entities_box)

        commands_box = QGroupBox("Commands", self)
        cgrid = QGridLayout(commands_box)
        self.command_checkboxes: dict[str, QCheckBox] = {}
        from .commands import build_command_registry
        for row_idx, command in enumerate(build_command_registry(self._plugin)):
            checkbox = QCheckBox(command.display_name, commands_box)
            checkbox.setChecked(self._entity_settings.is_command_enabled(command.key, command.default_enabled))
            self.command_checkboxes[command.key] = checkbox
            cgrid.addWidget(checkbox, row_idx, 0)
        outer.addWidget(commands_box)

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

        for key, row in self.entity_rows.items():
            self._entity_settings.set_publish_enabled(key, row.publish_checkbox.isChecked())
            if not row.entity.is_event_driven:
                try:
                    self._entity_settings.set_interval_s(key, int(row.interval_field.text()))
                except ValueError:
                    QMessageBox.warning(
                        self, "Invalid interval",
                        f"Interval for {row.entity.display_name} must be an integer.",
                    )
                    return False
        for key, checkbox in self.command_checkboxes.items():
            self._entity_settings.set_command_enabled(key, checkbox.isChecked())

        if self._plugin is not None and hasattr(self._plugin, "reload_session"):
            self._plugin.reload_session()
        return True

    def _sample_into_row(self, row: _EntityRow) -> None:
        self._sampler.submit(row.entity.sample, lambda result: row.sample_arrived.emit(result))

    def _refresh_all(self) -> None:
        for row in self.entity_rows.values():
            row.value_label.setText("Loading…")
            self._sample_into_row(row)

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
