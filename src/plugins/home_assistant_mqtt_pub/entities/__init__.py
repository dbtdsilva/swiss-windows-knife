from .base import Entity, SampleResult  # noqa: F401
from .cpu_frequency import CpuFrequencyEntity
from .cpu_temperature import CpuTemperatureEntity
from .cpu_usage import CpuUsageEntity
from .memory_usage import MemoryUsageEntity


def build_entity_registry() -> list:
    return [
        CpuUsageEntity(),
        CpuTemperatureEntity(),
        CpuFrequencyEntity(),
        MemoryUsageEntity(),
    ]
