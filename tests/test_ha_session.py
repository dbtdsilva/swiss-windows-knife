from src.plugins.home_assistant_mqtt_pub.device_context import DeviceContext
from src.plugins.home_assistant_mqtt_pub.mqtt_session import MqttSession


def _ctx():
    return DeviceContext(name="pc")


def _broker():
    return dict(host="broker", port=1883, username="u", password="p", client_id="cid")


def test_start_sets_lwt_and_connects_async(fake_paho_client):
    sess = MqttSession(broker_config=_broker(), availability_topic=_ctx().availability_topic)
    sess.start()
    client = fake_paho_client[0]
    assert client.will == (_ctx().availability_topic, "offline", 0, True)
    assert client.username == "u"
    assert client.password == "p"
    assert client.connect_args == ("broker", 1883, 30)
    assert client.loop_started is True
    assert client.reconnect_min == 1
    assert client.reconnect_max == 30


def test_on_connect_subscribes_to_topics_and_fires_callback(fake_paho_client):
    sess = MqttSession(broker_config=_broker(), availability_topic=_ctx().availability_topic)
    fired = []
    sess.on_connected = lambda: fired.append(True)
    sess.subscribe("homeassistant/status", lambda payload: None)
    sess.subscribe("homeassistant/button/swk_pc/lock/set", lambda payload: None)
    sess.start()
    client = fake_paho_client[0]
    client.fire_on_connect(rc=0)
    assert "homeassistant/status" in client.subscribed
    assert "homeassistant/button/swk_pc/lock/set" in client.subscribed
    assert fired == [True]


def test_on_message_routes_to_registered_handler(fake_paho_client):
    sess = MqttSession(broker_config=_broker(), availability_topic=_ctx().availability_topic)
    received = []
    sess.subscribe("homeassistant/status", lambda payload: received.append(payload))
    sess.start()
    client = fake_paho_client[0]
    client.fire_on_message("homeassistant/status", "online")
    assert received == ["online"]


def test_publish_passes_through(fake_paho_client):
    sess = MqttSession(broker_config=_broker(), availability_topic=_ctx().availability_topic)
    sess.start()
    sess.publish("a/topic", "hello", retain=True)
    assert fake_paho_client[0].published == [("a/topic", "hello", True)]


def test_stop_publishes_offline_then_disconnects(fake_paho_client):
    sess = MqttSession(broker_config=_broker(), availability_topic="homeassistant/swk_pc/availability")
    sess.start()
    fake_paho_client[0].connected = True
    sess.stop()
    client = fake_paho_client[0]
    assert ("homeassistant/swk_pc/availability", "offline", True) in client.published
    assert client.loop_started is False
    assert client.connected is False
