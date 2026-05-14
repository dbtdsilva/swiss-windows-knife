import logging

from PySide6.QtCore import QSize
from PySide6.QtWidgets import (
    QDialogButtonBox,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..base.config_panel import ConfigPanel
from ..base.persistent_dialog import PersistentSizeDialog
from .general_config_panel import GeneralConfigPanel

DEFAULT_PADDING = QSize(80, 60)


class ConfigurationDialog(PersistentSizeDialog):

    size_settings_prefix = "config_dialog"

    def __init__(self, parent: QWidget | None, plugins) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configuration")
        self._plugins = list(plugins)

        # `_panels_by_plugin` is the persistent record of "which panels does
        # this plugin contribute" (queried once at construction). `_tab_index`
        # maps each panel to its tab position in the QTabWidget; every panel
        # is inserted once at construction and toggled via `setTabVisible`,
        # so the index stays valid for the dialog's lifetime.
        self._panels_by_plugin: dict = {}
        self._tab_index: dict = {}

        layout = QVBoxLayout(self)

        self._tabs = QTabWidget(self)
        layout.addWidget(self._tabs)

        self._general_panel = GeneralConfigPanel(self._plugins, self)
        self._general_panel.plugin_toggled.connect(self._on_plugin_toggled)
        self._tabs.addTab(
            self._wrap_in_scroll(self._general_panel),
            self._general_panel.title or "General",
        )

        for plugin in self._plugins:
            panels = list(plugin.retrieve_config_panels())
            self._panels_by_plugin[plugin] = panels
            for panel in panels:
                self._insert_plugin_panel(plugin, panel)
            if not plugin.is_enabled():
                self._set_plugin_tabs_visible(plugin, False)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.adjustSize()
        self.restore_size(self.size() + DEFAULT_PADDING)

    @property
    def _all_panels(self) -> list[ConfigPanel]:
        """Apply order: every per-plugin panel, then the General panel last
        so `set_enabled` runs after per-plugin settings have been saved."""
        out: list[ConfigPanel] = []
        for plugin in self._plugins:
            out.extend(self._panels_by_plugin.get(plugin, []))
        out.append(self._general_panel)
        return out

    @staticmethod
    def _wrap_in_scroll(panel: ConfigPanel) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(panel)
        return scroll

    def _tab_title(self, panel: ConfigPanel) -> str:
        return panel.title or panel.__class__.__name__

    def _alphabetical_insert_index(self, title: str) -> int:
        """First tab index (>= 1, since General is pinned at 0) whose title
        sorts after `title`. Returns `count()` if `title` belongs at the end."""
        for i in range(1, self._tabs.count()):
            if self._tabs.tabText(i).lower() > title.lower():
                return i
        return self._tabs.count()

    def _rebuild_tab_index(self) -> None:
        self._tab_index.clear()
        for i in range(self._tabs.count()):
            scroll = self._tabs.widget(i)
            inner = scroll.widget() if isinstance(scroll, QScrollArea) else scroll
            if isinstance(inner, ConfigPanel) and inner is not self._general_panel:
                self._tab_index[inner] = i

    def _insert_plugin_panel(self, plugin, panel: ConfigPanel) -> None:
        if panel in self._tab_index:
            return
        title = self._tab_title(panel)
        insert_at = self._alphabetical_insert_index(title)
        self._tabs.insertTab(insert_at, self._wrap_in_scroll(panel), title)
        self._rebuild_tab_index()

    def _set_plugin_tabs_visible(self, plugin, visible: bool) -> None:
        for panel in self._panels_by_plugin.get(plugin, []):
            index = self._tab_index.get(panel)
            if index is not None:
                self._tabs.setTabVisible(index, visible)

    def _on_plugin_toggled(self, plugin, enabled: bool) -> None:
        self._set_plugin_tabs_visible(plugin, enabled)

    def _on_accept(self) -> None:
        for panel in self._all_panels:
            if not panel.apply():
                return
        self.accept()

    def done(self, result: int) -> None:
        # Fires on OK (`accept()`), Cancel (`reject()`), and X (`closeEvent`
        # → default `done(Rejected)`). Run panel cleanup *before* Qt starts
        # destroying anything so panels can cancel in-flight async work
        # while their child widgets are still alive.
        for panel in self._all_panels:
            try:
                panel.cleanup()
            except Exception:
                logging.exception("ConfigPanel.cleanup raised")
        super().done(result)
