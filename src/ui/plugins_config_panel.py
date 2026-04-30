from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QLabel, QVBoxLayout, QWidget

from ..base.config_panel import ConfigPanel


class PluginsConfigPanel(ConfigPanel):
    """Master on/off switches for the toggleable plugins.

    `plugin_toggled(plugin, enabled)` fires every time a checkbox state
    changes — `ConfigurationDialog` listens so it can insert/remove the
    matching per-plugin tab live, before the user clicks OK.
    Persistence happens in `apply()`: only changed checkboxes call into
    `plugin.set_enabled` so a no-op OK doesn't trigger restart side
    effects.
    """

    title = "Plugins"

    plugin_toggled = Signal(object, bool)

    def __init__(self, plugins, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._plugins = list(plugins)
        self._checkboxes: dict = {}

        layout = QVBoxLayout(self)
        intro = QLabel("Enable or disable individual plugins. Disabled "
                       "plugins stop their work and are hidden from the "
                       "tray menu and Configuration tabs.", self)
        intro.setWordWrap(True)
        layout.addWidget(intro)

        for plugin in self._plugins:
            if not plugin.is_toggleable():
                continue
            box = QCheckBox(plugin.get_display_name(), self)
            box.setChecked(plugin.is_enabled())
            box.toggled.connect(
                lambda checked, p=plugin: self.plugin_toggled.emit(p, checked))
            layout.addWidget(box)
            self._checkboxes[plugin] = box

        layout.addStretch(1)

    def apply(self) -> bool:
        for plugin, box in self._checkboxes.items():
            checked = box.isChecked()
            if checked != plugin.is_enabled():
                plugin.set_enabled(checked)
        return True
