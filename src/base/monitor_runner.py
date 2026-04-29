import logging
import queue
import threading
from collections.abc import Callable


class _MonitorRunner:
    def __init__(self) -> None:
        self._queue: queue.Queue = queue.Queue()
        self._thread = threading.Thread(target=self._run, daemon=True, name="MonitorRunner")
        self._thread.start()

    def submit(self, fn: Callable, *args, **kwargs) -> None:
        self._queue.put((fn, args, kwargs))

    def _run(self) -> None:
        while True:
            fn, args, kwargs = self._queue.get()
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
