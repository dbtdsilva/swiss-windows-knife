from dataclasses import dataclass
from enum import StrEnum


class HealthState(StrEnum):
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"
    DISABLED = "disabled"


@dataclass(frozen=True)
class HealthReport:
    state: HealthState
    message: str
