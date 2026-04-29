import pytest


class _FakeUserSettings:
    def __init__(self) -> None:
        self._data: dict = {}

    def get(self, key):
        return self._data.get(key)

    def has_key(self, key) -> bool:
        return key in self._data

    def set(self, key, value) -> None:
        self._data[key] = value


@pytest.fixture
def fake_user_settings(monkeypatch):
    """Replace `UserSettings.instance()` with a dict-backed fake.

    Panels and plugins fetch settings via the singleton at __init__ time,
    so this fixture must be applied before instantiating them.
    """
    from src.base.user_settings import UserSettings
    fake = _FakeUserSettings()
    monkeypatch.setattr(UserSettings, 'instance', classmethod(lambda cls: fake))
    return fake


@pytest.fixture
def silent_messagebox(monkeypatch):
    """Suppress QMessageBox modals so apply()-style validation can run headless."""
    from PySide6.QtWidgets import QMessageBox
    for method in ('warning', 'critical', 'information', 'question'):
        monkeypatch.setattr(QMessageBox, method, lambda *args, **kwargs: None)


class _FakePahoClient:
    """Records paho calls so tests can assert on them without a broker."""

    def __init__(self, *args, **kwargs):
        self.init_args = args
        self.init_kwargs = kwargs
        self.username = None
        self.password = None
        self.will = None
        self.connected = False
        self.loop_started = False
        self.published: list[tuple[str, str | bytes, bool]] = []
        self.subscribed: list[str] = []
        self.on_connect = None
        self.on_disconnect = None
        self.on_message = None
        self.reconnect_min = None
        self.reconnect_max = None

    def username_pw_set(self, user, password):
        self.username, self.password = user, password

    def will_set(self, topic, payload, qos=0, retain=False):
        self.will = (topic, payload, qos, retain)

    def reconnect_delay_set(self, min_delay, max_delay):
        self.reconnect_min, self.reconnect_max = min_delay, max_delay

    def connect_async(self, host, port, keepalive):
        self.connect_args = (host, port, keepalive)

    def loop_start(self):
        self.loop_started = True

    def loop_stop(self):
        self.loop_started = False

    def disconnect(self):
        self.connected = False

    def is_connected(self):
        return self.connected

    def subscribe(self, topic):
        self.subscribed.append(topic)

    def publish(self, topic, payload=None, qos=0, retain=False):
        self.published.append((topic, payload, retain))

    def fire_on_connect(self, rc=0):
        self.connected = (rc == 0)
        self.on_connect(self, None, None, rc, None)

    def fire_on_message(self, topic, payload):
        class _Msg:
            pass
        m = _Msg()
        m.topic = topic
        m.payload = payload.encode() if isinstance(payload, str) else payload
        m.retain = False
        m.timestamp = 0
        self.on_message(self, None, m)


@pytest.fixture
def fake_paho_client(monkeypatch):
    instances = []

    def factory(*args, **kwargs):
        c = _FakePahoClient(*args, **kwargs)
        instances.append(c)
        return c

    import paho.mqtt.client as paho
    monkeypatch.setattr(paho, "Client", factory)
    return instances
