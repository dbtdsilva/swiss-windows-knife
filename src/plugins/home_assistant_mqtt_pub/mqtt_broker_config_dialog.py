from PySide6.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox
from .mqtt_config import MqttConfig

class MqttBrokerConfigDialog(QDialog):
    def __init__(self, parent = None, mqtt_config: MqttConfig = None):
        super().__init__(parent)

        # Set up the dialog
        self.setWindowTitle("Connection Settings")

        # Create form layout
        layout = QFormLayout(self)

        # Login field
        self.login_field = QLineEdit(self)
        layout.addRow("Login:", self.login_field)

        # Password field
        self.password_field = QLineEdit(self)
        self.password_field.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        layout.addRow("Password:", self.password_field)

        # Host field
        self.host_field = QLineEdit(self)
        layout.addRow("Host:", self.host_field)

        # Port field
        self.port_field = QLineEdit(self)
        layout.addRow("Port:", self.port_field)

        self.client_id_field = QLineEdit(self)
        layout.addRow("Client ID:", self.client_id_field)

        if mqtt_config is not None:
            self.host_field.setText(mqtt_config.host)
            self.port_field.setText(str(mqtt_config.port))
            self.login_field.setText(mqtt_config.username)
            self.password_field.setText(mqtt_config.password)
            self.client_id_field.setText(mqtt_config.client_id)

        # OK and Cancel buttons
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def get_data(self):
        return MqttConfig(self.host_field.text(),
                          self.port_field.text(),
                          self.login_field.text(),
                          self.password_field.text(),
                          self.client_id_field.text())
