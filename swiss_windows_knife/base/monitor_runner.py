import logging
import queue
import threading
from collections.abc import Callable

from .cancellation import Token


class _MonitorRunner:
    def __init__(self) -> None:
        self._queue: queue.Queue = queue.Queue()
        self._thread = threading.Thread(target=self._run, daemon=True, name="MonitorRunner")
        self._thread.start()

    def submit(self, fn: Callable, *args, **kwargs) -> Token:
        """Submit work; returns a token the caller can cancel.

        If the token is cancelled before the worker dequeues this entry, `fn`
        is skipped entirely. Once `fn` starts running it can't be aborted —
        but `fn` itself may consult the token to skip side effects (e.g.,
        emitting back into a Qt object that is being destroyed).
        """
        token = Token()
        self._queue.put((fn, args, kwargs, token))
        return token

    def _run(self) -> None:
        while True:
            fn, args, kwargs, token = self._queue.get()
            if token.is_cancelled:
                continue
            try:
                fn(*args, **kwargs)
            except Exception:
                logging.exception("Monitor operation failed")


_runner: _MonitorRunner | None = None
_runner_lock = threading.Lock()


def runner() -> _MonitorRunner:
    global _runner
    with _runner_lock:
        if _runner is None:
            _runner = _MonitorRunner()
    return _runner
