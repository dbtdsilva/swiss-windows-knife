from PySide6.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox


class MqttBrokerConfigDialog(QDialog):
    def __init__(self, parent=None):
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

        # OK and Cancel buttons
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def get_data(self):
        return {
            'login': self.login_field.text(),
            'password': self.password_field.text(),
            'host': self.host_field.text(),
            'port': self.port_field.text()
        }
