import logging
import queue
import threading
from typing import Any, Callable


class SamplerRunner:
    """Single-thread queue for sampling work that can't sit on the Qt thread.

    Mirrors src/base/monitor_runner.py but is a real instance (not a singleton)
    so the plugin owns its lifetime.
    """

    def __init__(self) -> None:
        self._queue: queue.Queue = queue.Queue()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="HASamplerRunner")
        self._thread.start()

    def submit(self, fn: Callable[[], Any], on_done: Callable[[Any], None]) -> None:
        self._queue.put((fn, on_done))

    def _run(self) -> None:
        while True:
            fn, on_done = self._queue.get()
            try:
                value = fn()
            except Exception:
                logging.exception("HA sampler fn raised")
                continue
            try:
                on_done(value)
            except Exception:
                logging.exception("HA sampler on_done raised")
