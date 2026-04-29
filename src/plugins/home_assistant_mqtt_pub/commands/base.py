from typing import Protocol


class Command(Protocol):
    key: str
    display_name: str
    default_enabled: bool

    def discovery_payload(self, ctx) -> dict: ...

    def run(self) -> None: ...

    def is_available(self) -> bool:
        return True
