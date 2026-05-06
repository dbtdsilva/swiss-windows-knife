from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ..base.config_panel import ConfigPanel


class _PluginCard(QFrame):
    """Title + description + toggle for one plugin row."""

    def __init__(self, plugin, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)

        title = QLabel(f"<b>{plugin.get_display_name()}</b>", self)
        description = QLabel(getattr(plugin, 'description', '') or "", self)
        description.setWordWrap(True)
        description.setStyleSheet("color: palette(placeholder-text);")

        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(2)
        text_col.addWidget(title)
        if description.text():
            text_col.addWidget(description)

        self.checkbox = QCheckBox(self)
        self.checkbox.setChecked(plugin.is_enabled())

        layout = QHBoxLayout(self)
        layout.addLayout(text_col, 1)
        layout.addWidget(self.checkbox, 0, Qt.AlignmentFlag.AlignTop)


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
            card = _PluginCard(plugin, self)
            card.checkbox.toggled.connect(
                lambda checked, p=plugin: self.plugin_toggled.emit(p, checked))
            layout.addWidget(card)
            self._checkboxes[plugin] = card.checkbox

        layout.addStretch(1)

    def apply(self) -> bool:
        for plugin, box in self._checkboxes.items():
            checked = box.isChecked()
            if checked != plugin.is_enabled():
                plugin.set_enabled(checked)
        return True
