from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, Protocol


@dataclass(frozen=True)
class SampleResult:
    is_available: bool
    value: Any = None
    unit: str = ""
    reason: str = ""

    @staticmethod
    def available(value: Any, unit: str = "") -> "SampleResult":
        return SampleResult(is_available=True, value=value, unit=unit)

    @staticmethod
    def unavailable(reason: str = "") -> "SampleResult":
        return SampleResult(is_available=False, reason=reason)


Component = Literal["sensor", "binary_sensor"]


class Entity(Protocol):
    key: str
    display_name: str
    component: Component
    default_enabled: bool
    default_interval_s: int | None    # None => event-driven
    is_event_driven: bool

    def discovery_payload(self, ctx) -> dict: ...   # ctx: DeviceContext

    def sample(self) -> SampleResult: ...

    def subscribe(self, on_change: Callable[[SampleResult], None]) -> None:
        """Optional. Only meaningful when is_event_driven is True."""
        ...

    def unsubscribe(self) -> None:
        """Optional. Reverse of subscribe()."""
        ...
