from .base import Entity, SampleResult  # noqa: F401
from .cpu_temperature import CpuTemperatureEntity
from .cpu_usage import CpuUsageEntity


def build_entity_registry() -> list:
    return [
        CpuUsageEntity(),
        CpuTemperatureEntity(),
    ]
