from .lock import LockCommand
from .shutdown import ShutdownCommand
from .sleep_cmd import SleepCommand


def build_command_registry(plugin) -> list:
    candidates = [LockCommand(), SleepCommand(), ShutdownCommand()]
    return [c for c in candidates if c.is_available()]
