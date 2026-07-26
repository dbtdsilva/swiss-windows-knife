import logging
from datetime import date, datetime
from functools import partial

import monitorcontrol
from PySide6.QtCore import QTimer, Signal, Slot
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QMenu, QWidget

from ...base.base_widget import BaseWidget
from ...base.config_panel import ConfigPanel
from ...base.health import HealthState
from ...base.monitor_runner import runner
from ...base.user_settings import UserSettings
from .curve import compute_keyframe_value
from .display_tuning_panel import DisplayTuningConfigPanel
from .display_wake_listener import DisplayWakeListener
from .sun_strength_notifier import SunStrengthNotifier, find_sun_events

TICK_MS = 1000


class DisplayImageTunerPlugin(BaseWidget):

    display_name = "Display brightness & contrast"
    description = (
        "Auto-adjusts monitor brightness and contrast over the day, "
        "ramping smoothly around sunrise and sunset."
    )

    brightness_changed = Signal(int)
    contrast_changed = Signal(int)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)

        self.user_settings = UserSettings.instance()
        self._seed_default_settings()

        logging.info(f"Starting with the 'brightness' set to {self.user_settings.get('brightness', int)}")
        logging.info(f"Starting with the 'contrast' set to {self.user_settings.get('contrast', int)}")

        self.sun_strength_plugin = SunStrengthNotifier(self)

        self._last_emitted: dict[str, int | None] = {'brightness': None, 'contrast': None}
        self._needs_retry: dict[str, bool] = {'brightness': False, 'contrast': False}
        # When set, the next apply for the axis writes unconditionally,
        # bypassing the get_luminance() dedup. Set on display wake (monitors
        # may report a stale value after a DDC-resetting power-cycle) and
        # kept across retries until an apply lands.
        self._force_next: dict[str, bool] = {'brightness': False, 'contrast': False}
        self._sun_events_cache_day: date | None = None
        self._sun_events_cache: tuple[float | None, float | None] = (None, None)

        self.brightness_changed.connect(self.change_monitor_brightness)
        self.contrast_changed.connect(self.change_monitor_contrast)

        self._wake_listener: DisplayWakeListener | None = None

        self._set_health(HealthState.OK, self._mode_message())

        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._tick)
        if self.is_enabled():
            self._tick_timer.start(TICK_MS)
            self._start_wake_listener()

    def _mode_message(self) -> str:
        b = self.user_settings.get('brightness', int)
        if b is None:
            return "Auto"
        return f"Manual {b}"

    def _seed_default_settings(self) -> None:
        defaults: dict[str, object] = {
            'brightness': None,
            'contrast': 90,
            'brightness_night_level': 0,
            'brightness_day_level': 100,
            'contrast_night_level': 0,
            'contrast_day_level': 100,
            'auto_sunrise_offset_minutes': 0,
            'auto_sunset_offset_minutes': 0,
            'auto_ramp_duration_minutes': 60,
            'auto_ramp_smoothness': 0.0,
        }
        for key, value in defaults.items():
            if not self.user_settings.has_key(key):
                self.user_settings.set(key, value)

    def retrieve_menus(self) -> list[QMenu | QAction]:
        return [
            self.create_value_control_menu('Brightness', 'brightness',
                                           self.change_brightness_manual,
                                           self.change_brightness_automatic),
            self.create_value_control_menu('Contrast', 'contrast',
                                           self.change_contrast_manual,
                                           self.change_contrast_automatic),
        ]

    def retrieve_config_panels(self) -> list[ConfigPanel]:
        return [DisplayTuningConfigPanel(self.sun_strength_plugin, self)]

    @Slot()
    def _tick(self) -> None:
        for axis in ('brightness', 'contrast'):
            manual = self.user_settings.get(axis, int)
            if manual is not None:
                # Manual mode is otherwise passive, but a prior apply that
                # failed on a monitor (e.g. still waking from suspend) must
                # still be re-driven, or that monitor stays stale forever.
                if self._needs_retry[axis]:
                    self._needs_retry[axis] = False
                    getattr(self, f'{axis}_changed').emit(manual)
                continue
            target = self._auto_target(axis)
            new_value = max(0, min(100, int(round(target))))
            if new_value != self._last_emitted[axis] or self._needs_retry[axis]:
                self._needs_retry[axis] = False
                self._last_emitted[axis] = new_value
                getattr(self, f'{axis}_changed').emit(new_value)

    def _auto_target(self, axis: str) -> float:
        night = self.user_settings.get(f'{axis}_night_level', float, 0.0)
        day = self.user_settings.get(f'{axis}_day_level', float, 100.0)
        sunrise_offset = self.user_settings.get('auto_sunrise_offset_minutes', float, 0.0)
        sunset_offset = self.user_settings.get('auto_sunset_offset_minutes', float, 0.0)
        duration = self.user_settings.get('auto_ramp_duration_minutes', float, 60.0)
        smoothness = self.user_settings.get('auto_ramp_smoothness', float, 0.0)

        sunrise_h, sunset_h = self._sun_events_for_today()
        _, _, tz = self.sun_strength_plugin.resolve_location()
        now = datetime.now().astimezone(tz)
        when_h = now.hour + now.minute / 60.0 + now.second / 3600.0

        return compute_keyframe_value(
            when_h,
            sunrise_hours=sunrise_h,
            sunset_hours=sunset_h,
            night_level=night,
            day_level=day,
            sunrise_offset_minutes=sunrise_offset,
            sunset_offset_minutes=sunset_offset,
            ramp_duration_minutes=duration,
            ramp_smoothness=smoothness,
        )

    def _sun_events_for_today(self) -> tuple[float | None, float | None]:
        latitude, longitude, tz = self.sun_strength_plugin.resolve_location()
        today = datetime.now().astimezone(tz).date()
        if self._sun_events_cache_day != today:
            day_start = tz.localize(datetime(today.year, today.month, today.day, 0, 0))
            self._sun_events_cache = find_sun_events(day_start, latitude, longitude)
            self._sun_events_cache_day = today
        return self._sun_events_cache

    def change_monitor_brightness(self, brightness):
        runner().submit(self._apply_brightness, brightness, self._force_next['brightness'])

    def _apply_brightness(self, brightness, force=False):
        try:
            monitors = list(enumerate(monitorcontrol.get_monitors()))
        except (ValueError, monitorcontrol.VCPError) as e:
            self._on_apply_failed('brightness', e)
            return
        error = None
        for i, monitor in monitors:
            try:
                with monitor:
                    if force or monitor.get_luminance() != brightness:
                        monitor.set_luminance(brightness)
                        logging.info(f"Setting brightness to {brightness} on monitor {i}")
            except (ValueError, monitorcontrol.VCPError) as e:
                # Isolate per monitor: one still waking from suspend must not
                # block the others (that left one screen updated, one stale).
                logging.warning(f"Exception was caught while changing brightness on monitor {i}: {e}")
                error = e
        if error is not None:
            self._on_apply_failed('brightness', error)
        else:
            self._force_next['brightness'] = False
            self._set_health(HealthState.OK, self._mode_message())

    def change_monitor_contrast(self, contrast):
        runner().submit(self._apply_contrast, contrast, self._force_next['contrast'])

    def _apply_contrast(self, contrast, force=False):
        try:
            monitors = list(enumerate(monitorcontrol.get_monitors()))
        except (ValueError, monitorcontrol.VCPError) as e:
            self._on_apply_failed('contrast', e)
            return
        error = None
        for i, monitor in monitors:
            try:
                with monitor:
                    if force or monitor.get_contrast() != contrast:
                        monitor.set_contrast(contrast)
                        logging.info(f"Setting contrast to {contrast} on monitor {i}")
            except (ValueError, monitorcontrol.VCPError) as e:
                logging.warning(f"Exception was caught while changing contrast on monitor {i}: {e}")
                error = e
        if error is not None:
            self._on_apply_failed('contrast', error)
        else:
            self._force_next['contrast'] = False
            self._set_health(HealthState.OK, self._mode_message())

    def _on_apply_failed(self, axis: str, error: Exception) -> None:
        # Flag a retry so _tick re-drives this axis next tick in either mode,
        # and clear the auto dedup cache so a never-applied value isn't
        # mistaken for already-on-screen. Otherwise a transient VCP error
        # (e.g. a monitor still waking) leaves it at its old value forever.
        # _force_next is left set so the retry keeps forcing until it lands.
        self._needs_retry[axis] = True
        self._last_emitted[axis] = None
        self._set_health(HealthState.WARNING, f"Monitor error: {error}")

    def _desired_value(self, axis: str) -> int:
        manual = self.user_settings.get(axis, int)
        if manual is not None:
            return manual
        return max(0, min(100, int(round(self._auto_target(axis)))))

    def _start_wake_listener(self) -> None:
        if self._wake_listener is not None:
            return
        try:
            self._wake_listener = DisplayWakeListener(self)
        except Exception:
            # A missing wake listener only forfeits the on-wake re-assert;
            # the periodic tick and retry path still work. Don't fail the
            # whole plugin over it.
            logging.exception("Failed to start display wake listener")
            return
        self._wake_listener.woke.connect(self._on_display_woke)

    def _stop_wake_listener(self) -> None:
        if self._wake_listener is not None:
            self._wake_listener.close()
            self._wake_listener = None

    @Slot()
    def _on_display_woke(self) -> None:
        if not self.is_enabled():
            return
        logging.info("Display woke — re-asserting brightness and contrast")
        for axis in ('brightness', 'contrast'):
            value = self._desired_value(axis)
            self._force_next[axis] = True
            self._needs_retry[axis] = False
            self._last_emitted[axis] = value
            getattr(self, f'{axis}_changed').emit(value)

    def create_value_control_menu(self, title, axis, manual_slot, automatic_slot) -> QMenu:
        menu = QMenu(title, self)

        manual_value = self.user_settings.get(axis, int)
        current_value = self._last_emitted[axis] if self._last_emitted[axis] is not None else manual_value
        current_label = f'Current: {current_value}' if current_value is not None else 'Current: —'
        current_action = QAction(current_label, self)
        current_action.setEnabled(False)
        menu.addAction(current_action)
        menu.addSeparator()

        group = QActionGroup(self)
        group.setExclusive(True)

        automatic_action = QAction('Automatic', self)
        automatic_action.setCheckable(True)
        automatic_action.toggled.connect(automatic_slot)
        if manual_value is None:
            automatic_action.setChecked(True)

        group.addAction(automatic_action)
        menu.addAction(automatic_action)
        menu.addSeparator()
        for value_entry in range(0, 101, 10):
            action = QAction(str(value_entry), self)
            action.setCheckable(True)
            action.toggled.connect(partial(lambda is_checked, value=value_entry: manual_slot(is_checked, value)))
            if value_entry == manual_value:
                action.setChecked(True)
            group.addAction(action)
            menu.addAction(action)
        return menu

    def change_brightness_automatic(self, is_checked):
        if is_checked:
            self.user_settings.set('brightness', None)
            if self._current_health.state is HealthState.OK:
                self._set_health(HealthState.OK, self._mode_message())

    def change_contrast_automatic(self, is_checked):
        if is_checked:
            self.user_settings.set('contrast', None)
            if self._current_health.state is HealthState.OK:
                self._set_health(HealthState.OK, self._mode_message())

    def change_brightness_manual(self, is_checked, brightness_level):
        if not is_checked:
            return
        self.user_settings.set('brightness', brightness_level)
        if self._current_health.state is HealthState.OK:
            self._set_health(HealthState.OK, self._mode_message())
        self._last_emitted['brightness'] = brightness_level
        self.brightness_changed.emit(brightness_level)

    def change_contrast_manual(self, is_checked, contrast_level):
        if not is_checked:
            return
        self.user_settings.set('contrast', contrast_level)
        if self._current_health.state is HealthState.OK:
            self._set_health(HealthState.OK, self._mode_message())
        self._last_emitted['contrast'] = contrast_level
        self.contrast_changed.emit(contrast_level)

    def status_changed(self, status: bool) -> None:
        if status:
            if not self._tick_timer.isActive():
                self._tick_timer.start(TICK_MS)
            self._start_wake_listener()
        else:
            self._tick_timer.stop()
            self._stop_wake_listener()

    def closeEvent(self, event):
        self._tick_timer.stop()
        self._stop_wake_listener()
        self.sun_strength_plugin.close()
        event.accept()
