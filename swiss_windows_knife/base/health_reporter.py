from PySide6.QtCore import Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QWidget

from .health import HealthReport, HealthState


class HealthReporter(QWidget):
    """Tray-attached component that exposes a health snapshot, an optional
    display name, and optional top-level menu entries.

    `BaseWidget` extends this with toggle/config-panel semantics. Components
    that are *not* user-facing features (e.g. the auto-updater) extend
    `HealthReporter` directly so they participate in the Health submenu
    without leaking into the Plugins toggle list or the Configuration tabs.

    QWidget (rather than QObject) so subclasses can override `closeEvent`
    for shutdown — the tray calls `close()` on each reporter at teardown.
    """

    display_name: str = ""
    description: str = ""

    health_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_health: HealthReport = HealthReport(HealthState.OK, "")

    def get_display_name(self) -> str:
        return self.display_name or self.__class__.__name__

    def health(self) -> HealthReport:
        return self._current_health

    def _set_health(self, state: HealthState, message: str) -> None:
        new_report = HealthReport(state, message)
        if new_report == self._current_health:
            return
        self._current_health = new_report
        self.health_changed.emit()

    def retrieve_menus(self) -> list[QMenu | QAction]:
        return []
