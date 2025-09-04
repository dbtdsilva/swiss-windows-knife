from dataclasses import dataclass


@dataclass
class MonitorInfo:
    device_id: str
    device_name: str
    model: str
    inputs: list
