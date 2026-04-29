from typing import override

from PySide6.QtCore import Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QWidget

from ...base.base_widget import BaseWidget
from ...base.config_panel import ConfigPanel
from ...base.user_settings import UserSettings
from .device_context import DeviceContext
from .entities import build_entity_registry
from .entity_settings import EntitySettings
from .mqtt_config import MqttConfig
from .mqtt_session import MqttSession
from .publisher import Publisher
from .sampler_runner import SamplerRunner


def build_command_registry(plugin):
    """Forward-declared; populated by Task 22."""
    return []


class HomeAssistantMqttPubPlugin(BaseWidget):

    display_name = "Home Assistant (MQTT)"

    def __init__(self, parent: QWidget | None) -> None:
        super().__init__(parent, is_enabled=True)
        self._user_settings = UserSettings.instance()
        self._entity_settings = EntitySettings(self._user_settings)
        self._sampler = SamplerRunner()
        self._entities = build_entity_registry()
        self._commands = build_command_registry(self)
        self._session: MqttSession | None = None
        self._publisher: Publisher | None = None

        cfg = MqttConfig.load_from_settings(self._user_settings)
        self.is_homeassistant_configured = cfg.is_complete()
        if self.is_homeassistant_configured:
            self._start_session(cfg)

    def _start_session(self, cfg: MqttConfig) -> None:
        ctx = DeviceContext(name=str(cfg.device_name))
        broker = dict(
            host=cfg.host, port=cfg.port,
            username=cfg.username, password=cfg.password,
            client_id=cfg.client_id,
        )
        self._session = MqttSession(broker_config=broker, availability_topic=ctx.availability_topic)
        self._publisher = Publisher(
            session=self._session, ctx=ctx, settings=self._entity_settings,
            sampler=self._sampler, entities=self._entities, commands=self._commands,
        )
        self._session.subscribe("homeassistant/status", self._publisher.on_ha_status)
        for command in self._commands:
            self._session.subscribe(
                ctx.command_topic(command.key),
                lambda payload, c=command: c.run(),
            )
        self._session.on_connected = self._publisher.on_connected
        self._session.start()

    @override
    def status_changed(self, status: bool) -> None:
        if status and self._session is None and self.is_homeassistant_configured:
            cfg = MqttConfig.load_from_settings(self._user_settings)
            self._start_session(cfg)
        elif not status and self._publisher is not None and self._session is not None:
            try:
                self._publisher.delete_all_for_current_device()
            finally:
                self._publisher.stop()
                self._session.stop()
                self._publisher = None
                self._session = None

    @override
    def retrieve_menus(self) -> list[QMenu | QAction]:
        menu = QMenu("Home Assistant", self)
        configured = QAction("Configured" if self.is_homeassistant_configured else "Not configured", self)
        configured.setEnabled(False)
        menu.addAction(configured)
        return [menu]

    @override
    def retrieve_config_panels(self) -> list[ConfigPanel]:
        from .mqtt_config_panel import MqttConfigPanel
        return [MqttConfigPanel(self)]

    @Slot()
    def reload_session(self) -> None:
        """Called by the config panel after apply()."""
        if self._publisher is not None and self._session is not None:
            self._publisher.stop()
            self._session.stop()
            self._publisher = None
            self._session = None
        cfg = MqttConfig.load_from_settings(self._user_settings)
        self.is_homeassistant_configured = cfg.is_complete()
        if self.is_homeassistant_configured and self.is_enabled():
            self._start_session(cfg)

    def closeEvent(self, event):
        if self._publisher is not None:
            self._publisher.stop()
        if self._session is not None:
            self._session.stop()
        event.accept()
