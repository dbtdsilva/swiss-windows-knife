from swiss_windows_knife.base.user_settings import UserSettings


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
            settings.get("homeassistant_host", str),
            settings.get("homeassistant_port", int),
            settings.get("homeassistant_username", str),
            settings.get("homeassistant_password", str),
            settings.get("homeassistant_client_id", str),
            settings.get("homeassistant_device_name", str),
        )

    def save_to_settings(self, settings):
        settings.set("homeassistant_host", self.host)
        settings.set("homeassistant_port", self.port)
        settings.set("homeassistant_username", self.username)
        settings.set("homeassistant_password", self.password)
        settings.set("homeassistant_client_id", self.client_id)
        settings.set("homeassistant_device_name", self.device_name)

    def is_complete(self) -> bool:
        return all(
            v is not None and v != ""
            for v in (self.host, self.port, self.username, self.password, self.client_id, self.device_name)
        )
