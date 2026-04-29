from .base import Entity, SampleResult  # noqa: F401
from .cpu_usage import CpuUsageEntity


def build_entity_registry() -> list:
    """Return a fresh ordered list of entity instances.

    Called at plugin start; multi-instance entities (e.g. per-disk) expand here.
    """
    return [
        CpuUsageEntity(),
    ]
