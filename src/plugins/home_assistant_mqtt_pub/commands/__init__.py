from .lock import LockCommand


def build_command_registry(plugin) -> list:
    candidates = [LockCommand()]
    return [c for c in candidates if c.is_available()]
