from typing import override

from PySide6.QtCore import Q_ARG, QMetaObject, Qt, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QWidget

from ...base.base_widget import BaseWidget
from ...base.config_panel import ConfigPanel
from ...base.health import HealthState
from ...base.user_settings import UserSettings
from .commands import build_command_registry
from .device_context import DeviceContext
from .entities import build_entity_registry
from .entity_settings import EntitySettings
from .mqtt_config import MqttConfig
from .mqtt_session import MqttSession
from .publisher import Publisher
from .sampler_runner import SamplerRunner


class HomeAssistantMqttPubPlugin(BaseWidget):

    display_name = "Home Assistant (MQTT)"
    description = (
        "Publishes Windows sensors and lock/sleep/shutdown commands to "
        "Home Assistant via MQTT discovery."
    )

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
            self._set_health(HealthState.WARNING, "Connecting…")
            self._start_session(cfg)
        else:
            self._set_health(HealthState.WARNING, "Not configured")

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
        self._session.subscribe("homeassistant/status", self._dispatch_ha_status)
        for command in self._commands:
            self._session.subscribe(
                ctx.command_topic(command.key),
                lambda payload, c=command: c.run(),
            )
        self._session.on_connected = self._dispatch_on_connected
        self._session.on_disconnected = self._dispatch_on_disconnected
        self._session.start()

    def _dispatch_on_connected(self) -> None:
        QMetaObject.invokeMethod(self, "_run_on_connected", Qt.ConnectionType.QueuedConnection)

    def _dispatch_on_disconnected(self) -> None:
        QMetaObject.invokeMethod(self, "_run_on_disconnected", Qt.ConnectionType.QueuedConnection)

    def _dispatch_ha_status(self, payload: str) -> None:
        QMetaObject.invokeMethod(
            self, "_run_on_ha_status",
            Qt.ConnectionType.QueuedConnection, Q_ARG(str, payload),
        )

    @Slot()
    def _run_on_connected(self) -> None:
        self._set_health(HealthState.OK, "Connected")
        if self._publisher is not None:
            self._publisher.on_connected()

    @Slot()
    def _run_on_disconnected(self) -> None:
        self._set_health(HealthState.WARNING, "Disconnected")

    @Slot(str)
    def _run_on_ha_status(self, payload: str) -> None:
        if self._publisher is not None:
            self._publisher.on_ha_status(payload)

    @override
    def status_changed(self, status: bool) -> None:
        if status and self._session is None and self.is_homeassistant_configured:
            cfg = MqttConfig.load_from_settings(self._user_settings)
            self._set_health(HealthState.WARNING, "Connecting…")
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
        return []

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
            self._set_health(HealthState.WARNING, "Connecting…")
            self._start_session(cfg)
        elif not self.is_homeassistant_configured:
            self._set_health(HealthState.WARNING, "Not configured")

    def closeEvent(self, event):
        if self._publisher is not None:
            self._publisher.stop()
        if self._session is not None:
            self._session.stop()
        event.accept()
