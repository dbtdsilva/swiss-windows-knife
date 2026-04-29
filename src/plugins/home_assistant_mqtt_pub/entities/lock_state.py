import logging
from typing import Callable

from PySide6.QtWidgets import QWidget

from .base import SampleResult


WM_WTSSESSION_CHANGE = 0x02B1
WTS_SESSION_LOCK = 0x7
WTS_SESSION_UNLOCK = 0x8
NOTIFY_FOR_THIS_SESSION = 0


class LockStateEntity(QWidget):
    key = "lock_state"
    display_name = "Locked"
    component = "binary_sensor"
    default_enabled = True
    default_interval_s = None
    is_event_driven = True

    def __init__(self) -> None:
        super().__init__(parent=None)
        self._on_change: Callable | None = None
        self._registered = False

    def discovery_payload(self, ctx) -> dict:
        return {
            "name": self.display_name,
            "unique_id": f"{ctx.device_id}_{self.key}",
            "object_id": f"{ctx.device_id}_{self.key}",
            "state_topic": ctx.state_topic(self.component, self.key),
            "availability_topic": ctx.availability_topic,
            "device_class": "lock",
            "payload_on": "ON",
            "payload_off": "OFF",
            "device": ctx.device_block(),
        }

    def sample(self) -> SampleResult:
        try:
            import ctypes
            DESKTOP_SWITCHDESKTOP = 0x0100
            hdesk = ctypes.windll.user32.OpenInputDesktop(0, False, DESKTOP_SWITCHDESKTOP)
            if not hdesk:
                return SampleResult.available(value=True)  # cannot open input desktop → locked
            ctypes.windll.user32.CloseDesktop(hdesk)
            return SampleResult.available(value=False)
        except Exception as exc:
            logging.debug("lock_state initial sample failed: %s", exc)
            return SampleResult.unavailable(reason=str(exc))

    def subscribe(self, on_change: Callable[[SampleResult], None]) -> None:
        self._on_change = on_change
        if self._registered:
            return
        try:
            import ctypes
            ctypes.windll.wtsapi32.WTSRegisterSessionNotification(
                int(self.winId()), NOTIFY_FOR_THIS_SESSION,
            )
            self._registered = True
        except Exception:
            logging.exception("WTSRegisterSessionNotification failed")

    def unsubscribe(self) -> None:
        if not self._registered:
            return
        try:
            import ctypes
            ctypes.windll.wtsapi32.WTSUnRegisterSessionNotification(int(self.winId()))
        except Exception:
            logging.exception("WTSUnRegisterSessionNotification failed")
        finally:
            self._registered = False
            self._on_change = None

    def nativeEvent(self, eventType, message):
        try:
            import ctypes
            msg = ctypes.wintypes.MSG.from_address(int(message))
        except Exception:
            return False, 0
        if msg.message == WM_WTSSESSION_CHANGE:
            self._dispatch_session_event(msg.wParam)
        return False, 0

    def _dispatch_session_event(self, wparam: int) -> None:
        if self._on_change is None:
            return
        if wparam == WTS_SESSION_LOCK:
            self._on_change(SampleResult.available(value=True))
        elif wparam == WTS_SESSION_UNLOCK:
            self._on_change(SampleResult.available(value=False))
