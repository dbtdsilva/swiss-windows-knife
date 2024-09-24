from typing import override
from PySide6.QtCore import Slot, QTimer
from PySide6.QtWidgets import QWidget, QMenu, QDialog
from PySide6.QtGui import QAction
import json

from src.base.user_settings import UserSettings

from ...app_info import APP_INFO
from ...base.base_widget import BaseWidget

import logging
import paho.mqtt.client as mqtt_client
import paho.mqtt.enums as mqtt_enums

from .mqtt_broker_config_dialog import MqttBrokerConfigDialog


class HomeAssistantMqttPubPlugin(BaseWidget):

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent, is_enabled=True)

        self.user_settings = UserSettings.instance()
        if not self.user_settings.has_key('homeassistant_host') or \
                not self.user_settings.has_key('homeassistant_port') or \
                not self.user_settings.has_key('homeassistant_client_id') or \
                not self.user_settings.has_key('homeassistant_username') or \
                not self.user_settings.has_key('homeassistant_password'):
            self.is_homeassistant_configured = False
        else:
            self.is_homeassistant_configured = True
            self.client = mqtt_client.Client(
                client_id=str(self.user_settings.get('homeassistant_client_id')),
                protocol=mqtt_client.MQTTv5,
                callback_api_version=mqtt_enums.CallbackAPIVersion.VERSION2)
            self.client.will_set("homeassistant/sensor/camelotaorus/availability", "offline", qos=0, retain=False)
            self.client.on_connect = self.on_connect
            self.client.on_message = self.on_message

            self.client.username_pw_set(
                str(self.user_settings.get('homeassistant_username')),
                str(self.user_settings.get('homeassistant_password')))

            self.sub_topic = "homeassistant/status"
            self.timer = QTimer()
            self.timer.timeout.connect(self.publish_message)
            self.timer.start(1000 * 15)

            self.toggle_mqtt_client(True)

    @override
    def status_changed(self):
        self.toggle_mqtt_client(self.is_enabled() and self.is_homeassistant_configured)

    def toggle_mqtt_client(self, status: bool):
        if status:
            host = self.user_settings.get('homeassistant_host')
            port = self.user_settings.get('homeassistant_port')
            if not isinstance(port, int) or not isinstance(host, str):
                return

            self.client.connect(host=host, port=port, keepalive=30)
            self.client.loop_start()
        elif self.client.is_connected():
            self.client.loop_stop()
            self.client.disconnect()

    @override
    def retrieve_menus(self) -> list[QMenu]:
        menu = QMenu('Home Assistant', self)
        enable_config = QAction('Enabled', self)
        enable_config.setCheckable(True)
        enable_config.setChecked(True)
        menu.addAction(enable_config)
        config_action = QAction('Configuration', self)
        config_action.triggered.connect(self.open_config)
        menu.addAction(config_action)
        menu.addSeparator()
        subscribe_action = QAction('Subscribe...', self)
        subscribe_action.triggered.connect(self.open_config)
        subscribe_action.setCheckable(True)
        subscribe_action.setChecked(True)
        publish_action = QAction('Publish local info', self)
        publish_action.triggered.connect(self.open_config)
        publish_action.setCheckable(True)
        publish_action.setChecked(True)
        menu.addActions([subscribe_action, publish_action])
        return [menu]

    @Slot()
    def open_config(self) -> None:
        dialog = MqttBrokerConfigDialog(self)
        result = dialog.exec()
        if result == QDialog.DialogCode.Accepted:
            pass

    def on_connect(self, client, userdata, flags, rc, properties):
        if rc == 0:
            logging.info(f"Connected to MQTT broker on {client.host}")
            client.subscribe(self.sub_topic)
        else:
            logging.error("Failed to connect, return code %d\n", rc)

    def on_disconnect(self, client, userdata, flags, rc, properties):
        logging.info(f"Disconnected from MQTT broker on {client.host}")

    def on_subscribe(self, client, userdata, mid, granted_qos, properties):
        logging.info(f"Subscribed: {mid} QoS: {granted_qos}")

    def on_message(self, client, userdata, msg):
        logging.debug(f'Received message on {msg.topic} with retain {msg.retain} at '
                      f'{msg.timestamp} with the message: {msg.payload.decode()}')
        if msg.topic == 'homeassistant/status':
            self.update_homeassistant_status(msg.payload.decode() == 'online')

    def update_homeassistant_status(self, status: bool) -> None:
        self.is_homeassistant_online = status
        if not self.is_homeassistant_online:
            return

        self.client.publish('homeassistant/sensor/camelotaorus/test/config', payload=json.dumps({
            "name": "test",
            "state_topic": "homeassistant/sensor/camelotaorus/state",
            "device_class": "temperature",
            "icon": "mdi:clock-time-three-outline",
            "unit_of_measurement": "°C",
            "value_template": "{{ value_json.temperature}}",
            "unique_id": "120f167c-f699-4109-88d9-34365a14814e",
            "object_id": "camelotaorus_test",
            "availability_topic": "homeassistant/sensor/camelotaorus/availability",
            "device": {
                "identifiers": "CamelotAorus",
                "manufacturer": "SwissWindowsKnife by Diogo Silva",
                "model": "Microsoft Windows NT 10.0.22631.0",
                "name": "CamelotAorus",
                "sw_version": APP_INFO.APP_VERSION
            }
        }))

        self.client.publish("homeassistant/sensor/camelotaorus/availability", "online", qos=0, retain=False)

    @Slot()
    def publish_message(self):
        if self.is_homeassistant_online:
            import random
            # self.client.publish(self.topic, self.message)
            # logging.debug(f"Published: {self.message} to topic: {self.topic}")
            self.client.publish("homeassistant/sensor/camelotaorus/state", json.dumps({
                'temperature': random.randint(15, 30)
            }), qos=0, retain=False)
        else:
            logging.error("Client is not connected. Message not sent.")

    def closeEvent(self, event):
        self.client.publish("homeassistant/sensor/camelotaorus/availability", "offline", qos=0, retain=False)

        self.client.loop_stop()
        self.client.disconnect()
        event.accept()
