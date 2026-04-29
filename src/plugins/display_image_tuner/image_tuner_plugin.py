from functools import partial
from typing import Optional
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QMenu
from PySide6.QtCore import QTimer, Signal, Slot

from ...base.config_panel import ConfigPanel
from ...base.user_settings import UserSettings
from ...base.base_widget import BaseWidget
from ...base.monitor_runner import runner
from .curve import compute_target, ease
from .sun_strength_notifier import SunStrengthNotifier
from .sun_location_panel import SunLocationConfigPanel

import monitorcontrol
import logging


TICK_MS = 1000


class DisplayImageTunerPlugin(BaseWidget):

    display_name = "Display brightness & contrast"

    brightness_changed = Signal(int)
    contrast_changed = Signal(int)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)

        self.user_settings = UserSettings.instance()
        if not self.user_settings.has_key('brightness'):
            self.user_settings.set('brightness', None)
        if not self.user_settings.has_key('contrast'):
            self.user_settings.set('contrast', 90)

        for axis in ('brightness', 'contrast'):
            if not self.user_settings.has_key(f'{axis}_auto_min'):
                self.user_settings.set(f'{axis}_auto_min', 0)
            if not self.user_settings.has_key(f'{axis}_auto_max'):
                self.user_settings.set(f'{axis}_auto_max', 100)
            if not self.user_settings.has_key(f'{axis}_auto_gamma'):
                self.user_settings.set(f'{axis}_auto_gamma', 1.0)
        if not self.user_settings.has_key('auto_smoothing_seconds'):
            self.user_settings.set('auto_smoothing_seconds', 0)

        logging.info(f"Starting with the 'brightness' set to {self.user_settings.get('brightness')}")
        logging.info(f"Starting with the 'contrast' set to {self.user_settings.get('contrast')}")

        self.sun_strength_plugin = SunStrengthNotifier(self)
        self.sun_strength_plugin.sun_strength_changed.connect(self._on_sun_strength)

        self._sun: Optional[int] = None
        self._actual: dict[str, Optional[float]] = {'brightness': None, 'contrast': None}
        self._last_emitted: dict[str, Optional[int]] = {'brightness': None, 'contrast': None}

        self.brightness_changed.connect(self.change_monitor_brightness)
        self.contrast_changed.connect(self.change_monitor_contrast)

        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._tick)
        self._tick_timer.start(TICK_MS)

    def retrieve_menus(self) -> list[QMenu | QAction]:
        return [
            self.create_value_control_menu('Brightness',
                                           lambda: self.user_settings.get('brightness'),
                                           self.change_brightness_manual,
                                           self.change_brightness_automatic),
            self.create_value_control_menu('Contrast',
                                           lambda: self.user_settings.get('contrast'),
                                           self.change_contrast_manual,
                                           self.change_contrast_automatic),
        ]

    def retrieve_config_panels(self) -> list[ConfigPanel]:
        return [SunLocationConfigPanel(self.sun_strength_plugin, self)]

    @Slot(int)
    def _on_sun_strength(self, value: int) -> None:
        self._sun = int(value)

    @Slot()
    def _tick(self) -> None:
        if self._sun is None:
            return
        try:
            smoothing = float(self.user_settings.get('auto_smoothing_seconds') or 0)
        except (TypeError, ValueError):
            smoothing = 0.0

        for axis in ('brightness', 'contrast'):
            fixed = self.user_settings.get(axis)
            if fixed is not None:
                # Fixed mode: keep _actual aligned to the fixed value so a later
                # switch back to auto starts the easing from a sensible point.
                try:
                    self._actual[axis] = float(int(fixed))
                except (TypeError, ValueError):
                    pass
                continue

            target = self._auto_target(axis)
            current = self._actual[axis]
            if current is None:
                current = target
            else:
                current = ease(current, target, dt=TICK_MS / 1000.0,
                               smoothing_seconds=smoothing)
            self._actual[axis] = current

            new_value = max(0, min(100, int(round(current))))
            if new_value != self._last_emitted[axis]:
                self._last_emitted[axis] = new_value
                getattr(self, f'{axis}_changed').emit(new_value)

    def _auto_target(self, axis: str) -> float:
        try:
            min_value = int(self.user_settings.get(f'{axis}_auto_min'))
            max_value = int(self.user_settings.get(f'{axis}_auto_max'))
            gamma = float(self.user_settings.get(f'{axis}_auto_gamma'))
        except (TypeError, ValueError):
            min_value, max_value, gamma = 0, 100, 1.0
        if max_value < min_value:
            min_value, max_value = max_value, min_value
        return compute_target(self._sun or 0, min_value=min_value,
                              max_value=max_value, gamma=gamma)

    def change_monitor_brightness(self, brightness):
        runner().submit(self._apply_brightness, brightness)

    def _apply_brightness(self, brightness):
        try:
            for i, monitor in enumerate(monitorcontrol.get_monitors()):
                with monitor:
                    if monitor.get_luminance() != brightness:
                        monitor.set_luminance(brightness)
                        logging.info(f"Setting brightness to {brightness} on monitor {i}")
        except (ValueError, monitorcontrol.VCPError) as e:
            logging.warning(f"Exception was caught while changing brightness: {e}")

    def change_monitor_contrast(self, contrast):
        runner().submit(self._apply_contrast, contrast)

    def _apply_contrast(self, contrast):
        try:
            for i, monitor in enumerate(monitorcontrol.get_monitors()):
                with monitor:
                    if monitor.get_contrast() != contrast:
                        monitor.set_contrast(contrast)
                        logging.info(f"Setting contrast to {contrast} on monitor {i}")
        except (ValueError, monitorcontrol.VCPError) as e:
            logging.warning(f"Exception was caught while changing contrast: {e}")

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
            self.user_settings.set('brightness', None)
            # Reset easing state; next tick will snap to first target.
            self._actual['brightness'] = None
            self._last_emitted['brightness'] = None

    def change_contrast_automatic(self, is_checked):
        if is_checked:
            self.user_settings.set('contrast', None)
            self._actual['contrast'] = None
            self._last_emitted['contrast'] = None

    def change_brightness_manual(self, is_checked, brightness_level):
        if not is_checked:
            return
        self.user_settings.set('brightness', brightness_level)
        self._actual['brightness'] = float(brightness_level)
        self._last_emitted['brightness'] = brightness_level
        self.brightness_changed.emit(brightness_level)

    def change_contrast_manual(self, is_checked, contrast_level):
        if not is_checked:
            return
        self.user_settings.set('contrast', contrast_level)
        self._actual['contrast'] = float(contrast_level)
        self._last_emitted['contrast'] = contrast_level
        self.contrast_changed.emit(contrast_level)

    def closeEvent(self, event):
        self._tick_timer.stop()
        self.sun_strength_plugin.close()
        event.accept()
