import logging

import psutil

from .base import SampleResult


class _NetIoBase:
    component = "sensor"
    default_enabled = True
    default_interval_s = 30
    is_event_driven = False

    def discovery_payload(self, ctx) -> dict:
        return {
            "name": self.display_name,
            "unique_id": f"{ctx.device_id}_{self.key}",
            "object_id": f"{ctx.device_id}_{self.key}",
            "state_topic": ctx.state_topic(self.component, self.key),
            "availability_topic": ctx.availability_topic,
            "unit_of_measurement": "B",
            "icon": "mdi:network",
            "device": ctx.device_block(),
            "state_class": "total_increasing",
        }


class NetworkRxEntity(_NetIoBase):
    key = "network_rx_bytes"
    display_name = "Network bytes received"

    def sample(self) -> SampleResult:
        try:
            return SampleResult.available(value=int(psutil.net_io_counters().bytes_recv), unit="B")
        except Exception as exc:
            logging.debug("network_rx failed: %s", exc)
            return SampleResult.unavailable(reason=str(exc))


class NetworkTxEntity(_NetIoBase):
    key = "network_tx_bytes"
    display_name = "Network bytes sent"

    def sample(self) -> SampleResult:
        try:
            return SampleResult.available(value=int(psutil.net_io_counters().bytes_sent), unit="B")
        except Exception as exc:
            logging.debug("network_tx failed: %s", exc)
            return SampleResult.unavailable(reason=str(exc))
