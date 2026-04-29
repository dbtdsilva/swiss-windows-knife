import logging
from collections.abc import Callable

import paho.mqtt.client as mqtt_client
import paho.mqtt.enums as mqtt_enums


class MqttSession:
    """Owns a paho Client, registers LWT, dispatches messages by topic."""

    def __init__(self, broker_config: dict, availability_topic: str) -> None:
        self._cfg = broker_config
        self._availability_topic = availability_topic
        self._handlers: dict[str, Callable[[str], None]] = {}
        self._client = mqtt_client.Client(
            client_id=str(broker_config.get("client_id", "")),
            protocol=mqtt_client.MQTTv5,
            callback_api_version=mqtt_enums.CallbackAPIVersion.VERSION2,
        )
        self._client.username_pw_set(
            str(broker_config.get("username", "")),
            str(broker_config.get("password", "")),
        )
        self._client.will_set(self._availability_topic, "offline", qos=0, retain=True)
        self._client.reconnect_delay_set(min_delay=1, max_delay=30)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

        self.on_connected: Callable[[], None] | None = None

    def subscribe(self, topic: str, handler: Callable[[str], None]) -> None:
        """Register a handler for the topic.

        Subscription on the broker happens at on_connect time so that
        reconnects automatically re-subscribe.
        """
        self._handlers[topic] = handler

    def start(self) -> None:
        self._client.connect_async(
            host=str(self._cfg["host"]),
            port=int(self._cfg["port"]),
            keepalive=30,
        )
        self._client.loop_start()

    def stop(self) -> None:
        if self._client.is_connected():
            try:
                self._client.publish(self._availability_topic, "offline", qos=0, retain=True)
            except Exception:
                logging.exception("failed to publish offline availability")
        self._client.loop_stop()
        self._client.disconnect()

    def publish(self, topic: str, payload, retain: bool = False) -> None:
        self._client.publish(topic, payload, qos=0, retain=retain)

    def _on_connect(self, client, userdata, flags, rc, properties):
        if rc != 0:
            logging.warning("MQTT connect failed rc=%s", rc)
            return
        logging.info("MQTT connected")
        for topic in self._handlers:
            client.subscribe(topic)
        if self.on_connected is not None:
            try:
                self.on_connected()
            except Exception:
                logging.exception("on_connected hook raised")

    def _on_disconnect(self, client, userdata, flags, rc, properties):
        logging.info("MQTT disconnected rc=%s", rc)

    def _on_message(self, client, userdata, msg):
        handler = self._handlers.get(msg.topic)
        if handler is None:
            logging.debug("MQTT message on unhandled topic %s", msg.topic)
            return
        try:
            payload = msg.payload.decode() if isinstance(msg.payload, (bytes, bytearray)) else str(msg.payload)
        except Exception:
            payload = ""
        try:
            handler(payload)
        except Exception:
            logging.exception("MQTT handler for %s raised", msg.topic)
