from PySide6.QtCore import Slot
from PySide6.QtWidgets import QWidget

from src.base.base_widget import BaseWidget

import logging
import paho.mqtt.client as mqtt_client
import paho.mqtt.enums as mqtt_enums


class HomeAssistantMqttPubPlugin(BaseWidget):

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent, is_enabled=True)

        self.broker_address = "192.168.1.253"
        self.port = 1883
        self.sub_topic = "homeassistant/#"
        self.client_id = 'b9a98b2b'
        self.username = 'dsilva'
        self.password = ''

        self.client = mqtt_client.Client(
            client_id=self.client_id,
            protocol=mqtt_client.MQTTv5,
            callback_api_version=mqtt_enums.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_subscribe = self.on_subscribe
        self.client.on_message = self.on_message

        self.client.username_pw_set(self.username, self.password)
        self.connect_to_mqtt()

    def on_connect(self, client, userdata, flags, rc, properties):
        if rc == 0:
            logging.info(f"Connected to MQTT broker on {self.broker_address}")
            client.subscribe(self.sub_topic)
        else:
            logging.error("Failed to connect, return code %d\n", rc)

    def on_disconnect(self, client, userdata, rc):
        logging.info(f"Disconnected from MQTT broker on {self.broker_address}")

    def on_subscribe(self, client, userdata, mid, granted_qos, properties):
        logging.info(f"Subscribed: {mid} QoS: {granted_qos}")

    def on_message(self, client, userdata, msg):
        logging.debug(f'Received message on {msg.topic} with retain {msg.retain} at '
                      f'{msg.timestamp} with the message: {msg.payload.decode()}')

    def connect_to_mqtt(self):
        try:
            self.client.connect(self.broker_address, self.port)
            self.client.loop_start()
        except Exception as e:
            logging.error(f"Status: Failed to connect ({e})")

    @Slot()
    def publish_message(self):
        if self.client.is_connected():
            # self.client.publish(self.topic, self.message)
            # logging.debug(f"Published: {self.message} to topic: {self.topic}")
            pass
        else:
            logging.error("Client is not connected. Message not sent.")

    def closeEvent(self, event):
        self.client.loop_stop()
        self.client.disconnect()
        event.accept()
