from .lock import LockCommand
from .sleep_cmd import SleepCommand


def build_command_registry(plugin) -> list:
    candidates = [LockCommand(), SleepCommand()]
    return [c for c in candidates if c.is_available()]
