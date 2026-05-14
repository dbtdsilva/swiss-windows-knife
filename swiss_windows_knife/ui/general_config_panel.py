from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from ..base.color_scheme import (
    ColorSchemePreference,
    apply_preference,
    load_preference,
    save_preference,
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


def _section_label(text: str, parent: QWidget) -> QLabel:
    return QLabel(f"<b>{text}</b>", parent)


class GeneralConfigPanel(ConfigPanel):
    """Application-wide settings plus master on/off switches for the plugins.

    `plugin_toggled(plugin, enabled)` fires every time a plugin checkbox state
    changes — `ConfigurationDialog` listens so it can insert/remove the
    matching per-plugin tab live, before the user clicks OK.
    Persistence happens in `apply()`: only changed checkboxes call into
    `plugin.set_enabled` so a no-op OK doesn't trigger restart side
    effects, and the color-scheme preference is only written when it
    differs from the stored value.
    """

    title = "General"

    plugin_toggled = Signal(object, bool)

    def __init__(self, plugins, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._plugins = list(plugins)
        self._checkboxes: dict = {}

        layout = QVBoxLayout(self)

        layout.addWidget(_section_label("Appearance", self))
        appearance_intro = QLabel(
            "Override the system light/dark setting, or follow it.", self,
        )
        appearance_intro.setWordWrap(True)
        layout.addWidget(appearance_intro)

        form = QFormLayout()
        self._color_scheme_combo = QComboBox(self)
        for preference in ColorSchemePreference:
            self._color_scheme_combo.addItem(preference.value, preference)
        self._initial_preference = load_preference()
        self._color_scheme_combo.setCurrentIndex(
            self._color_scheme_combo.findData(self._initial_preference),
        )
        form.addRow("Color scheme:", self._color_scheme_combo)
        layout.addLayout(form)

        layout.addSpacing(12)
        layout.addWidget(_section_label("Plugins", self))
        plugins_intro = QLabel(
            "Enable or disable individual plugins. Disabled plugins stop "
            "their work and are hidden from the tray menu and Configuration "
            "tabs.",
            self,
        )
        plugins_intro.setWordWrap(True)
        layout.addWidget(plugins_intro)

        for plugin in self._plugins:
            if not plugin.is_toggleable():
                continue
            card = _PluginCard(plugin, self)
            card.checkbox.toggled.connect(
                lambda checked, p=plugin: self.plugin_toggled.emit(p, checked))
            layout.addWidget(card)
            self._checkboxes[plugin] = card.checkbox

        layout.addStretch(1)

    def _selected_preference(self) -> ColorSchemePreference:
        return self._color_scheme_combo.currentData()

    def apply(self) -> bool:
        preference = self._selected_preference()
        if preference != self._initial_preference:
            save_preference(preference)
            apply_preference(preference)
            self._initial_preference = preference

        for plugin, box in self._checkboxes.items():
            checked = box.isChecked()
            if checked != plugin.is_enabled():
                plugin.set_enabled(checked)
        return True
