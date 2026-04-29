from .base import Entity, SampleResult  # noqa: F401
from .battery_state import BatteryStateEntity
from .cpu_frequency import CpuFrequencyEntity
from .cpu_temperature import CpuTemperatureEntity
from .cpu_usage import CpuUsageEntity
from .current_user import CurrentUserEntity
from .disk_free import discover_disk_free_entities
from .memory_usage import MemoryUsageEntity
from .monitor_count import MonitorCountEntity
from .network_io import NetworkRxEntity, NetworkTxEntity
from .uptime import UptimeEntity


def build_entity_registry() -> list:
    return [
        CpuUsageEntity(),
        CpuTemperatureEntity(),
        CpuFrequencyEntity(),
        MemoryUsageEntity(),
        UptimeEntity(),
        BatteryStateEntity(),
        *discover_disk_free_entities(),
        NetworkRxEntity(),
        NetworkTxEntity(),
        MonitorCountEntity(),
        CurrentUserEntity(),
    ]
