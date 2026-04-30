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
from .plugins_config_panel import PluginsConfigPanel

DEFAULT_PADDING = QSize(80, 60)


class ConfigurationDialog(PersistentSizeDialog):

    size_settings_prefix = "config_dialog"

    def __init__(self, parent: QWidget | None, plugins) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configuration")
        self._plugins = list(plugins)

        # `_panels_by_plugin` is the persistent record of "which panels does
        # this plugin contribute" (queried once at construction). `_tab_index`
        # tracks which of those are currently inserted in the QTabWidget so
        # we can show/hide them as the user toggles checkboxes.
        self._panels_by_plugin: dict = {}
        self._tab_index: dict = {}

        layout = QVBoxLayout(self)

        self._tabs = QTabWidget(self)
        layout.addWidget(self._tabs)

        self._plugins_panel = PluginsConfigPanel(self._plugins, self)
        self._plugins_panel.plugin_toggled.connect(self._on_plugin_toggled)
        self._tabs.addTab(
            self._wrap_in_scroll(self._plugins_panel),
            self._plugins_panel.title or "Plugins",
        )

        for plugin in self._plugins:
            panels = list(plugin.retrieve_config_panels())
            self._panels_by_plugin[plugin] = panels
            if plugin.is_enabled():
                for panel in panels:
                    self._insert_plugin_panel(plugin, panel)

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
        """Apply order: every per-plugin panel, then the Plugins panel last
        so `set_enabled` runs after per-plugin settings have been saved."""
        out: list[ConfigPanel] = []
        for plugin in self._plugins:
            out.extend(self._panels_by_plugin.get(plugin, []))
        out.append(self._plugins_panel)
        return out

    @staticmethod
    def _wrap_in_scroll(panel: ConfigPanel) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(panel)
        return scroll

    def _insert_plugin_panel(self, plugin, panel: ConfigPanel) -> None:
        if panel in self._tab_index:
            return
        index = self._tabs.addTab(
            self._wrap_in_scroll(panel),
            panel.title or panel.__class__.__name__,
        )
        self._tab_index[panel] = index

    def _remove_plugin_panel(self, panel: ConfigPanel) -> None:
        index = self._tab_index.pop(panel, None)
        if index is None:
            return
        # Removing a tab shifts indices of later tabs; rebuild the map by
        # rescanning what's still in the QTabWidget.
        self._tabs.removeTab(index)
        self._tab_index.clear()
        for i in range(self._tabs.count()):
            scroll = self._tabs.widget(i)
            inner = scroll.widget() if isinstance(scroll, QScrollArea) else scroll
            if isinstance(inner, ConfigPanel) and inner is not self._plugins_panel:
                self._tab_index[inner] = i

    def _on_plugin_toggled(self, plugin, enabled: bool) -> None:
        panels = self._panels_by_plugin.get(plugin, [])
        if enabled:
            for panel in panels:
                self._insert_plugin_panel(plugin, panel)
        else:
            for panel in panels:
                self._remove_plugin_panel(panel)

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
