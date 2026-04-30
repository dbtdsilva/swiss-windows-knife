import logging
import queue
import threading
from collections.abc import Callable
from typing import Any

from ...base.cancellation import Token


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

    def submit(self, fn: Callable[[], Any], on_done: Callable[[Any], None]) -> Token:
        """Submit a sample; returns a token that suppresses `on_done` when
        cancelled. `fn` itself may still run (it has no side effects on Qt
        objects); only the delivery callback is gated by the token."""
        token = Token()
        self._queue.put((fn, on_done, token))
        return token

    def _run(self) -> None:
        while True:
            fn, on_done, token = self._queue.get()
            try:
                value = fn()
            except Exception:
                logging.exception("HA sampler fn raised")
                continue
            if token.is_cancelled:
                continue
            try:
                on_done(value)
            except Exception:
                logging.exception("HA sampler on_done raised")
