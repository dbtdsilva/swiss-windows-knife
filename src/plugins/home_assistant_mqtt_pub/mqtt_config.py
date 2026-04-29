from src.base.user_settings import UserSettings


class MqttConfig:
    def __init__(self, host, port, username, password, client_id, device_name=None):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.client_id = client_id
        self.device_name = device_name

    @staticmethod
    def load_from_settings(settings: UserSettings):
        return MqttConfig(
            settings.get("homeassistant_host"),
            settings.get("homeassistant_port"),
            settings.get("homeassistant_username"),
            settings.get("homeassistant_password"),
            settings.get("homeassistant_client_id"),
            settings.get("homeassistant_device_name"),
        )

    def save_to_settings(self, settings):
        settings.set("homeassistant_host", self.host)
        settings.set("homeassistant_port", int(self.port) if self.port not in (None, "") else self.port)
        settings.set("homeassistant_username", self.username)
        settings.set("homeassistant_password", self.password)
        settings.set("homeassistant_client_id", self.client_id)
        settings.set("homeassistant_device_name", self.device_name)

    def is_complete(self) -> bool:
        return all(
            v not in (None, "")
            for v in (self.host, self.port, self.username, self.password, self.client_id, self.device_name)
        )
