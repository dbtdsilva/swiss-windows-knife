import threading


class Token:
    """Atomic cancellation flag handed back from `submit`-style APIs.

    Submitters store the token, cancel it when their receiver goes away,
    and the runner / queue checks `is_cancelled` at the callback boundary.
    Cancellation is one-way and idempotent.
    """

    __slots__ = ("_cancelled", "_lock")

    def __init__(self) -> None:
        self._cancelled = False
        self._lock = threading.Lock()

    def cancel(self) -> None:
        with self._lock:
            self._cancelled = True

    @property
    def is_cancelled(self) -> bool:
        with self._lock:
            return self._cancelled
