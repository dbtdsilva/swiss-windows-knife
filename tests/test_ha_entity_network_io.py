from unittest.mock import MagicMock, patch

from swiss_windows_knife.plugins.home_assistant_mqtt_pub.entities.network_io import (
    NetworkRxEntity,
    NetworkTxEntity,
)


def _io(rx, tx):
    m = MagicMock()
    m.bytes_recv = rx
    m.bytes_sent = tx
    return m


def test_rx_returns_bytes_received():
    e = NetworkRxEntity()
    with patch("psutil.net_io_counters", return_value=_io(rx=1234, tx=999)):
        r = e.sample()
    assert r.value == 1234
    assert r.unit == "B"


def test_tx_returns_bytes_sent():
    e = NetworkTxEntity()
    with patch("psutil.net_io_counters", return_value=_io(rx=1234, tx=999)):
        r = e.sample()
    assert r.value == 999
