

from functools import partial
from PySide6.QtWidgets import QWidget
from plugins.base_plugin import BasePlugin
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QMenu
from PySide6.QtCore import Signal

from plugins.controllable_data import ControllableData
from plugins.sun_strenght_plugin import SunStrenghtPlugin

import monitorcontrol


class ImageTunerPlugin(BasePlugin):

    brightness_changed = Signal(int)
    contrast_changed = Signal(int)

    def __init__(self, parent: QWidget, sun_strenght_plugin: SunStrenghtPlugin) -> None:
        super().__init__(parent)

        self.controllable_data = ControllableData()
        self.sun_strenght_plugin = sun_strenght_plugin

        self.automatic_brightness_slot = None
        self.automatic_contrast_slot = None

        self.brightness_changed.connect(self.change_monitor_brightness)
        self.contrast_changed.connect(self.change_monitor_contrast)

    def retrieve_menus(self) -> list[QMenu]:
        return [
            self.create_value_control_menu('Brightness',
                                           lambda: self.controllable_data.brightness,
                                           self.change_brightness_manual,
                                           self.change_brightness_automatic),
            self.create_value_control_menu('Contrast',
                                           lambda: self.controllable_data.contrast,
                                           self.change_contrast_manual,
                                           self.change_contrast_automatic)]

    def change_monitor_brightness(self, brightness):
        # Change respective settings on the monitor through DDC/CI
        try:
            for i, monitor in enumerate(monitorcontrol.get_monitors()):
                with monitor:
                    if monitor.get_luminance() != brightness:
                        monitor.set_luminance(brightness)
                        self.logger.info(f"Setting brightness to {brightness} on monitor {i}")
        except (ValueError, monitorcontrol.VCPError) as e:
            self.logger.warn(f"Exception was caught while changing brightness: {e}")

    def change_monitor_contrast(self, contrast):
        # Change respective settings on the monitor through DDC/CI
        try:
            for i, monitor in enumerate(monitorcontrol.get_monitors()):
                with monitor:
                    if monitor.get_contrast() != contrast:
                        monitor.set_contrast(contrast)
                        self.logger.info(f"Setting contrast to {contrast} on monitor {i}")
        except (ValueError, monitorcontrol.VCPError) as e:
            self.logger.warn(f"Exception was caught while changing contrast: {e}")

    def create_value_control_menu(self, title, property_get, manual_slot, automatic_slot) -> QMenu:
        menu = QMenu(title, self)
        group = QActionGroup(self)
        group.setExclusive(True)

        automatic_action = QAction('Automatic', self)
        automatic_action.setCheckable(True)
        automatic_action.toggled.connect(automatic_slot)
        if property_get() is None:
            automatic_action.setChecked(True)

        group.addAction(automatic_action)
        menu.addAction(automatic_action)
        menu.addSeparator()
        for value_entry in range(0, 101, 10):
            action = QAction(str(value_entry), self)
            action.setCheckable(True)
            action.toggled.connect(partial(lambda is_checked, value=value_entry: manual_slot(is_checked, value)))
            if value_entry == property_get():
                action.setChecked(True)
            group.addAction(action)
            menu.addAction(action)
        return menu

    def change_brightness_automatic(self, is_checked):
        if is_checked:
            self.controllable_data.brightness = None
            self.automatic_brightness_slot = lambda val: self.brightness_changed.emit(val)
            self.sun_strenght_plugin.sun_strength_changed.connect(self.automatic_brightness_slot)
        else:
            self.sun_strenght_plugin.sun_strength_changed.disconnect(self.automatic_brightness_slot)
            self.automatic_brightness_slot = None

    def change_contrast_automatic(self, is_checked):
        if is_checked:
            self.controllable_data.contrast = None
            self.automatic_contrast_slot = lambda val: self.contrast_changed.emit(val)
            self.sun_strenght_plugin.sun_strength_changed.connect(self.automatic_contrast_slot)
        else:
            self.sun_strenght_plugin.sun_strength_changed.disconnect(self.automatic_contrast_slot)
            self.automatic_contrast_slot = None

    def change_brightness_manual(self, is_checked, brightness_level):
        if not is_checked:
            return

        self.brightness_changed.emit(brightness_level)
        self.controllable_data.brightness = brightness_level

    def change_contrast_manual(self, is_checked, contrast_level):
        if not is_checked:
            return

        self.contrast_changed.emit(contrast_level)
        self.controllable_data.contrast = contrast_level
