# Display tuning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add tunable auto-mode for brightness/contrast (per-axis min/max/gamma plus shared smoothing) with a live preview graph showing both curves through the day at the user's location, with a year scrubber.

**Architecture:** Pure curve and easing math live in a new `curve.py` next to the existing image tuner plugin; `DisplayImageTunerPlugin` gains a 1 Hz timer that applies the curve and eases the float-tracked output toward the target each tick when the axis is in auto mode. A new `DisplayTuningConfigPanel` carries the controls plus a `DisplayTuningPreview` `QPainter`-based widget that plots both curves for an arbitrary date by reusing a date-parameterised `compute_sun_strength` helper extracted from `SunStrengthNotifier`. Defaults (min=0, max=100, γ=1.0, smoothing=0) reproduce today's behavior exactly.

**Tech Stack:** PySide6 (Qt timers, QWidget paintEvent with QPainter, ConfigPanel), pysolar (existing solar geometry), pytest + pytest-qt (existing).

**Spec:** `docs/superpowers/specs/2026-04-29-display-tuning-design.md`

---

### Task 1: Curve math (`compute_target`)

**Files:**
- Create: `src/plugins/display_image_tuner/curve.py`
- Test: `tests/test_display_tuner_curve.py`

- [ ] **Step 1: Write the failing tests**

Write `tests/test_display_tuner_curve.py`:

```python
import pytest

from src.plugins.display_image_tuner.curve import compute_target


@pytest.mark.parametrize("sun, expected", [
    (0, 0.0),
    (50, 50.0),
    (100, 100.0),
])
def test_compute_target_linear_full_range(sun, expected):
    assert compute_target(sun, min_value=0, max_value=100, gamma=1.0) == pytest.approx(expected)


@pytest.mark.parametrize("sun, expected", [
    (0, 20.0),
    (50, 50.0),
    (100, 80.0),
])
def test_compute_target_linear_clamped(sun, expected):
    assert compute_target(sun, min_value=20, max_value=80, gamma=1.0) == pytest.approx(expected)


def test_compute_target_boosted_gamma_above_linear():
    linear = compute_target(50, min_value=0, max_value=100, gamma=1.0)
    boosted = compute_target(50, min_value=0, max_value=100, gamma=0.5)
    assert boosted > linear


def test_compute_target_lazy_gamma_below_linear():
    linear = compute_target(50, min_value=0, max_value=100, gamma=1.0)
    lazy = compute_target(50, min_value=0, max_value=100, gamma=2.0)
    assert lazy < linear


def test_compute_target_clamps_at_min_when_sun_zero():
    assert compute_target(0, min_value=20, max_value=80, gamma=2.0) == pytest.approx(20.0)


def test_compute_target_clamps_at_max_when_sun_full():
    assert compute_target(100, min_value=20, max_value=80, gamma=0.5) == pytest.approx(80.0)


def test_compute_target_below_zero_sun_clamps_to_min():
    assert compute_target(-10, min_value=20, max_value=80, gamma=1.0) == pytest.approx(20.0)


def test_compute_target_above_hundred_sun_clamps_to_max():
    assert compute_target(150, min_value=20, max_value=80, gamma=1.0) == pytest.approx(80.0)


def test_compute_target_min_equals_max_returns_constant():
    assert compute_target(0, min_value=50, max_value=50, gamma=1.0) == pytest.approx(50.0)
    assert compute_target(73, min_value=50, max_value=50, gamma=2.5) == pytest.approx(50.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./env/Scripts/python.exe -m pytest tests/test_display_tuner_curve.py -v`
Expected: collection error / import error (`curve` module does not exist).

- [ ] **Step 3: Write minimal implementation**

Write `src/plugins/display_image_tuner/curve.py`:

```python
"""Pure-function math for the auto-mode display tuner.

`compute_target` maps a 0-100 sun strength to a 0-100 monitor value via a
gamma curve clamped to a configurable [min_value, max_value] range. No Qt,
no I/O — safe to unit-test in isolation.
"""
from __future__ import annotations


def compute_target(
    sun: float,
    *,
    min_value: int,
    max_value: int,
    gamma: float,
) -> float:
    s = max(0.0, min(100.0, float(sun))) / 100.0
    shaped = s ** gamma
    return float(min_value) + (float(max_value) - float(min_value)) * shaped
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./env/Scripts/python.exe -m pytest tests/test_display_tuner_curve.py -v`
Expected: all 11 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/plugins/display_image_tuner/curve.py tests/test_display_tuner_curve.py
git commit -m "feat: add compute_target gamma-curve helper for auto display tuner"
```

---

### Task 2: Easing math (`ease`)

**Files:**
- Modify: `src/plugins/display_image_tuner/curve.py`
- Test: `tests/test_display_tuner_easing.py`

- [ ] **Step 1: Write the failing tests**

Write `tests/test_display_tuner_easing.py`:

```python
import pytest

from src.plugins.display_image_tuner.curve import ease


def test_ease_snaps_to_target_when_smoothing_zero():
    assert ease(actual=10.0, target=80.0, dt=1.0, smoothing_seconds=0.0) == pytest.approx(80.0)


def test_ease_snaps_to_target_when_smoothing_negative():
    assert ease(actual=10.0, target=80.0, dt=1.0, smoothing_seconds=-5.0) == pytest.approx(80.0)


def test_ease_moves_toward_target():
    out = ease(actual=0.0, target=100.0, dt=1.0, smoothing_seconds=10.0)
    assert 0.0 < out < 100.0


def test_ease_closes_proportional_fraction_of_gap_per_tick():
    # smoothing=10s, dt=1s -> exactly 1/10 of the gap closed per tick
    out = ease(actual=0.0, target=100.0, dt=1.0, smoothing_seconds=10.0)
    assert out == pytest.approx(10.0)


def test_ease_does_not_overshoot_when_target_above():
    actual = 0.0
    for _ in range(1000):
        actual = ease(actual=actual, target=50.0, dt=1.0, smoothing_seconds=5.0)
    assert actual <= 50.0
    assert actual == pytest.approx(50.0, abs=1e-3)


def test_ease_does_not_overshoot_when_target_below():
    actual = 100.0
    for _ in range(1000):
        actual = ease(actual=actual, target=50.0, dt=1.0, smoothing_seconds=5.0)
    assert actual >= 50.0
    assert actual == pytest.approx(50.0, abs=1e-3)


def test_ease_already_at_target_stays_at_target():
    assert ease(actual=42.0, target=42.0, dt=1.0, smoothing_seconds=10.0) == pytest.approx(42.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./env/Scripts/python.exe -m pytest tests/test_display_tuner_easing.py -v`
Expected: ImportError — `ease` not defined in `curve`.

- [ ] **Step 3: Add `ease` to `curve.py`**

Append to `src/plugins/display_image_tuner/curve.py`:

```python
def ease(
    actual: float,
    target: float,
    *,
    dt: float,
    smoothing_seconds: float,
) -> float:
    if smoothing_seconds <= 0.0:
        return float(target)
    fraction = dt / smoothing_seconds
    if fraction >= 1.0:
        return float(target)
    return float(actual) + (float(target) - float(actual)) * fraction
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./env/Scripts/python.exe -m pytest tests/test_display_tuner_easing.py -v`
Expected: all 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/plugins/display_image_tuner/curve.py tests/test_display_tuner_easing.py
git commit -m "feat: add ease helper for smoothing auto display values"
```

---

### Task 3: Gamma slider mapping

**Files:**
- Modify: `src/plugins/display_image_tuner/curve.py`
- Test: `tests/test_display_tuner_gamma_slider.py`

The slider is symmetric in log space: γ = 1/3 at slider 0, γ = 1.0 at slider 50, γ = 3.0 at slider 100. The spec range "0.3–3.0" is approximate; precise mapping uses 1/3 to 3 so the slider is symmetric around γ=1.0.

- [ ] **Step 1: Write the failing tests**

Write `tests/test_display_tuner_gamma_slider.py`:

```python
import pytest

from src.plugins.display_image_tuner.curve import gamma_from_slider, slider_from_gamma


def test_slider_zero_gives_one_third():
    assert gamma_from_slider(0) == pytest.approx(1 / 3, rel=1e-6)


def test_slider_fifty_gives_one():
    assert gamma_from_slider(50) == pytest.approx(1.0, rel=1e-6)


def test_slider_hundred_gives_three():
    assert gamma_from_slider(100) == pytest.approx(3.0, rel=1e-6)


def test_slider_clamps_below_zero():
    assert gamma_from_slider(-20) == pytest.approx(1 / 3, rel=1e-6)


def test_slider_clamps_above_hundred():
    assert gamma_from_slider(150) == pytest.approx(3.0, rel=1e-6)


@pytest.mark.parametrize("gamma", [1 / 3, 0.5, 0.8, 1.0, 1.5, 2.0, 3.0])
def test_slider_round_trip(gamma):
    assert gamma_from_slider(slider_from_gamma(gamma)) == pytest.approx(gamma, rel=1e-3)


def test_slider_from_gamma_clamps_below_one_third():
    assert slider_from_gamma(0.1) == 0


def test_slider_from_gamma_clamps_above_three():
    assert slider_from_gamma(10.0) == 100
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./env/Scripts/python.exe -m pytest tests/test_display_tuner_gamma_slider.py -v`
Expected: ImportError — `gamma_from_slider`/`slider_from_gamma` not defined.

- [ ] **Step 3: Add the helpers to `curve.py`**

Append to `src/plugins/display_image_tuner/curve.py`:

```python
import math

GAMMA_MIN = 1 / 3
GAMMA_MAX = 3.0
_LN3 = math.log(3.0)


def gamma_from_slider(slider_pos: int) -> float:
    pos = max(0, min(100, int(slider_pos)))
    # Symmetric in log space: pos=0 -> 1/3, pos=50 -> 1, pos=100 -> 3
    return math.exp(((pos - 50) / 50.0) * _LN3)


def slider_from_gamma(gamma: float) -> int:
    g = max(GAMMA_MIN, min(GAMMA_MAX, float(gamma)))
    pos = round(50.0 + (math.log(g) / _LN3) * 50.0)
    return max(0, min(100, int(pos)))
```

Note: the bare `import math` at the bottom of the file is fine for now; if a future change requires it earlier, lift the import to the top of the module.

- [ ] **Step 4: Run tests to verify they pass**

Run: `./env/Scripts/python.exe -m pytest tests/test_display_tuner_gamma_slider.py -v`
Expected: all 9 tests pass.

- [ ] **Step 5: Run full curve test file together**

Run: `./env/Scripts/python.exe -m pytest tests/test_display_tuner_curve.py tests/test_display_tuner_easing.py tests/test_display_tuner_gamma_slider.py -v`
Expected: all 27 tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/plugins/display_image_tuner/curve.py tests/test_display_tuner_gamma_slider.py
git commit -m "feat: add log-symmetric gamma slider mapping helpers"
```

---

### Task 4: Extract `compute_sun_strength` helper

**Files:**
- Modify: `src/plugins/display_image_tuner/sun_strength_notifier.py`
- Test: `tests/test_sun_strength_helper.py`

Today, `SunStrengthNotifier.calculate_sun_strength` reads `datetime.now()` and the user's lat/lng/timezone, then maps `pysolar` output to a 0–100 integer. Extract a pure module-level helper that takes the datetime and location explicitly so the graph widget can call it with arbitrary dates.

- [ ] **Step 1: Write the failing test**

Write `tests/test_sun_strength_helper.py`:

```python
from datetime import datetime

import pytz

from src.plugins.display_image_tuner.sun_strength_notifier import compute_sun_strength


def test_compute_sun_strength_zero_at_midnight_local():
    # Midnight in Lausanne -> sun is below horizon -> strength is 0
    when = pytz.timezone("Europe/Zurich").localize(datetime(2026, 6, 21, 0, 0, 0))
    val = compute_sun_strength(when, latitude=46.521410, longitude=6.632273)
    assert val == 0


def test_compute_sun_strength_positive_at_solar_noon_summer():
    when = pytz.timezone("Europe/Zurich").localize(datetime(2026, 6, 21, 12, 30, 0))
    val = compute_sun_strength(when, latitude=46.521410, longitude=6.632273)
    assert val > 0
    assert val <= 100


def test_compute_sun_strength_capped_at_one_hundred():
    # Equator at solar noon on equinox should still be capped at 100
    when = pytz.timezone("UTC").localize(datetime(2026, 3, 20, 12, 0, 0))
    val = compute_sun_strength(when, latitude=0.0, longitude=0.0)
    assert val == 100


def test_compute_sun_strength_lower_in_winter_than_summer_at_same_hour():
    tz = pytz.timezone("Europe/Zurich")
    summer = compute_sun_strength(
        tz.localize(datetime(2026, 6, 21, 13, 0)),
        latitude=46.521410, longitude=6.632273,
    )
    winter = compute_sun_strength(
        tz.localize(datetime(2026, 12, 21, 13, 0)),
        latitude=46.521410, longitude=6.632273,
    )
    assert winter < summer
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./env/Scripts/python.exe -m pytest tests/test_sun_strength_helper.py -v`
Expected: ImportError — `compute_sun_strength` not exported.

- [ ] **Step 3: Refactor the notifier**

Replace `src/plugins/display_image_tuner/sun_strength_notifier.py` with:

```python
from datetime import datetime
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import QTimer, Signal
import pytz
from ...base.base_widget import BaseWidget
from ...base.user_settings import UserSettings
from pysolar import solar, radiation
import logging


DEFAULT_LATITUDE = 46.521410
DEFAULT_LONGITUDE = 6.632273
DEFAULT_TIMEZONE = 'Europe/Zurich'
ALTITUDE_OFFSET_DEG = 5


def compute_sun_strength(when: datetime, latitude: float, longitude: float) -> int:
    """Compute 0-100 sun strength at `when` for `(latitude, longitude)`.

    Mirrors the original mapping: solar altitude (with a 5deg offset for
    horizon haze) feeds into pysolar's direct-radiation model; the 0-600
    W/m^2 band is linearly mapped to 0-100 and capped at 100.

    `when` MUST be timezone-aware. The function converts to UTC internally.
    """
    altitude = solar.get_altitude(latitude, longitude, when) + ALTITUDE_OFFSET_DEG
    utc_naive = when.astimezone(pytz.utc).replace(tzinfo=None)
    power = radiation.get_radiation_direct(utc_naive, altitude)
    return int(power / 6.0) if power < 600 else 100


class SunStrengthNotifier(BaseWidget):

    sun_strength_changed = Signal(int)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.user_settings = UserSettings.instance()
        self._ensure_defaults()

        self.timer = QTimer()
        self.timer.timeout.connect(self.calculate_sun_strength)
        self.timer.start(1000 * 60)
        self.calculate_sun_strength()

    def _ensure_defaults(self) -> None:
        if not self.user_settings.has_key('sun_latitude'):
            self.user_settings.set('sun_latitude', DEFAULT_LATITUDE)
        if not self.user_settings.has_key('sun_longitude'):
            self.user_settings.set('sun_longitude', DEFAULT_LONGITUDE)
        if not self.user_settings.has_key('sun_timezone'):
            self.user_settings.set('sun_timezone', DEFAULT_TIMEZONE)

    def _resolve_location(self) -> tuple[float, float, "pytz.tzinfo.BaseTzInfo"]:
        try:
            latitude = float(self.user_settings.get('sun_latitude'))  # type: ignore[arg-type]
            longitude = float(self.user_settings.get('sun_longitude'))  # type: ignore[arg-type]
            timezone = pytz.timezone(str(self.user_settings.get('sun_timezone')))
            return latitude, longitude, timezone
        except (TypeError, ValueError, pytz.UnknownTimeZoneError):
            logging.warning("Invalid sun-strength settings, falling back to defaults")
            return DEFAULT_LATITUDE, DEFAULT_LONGITUDE, pytz.timezone(DEFAULT_TIMEZONE)

    def calculate_sun_strength(self):
        latitude, longitude, timezone = self._resolve_location()
        when = datetime.now().astimezone(timezone)
        current_value = compute_sun_strength(when, latitude, longitude)
        self.sun_strength_changed.emit(current_value)
        logging.debug(f'Sun strength has changed to {current_value}')

    def closeEvent(self, event):
        self.timer.stop()
        event.accept()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./env/Scripts/python.exe -m pytest tests/test_sun_strength_helper.py -v`
Expected: all 4 tests pass.

- [ ] **Step 5: Run full test suite to verify the refactor didn't regress anything**

Run: `QT_QPA_PLATFORM=offscreen ./env/Scripts/python.exe -m pytest tests/ -q`
Expected: all tests pass (existing + new).

- [ ] **Step 6: Commit**

```bash
git add src/plugins/display_image_tuner/sun_strength_notifier.py tests/test_sun_strength_helper.py
git commit -m "refactor: extract date-parameterised compute_sun_strength helper"
```

---

### Task 5: New settings defaults

**Files:**
- Modify: `src/plugins/display_image_tuner/image_tuner_plugin.py:25-35`

Initialize the seven new keys (`<axis>_auto_min`, `<axis>_auto_max`, `<axis>_auto_gamma` for brightness and contrast, plus shared `auto_smoothing_seconds`) lazily in the plugin's `__init__` so existing installs don't lose data.

- [ ] **Step 1: Add the defaults**

In `src/plugins/display_image_tuner/image_tuner_plugin.py`, replace the body of `__init__` from `self.user_settings = UserSettings.instance()` through the `logging.info` calls with:

```python
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
```

- [ ] **Step 2: Smoke test the import chain**

Run: `QT_QPA_PLATFORM=offscreen ./env/Scripts/python.exe -c "from src.plugins.display_image_tuner.image_tuner_plugin import DisplayImageTunerPlugin; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add src/plugins/display_image_tuner/image_tuner_plugin.py
git commit -m "feat: initialise default keys for tunable auto display settings"
```

---

### Task 6: Easing tick + curve application

**Files:**
- Modify: `src/plugins/display_image_tuner/image_tuner_plugin.py`

Replace the direct `sun_strength_changed → brightness/contrast_changed` wiring (currently set up by `change_brightness_automatic` and `change_contrast_automatic`) with: a cached `_sun` member, a 1 Hz QTimer, per-axis float-tracked `_actual` state, and curve+ease application on each tick.

The fixed-value menu path (`change_brightness_manual`, `change_contrast_manual`) is unchanged — they still write the user setting and emit immediately.

- [ ] **Step 1: Replace the plugin file**

Overwrite `src/plugins/display_image_tuner/image_tuner_plugin.py` with:

```python
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
```

- [ ] **Step 2: Lint**

Run: `./env/Scripts/python.exe -m flake8 --max-complexity=10 --max-line-length=127 src/plugins/display_image_tuner/image_tuner_plugin.py`
Expected: no output.

- [ ] **Step 3: Smoke test the import + a 1-tick simulation**

Run:

```bash
QT_QPA_PLATFORM=offscreen ./env/Scripts/python.exe -c "
import sys
from PySide6.QtWidgets import QApplication, QWidget
app = QApplication(sys.argv)
from src.plugins.display_image_tuner.image_tuner_plugin import DisplayImageTunerPlugin
parent = QWidget()
plugin = DisplayImageTunerPlugin(parent)
plugin._sun = 50
plugin._tick()
print('actual after one tick (snap, smoothing=0):', plugin._actual)
print('last_emitted:', plugin._last_emitted)
"
```

Expected: `_actual['brightness']` and `_actual['contrast']` are 50.0 (since the user is currently in auto-mode for brightness with min=0/max=100/γ=1, and contrast may be in fixed mode depending on settings — adjust the assertion mentally based on what's in your registry). No exceptions.

- [ ] **Step 4: Restart the app to make sure it boots**

Run (kill any running tray + relaunch in background, per project convention):

```bash
powershell -NoProfile -Command "Get-Process SwissWindowsKnife -ErrorAction SilentlyContinue | Stop-Process -Force; Get-Process | Where-Object { \$_.Path -like '*\swiss-windows-knife\env\Scripts\python.exe' } | Stop-Process -Force"
./env/Scripts/python.exe -m src.swiss_windows_knife &
sleep 3
```

Confirm in the launched process's stdout that the startup log line `Starting widget..` and the brightness/contrast init lines appear without errors.

- [ ] **Step 5: Commit**

```bash
git add src/plugins/display_image_tuner/image_tuner_plugin.py
git commit -m "feat: apply gamma curve and easing to auto display values"
```

---

### Task 7: `DisplayTuningPreview` graph widget

**Files:**
- Create: `src/plugins/display_image_tuner/display_tuning_panel.py`

The widget plots both brightness and contrast curves on the same axes for a chosen day-of-year. It accepts a sun-strength callable so the panel — which knows the user's lat/lng — can wire it without the widget importing `UserSettings`.

- [ ] **Step 1: Create the file**

Write `src/plugins/display_image_tuner/display_tuning_panel.py`:

```python
from __future__ import annotations

from calendar import isleap
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Callable

import pytz
from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QFormLayout, QGroupBox, QHBoxLayout, QLabel, QSlider, QVBoxLayout, QWidget,
)

from ...base.config_panel import ConfigPanel
from ...base.user_settings import UserSettings
from .curve import compute_target, gamma_from_slider, slider_from_gamma
from .sun_strength_notifier import (
    DEFAULT_LATITUDE, DEFAULT_LONGITUDE, DEFAULT_TIMEZONE, compute_sun_strength,
)


SAMPLES_PER_DAY = 96  # 15-minute resolution
COLOR_BRIGHTNESS = QColor(255, 191, 0)   # amber
COLOR_CONTRAST = QColor(64, 156, 255)    # blue
COLOR_AXIS = QColor(120, 120, 120)
COLOR_GRID = QColor(60, 60, 60)
COLOR_NOW = QColor(220, 80, 80)


@dataclass
class AxisCurveSettings:
    min_value: int
    max_value: int
    gamma: float


SunStrengthAt = Callable[[datetime], int]


class DisplayTuningPreview(QWidget):
    """Plots brightness and contrast curves through a single day."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(480, 220)

        self._brightness = AxisCurveSettings(0, 100, 1.0)
        self._contrast = AxisCurveSettings(0, 100, 1.0)
        self._date: datetime | None = None
        self._sun_at: SunStrengthAt | None = None
        self._show_now_marker = False

    def set_brightness(self, settings: AxisCurveSettings) -> None:
        self._brightness = settings
        self.update()

    def set_contrast(self, settings: AxisCurveSettings) -> None:
        self._contrast = settings
        self.update()

    def set_date(self, day_start_local: datetime, *, show_now_marker: bool) -> None:
        self._date = day_start_local
        self._show_now_marker = show_now_marker
        self.update()

    def set_sun_callable(self, sun_at: SunStrengthAt) -> None:
        self._sun_at = sun_at
        self.update()

    def paintEvent(self, event) -> None:  # noqa: D401
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        plot_rect = self._plot_rect()
        self._draw_axes_and_grid(painter, plot_rect)

        if self._date is None or self._sun_at is None:
            painter.end()
            return

        b_path = self._build_path(plot_rect, self._brightness)
        c_path = self._build_path(plot_rect, self._contrast)

        painter.setPen(QPen(COLOR_BRIGHTNESS, 2.0))
        painter.drawPath(b_path)
        painter.setPen(QPen(COLOR_CONTRAST, 2.0))
        painter.drawPath(c_path)

        self._draw_legend(painter, plot_rect)

        if self._show_now_marker:
            self._draw_now_marker(painter, plot_rect)

        painter.end()

    def _plot_rect(self) -> QRectF:
        margin_left = 32
        margin_right = 12
        margin_top = 12
        margin_bottom = 24
        return QRectF(
            margin_left, margin_top,
            self.width() - margin_left - margin_right,
            self.height() - margin_top - margin_bottom,
        )

    def _draw_axes_and_grid(self, painter: QPainter, rect: QRectF) -> None:
        painter.setPen(QPen(COLOR_GRID, 1.0))
        for y_pct in (0, 25, 50, 75, 100):
            y = rect.bottom() - rect.height() * (y_pct / 100.0)
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
        for hour in (0, 6, 12, 18, 24):
            x = rect.left() + rect.width() * (hour / 24.0)
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))

        painter.setPen(QPen(COLOR_AXIS, 1.0))
        painter.drawRect(rect)

        painter.setPen(QPen(COLOR_AXIS, 1.0))
        for y_pct in (0, 50, 100):
            y = rect.bottom() - rect.height() * (y_pct / 100.0)
            painter.drawText(QPointF(4, y + 4), str(y_pct))
        for hour in (0, 6, 12, 18, 24):
            x = rect.left() + rect.width() * (hour / 24.0)
            painter.drawText(QPointF(x - 6, rect.bottom() + 16), f"{hour}h")

    def _build_path(self, rect: QRectF, settings: AxisCurveSettings) -> QPainterPath:
        assert self._date is not None and self._sun_at is not None
        path = QPainterPath()
        for i in range(SAMPLES_PER_DAY + 1):
            hour_fraction = i / SAMPLES_PER_DAY
            t = self._date + timedelta(hours=24 * hour_fraction)
            sun = self._sun_at(t)
            value = compute_target(
                sun,
                min_value=settings.min_value,
                max_value=settings.max_value,
                gamma=settings.gamma,
            )
            x = rect.left() + rect.width() * hour_fraction
            y = rect.bottom() - rect.height() * (value / 100.0)
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        return path

    def _draw_legend(self, painter: QPainter, rect: QRectF) -> None:
        x = rect.right() - 130
        y = rect.top() + 14
        painter.setPen(QPen(COLOR_BRIGHTNESS, 3.0))
        painter.drawLine(QPointF(x, y), QPointF(x + 18, y))
        painter.setPen(QPen(COLOR_AXIS, 1.0))
        painter.drawText(QPointF(x + 24, y + 4), "Brightness")
        y += 14
        painter.setPen(QPen(COLOR_CONTRAST, 3.0))
        painter.drawLine(QPointF(x, y), QPointF(x + 18, y))
        painter.setPen(QPen(COLOR_AXIS, 1.0))
        painter.drawText(QPointF(x + 24, y + 4), "Contrast")

    def _draw_now_marker(self, painter: QPainter, rect: QRectF) -> None:
        now = datetime.now().astimezone()
        hour_fraction = (now.hour + now.minute / 60.0) / 24.0
        x = rect.left() + rect.width() * hour_fraction
        painter.setPen(QPen(COLOR_NOW, 1.0, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
```

- [ ] **Step 2: Smoke test that the widget paints without error**

Run:

```bash
QT_QPA_PLATFORM=offscreen ./env/Scripts/python.exe -c "
import sys
from datetime import datetime
import pytz
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPixmap
app = QApplication(sys.argv)
from src.plugins.display_image_tuner.display_tuning_panel import DisplayTuningPreview, AxisCurveSettings
from src.plugins.display_image_tuner.sun_strength_notifier import compute_sun_strength
w = DisplayTuningPreview()
w.set_brightness(AxisCurveSettings(20, 80, 0.7))
w.set_contrast(AxisCurveSettings(40, 90, 1.5))
tz = pytz.timezone('Europe/Zurich')
day_start = tz.localize(datetime(2026, 6, 21, 0, 0))
w.set_date(day_start, show_now_marker=False)
w.set_sun_callable(lambda when: compute_sun_strength(when, 46.5, 6.6))
w.resize(640, 240)
pm = QPixmap(w.size())
w.render(pm)
print('rendered, size:', pm.size().width(), pm.size().height())
"
```

Expected: prints `rendered, size: 640 240` with no exceptions.

- [ ] **Step 3: Lint**

Run: `./env/Scripts/python.exe -m flake8 --max-complexity=10 --max-line-length=127 src/plugins/display_image_tuner/display_tuning_panel.py`
Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add src/plugins/display_image_tuner/display_tuning_panel.py
git commit -m "feat: add DisplayTuningPreview widget plotting brightness/contrast curves"
```

---

### Task 8: `DisplayTuningConfigPanel`

**Files:**
- Modify: `src/plugins/display_image_tuner/display_tuning_panel.py`

Add the `ConfigPanel` subclass. It owns: per-axis Min/Max/γ sliders, the shared Smoothing slider, the day-of-year scrubber with date label, and the `DisplayTuningPreview` widget. Slider changes update the preview live; `apply()` validates and writes settings.

- [ ] **Step 1: Append the panel class**

All required imports (`date`, `isleap`, `pytz`, `QFormLayout`, `QGroupBox`, `QHBoxLayout`, `QLabel`, `QSlider`, `QVBoxLayout`, `ConfigPanel`, `UserSettings`, `gamma_from_slider`, `slider_from_gamma`, `DEFAULT_LATITUDE`, `DEFAULT_LONGITUDE`, `DEFAULT_TIMEZONE`, `compute_sun_strength`) are already at the top of the file from Task 7. Append the class to the bottom of `src/plugins/display_image_tuner/display_tuning_panel.py`:

```python
class DisplayTuningConfigPanel(ConfigPanel):

    title = "Display tuning"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._user_settings = UserSettings.instance()

        self._brightness_min = self._make_value_slider()
        self._brightness_max = self._make_value_slider()
        self._brightness_gamma = self._make_gamma_slider()
        self._brightness_min.setValue(self._read_int('brightness_auto_min', 0))
        self._brightness_max.setValue(self._read_int('brightness_auto_max', 100))
        self._brightness_gamma.setValue(slider_from_gamma(self._read_float('brightness_auto_gamma', 1.0)))

        self._contrast_min = self._make_value_slider()
        self._contrast_max = self._make_value_slider()
        self._contrast_gamma = self._make_gamma_slider()
        self._contrast_min.setValue(self._read_int('contrast_auto_min', 0))
        self._contrast_max.setValue(self._read_int('contrast_auto_max', 100))
        self._contrast_gamma.setValue(slider_from_gamma(self._read_float('contrast_auto_gamma', 1.0)))

        self._smoothing = QSlider(Qt.Orientation.Horizontal)
        self._smoothing.setRange(0, 60)
        self._smoothing.setValue(self._read_int('auto_smoothing_seconds', 0))

        self._day = QSlider(Qt.Orientation.Horizontal)
        self._day.setRange(1, 366)
        self._day.setValue(date.today().timetuple().tm_yday)
        self._day_label = QLabel(self._format_day(self._day.value()))

        self._preview = DisplayTuningPreview()
        self._preview.set_sun_callable(self._sun_strength_at)

        # Wire change signals -> preview refresh
        for w in (
            self._brightness_min, self._brightness_max, self._brightness_gamma,
            self._contrast_min, self._contrast_max, self._contrast_gamma,
            self._day,
        ):
            w.valueChanged.connect(self._refresh_preview)
        self._brightness_min.valueChanged.connect(
            lambda v: self._brightness_max.setValue(max(self._brightness_max.value(), v))
        )
        self._brightness_max.valueChanged.connect(
            lambda v: self._brightness_min.setValue(min(self._brightness_min.value(), v))
        )
        self._contrast_min.valueChanged.connect(
            lambda v: self._contrast_max.setValue(max(self._contrast_max.value(), v))
        )
        self._contrast_max.valueChanged.connect(
            lambda v: self._contrast_min.setValue(min(self._contrast_min.value(), v))
        )
        self._day.valueChanged.connect(lambda v: self._day_label.setText(self._format_day(v)))

        layout = QVBoxLayout(self)
        layout.addWidget(self._build_axis_group("Brightness", self._brightness_min,
                                                self._brightness_max, self._brightness_gamma))
        layout.addWidget(self._build_axis_group("Contrast", self._contrast_min,
                                                self._contrast_max, self._contrast_gamma))
        layout.addWidget(self._preview)

        shared = QGroupBox("Shared")
        shared_form = QFormLayout(shared)
        shared_form.addRow("Smoothing (s)", self._smoothing)
        day_row = QHBoxLayout()
        day_row.addWidget(self._day)
        day_row.addWidget(self._day_label)
        shared_form.addRow("Day of year", day_row)
        layout.addWidget(shared)

        self._refresh_preview()

    def _make_value_slider(self) -> QSlider:
        s = QSlider(Qt.Orientation.Horizontal)
        s.setRange(0, 100)
        return s

    def _make_gamma_slider(self) -> QSlider:
        s = QSlider(Qt.Orientation.Horizontal)
        s.setRange(0, 100)
        return s

    def _build_axis_group(self, title, min_w, max_w, gamma_w) -> QGroupBox:
        box = QGroupBox(title)
        form = QFormLayout(box)
        form.addRow("Min", min_w)
        form.addRow("Max", max_w)
        form.addRow("Curve (γ)", gamma_w)
        return box

    def _read_int(self, key: str, default: int) -> int:
        try:
            return int(self._user_settings.get(key))
        except (TypeError, ValueError):
            return default

    def _read_float(self, key: str, default: float) -> float:
        try:
            return float(self._user_settings.get(key))
        except (TypeError, ValueError):
            return default

    def _resolve_location(self) -> tuple[float, float, "pytz.tzinfo.BaseTzInfo"]:
        try:
            latitude = float(self._user_settings.get('sun_latitude'))
            longitude = float(self._user_settings.get('sun_longitude'))
            timezone = pytz.timezone(str(self._user_settings.get('sun_timezone')))
            return latitude, longitude, timezone
        except (TypeError, ValueError, pytz.UnknownTimeZoneError):
            return DEFAULT_LATITUDE, DEFAULT_LONGITUDE, pytz.timezone(DEFAULT_TIMEZONE)

    def _sun_strength_at(self, when):
        lat, lng, _ = self._resolve_location()
        return compute_sun_strength(when, lat, lng)

    def _format_day(self, day_of_year: int) -> str:
        # Use 2024 (leap year) so day=366 is always valid for the label.
        d = date(2024, 1, 1) + timedelta(days=day_of_year - 1)
        return d.strftime("%b %d")

    def _refresh_preview(self) -> None:
        _, _, tz = self._resolve_location()
        year = date.today().year
        last_day = 366 if isleap(year) else 365
        day_int = min(self._day.value(), last_day)
        day = date(year, 1, 1) + timedelta(days=day_int - 1)
        day_start = tz.localize(datetime(day.year, day.month, day.day, 0, 0))
        is_today = day == date.today()
        self._preview.set_date(day_start, show_now_marker=is_today)

        self._preview.set_brightness(AxisCurveSettings(
            min_value=self._brightness_min.value(),
            max_value=self._brightness_max.value(),
            gamma=gamma_from_slider(self._brightness_gamma.value()),
        ))
        self._preview.set_contrast(AxisCurveSettings(
            min_value=self._contrast_min.value(),
            max_value=self._contrast_max.value(),
            gamma=gamma_from_slider(self._contrast_gamma.value()),
        ))

    def apply(self) -> bool:
        self._user_settings.set('brightness_auto_min', self._brightness_min.value())
        self._user_settings.set('brightness_auto_max', self._brightness_max.value())
        self._user_settings.set('brightness_auto_gamma',
                                gamma_from_slider(self._brightness_gamma.value()))
        self._user_settings.set('contrast_auto_min', self._contrast_min.value())
        self._user_settings.set('contrast_auto_max', self._contrast_max.value())
        self._user_settings.set('contrast_auto_gamma',
                                gamma_from_slider(self._contrast_gamma.value()))
        self._user_settings.set('auto_smoothing_seconds', self._smoothing.value())
        return True
```

- [ ] **Step 2: Smoke test panel construction + preview render**

Run:

```bash
QT_QPA_PLATFORM=offscreen ./env/Scripts/python.exe -c "
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPixmap
app = QApplication(sys.argv)
from src.plugins.display_image_tuner.display_tuning_panel import DisplayTuningConfigPanel
panel = DisplayTuningConfigPanel()
panel.resize(640, 600)
pm = QPixmap(panel.size())
panel.render(pm)
print('panel rendered:', pm.size().width(), pm.size().height())
print('apply() returned:', panel.apply())
"
```

Expected: `panel rendered: 640 600` and `apply() returned: True`. No exceptions.

- [ ] **Step 3: Lint**

Run: `./env/Scripts/python.exe -m flake8 --max-complexity=10 --max-line-length=127 src/plugins/display_image_tuner/display_tuning_panel.py`
Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add src/plugins/display_image_tuner/display_tuning_panel.py
git commit -m "feat: add DisplayTuningConfigPanel with live preview graph"
```

---

### Task 9: Wire the panel into the plugin

**Files:**
- Modify: `src/plugins/display_image_tuner/image_tuner_plugin.py`

- [ ] **Step 1: Import and return the new panel**

Add to the imports in `image_tuner_plugin.py` (next to `from .sun_location_panel import SunLocationConfigPanel`):

```python
from .display_tuning_panel import DisplayTuningConfigPanel
```

Replace the existing `retrieve_config_panels` method body:

```python
    def retrieve_config_panels(self) -> list[ConfigPanel]:
        return [
            SunLocationConfigPanel(self.sun_strength_plugin, self),
            DisplayTuningConfigPanel(self),
        ]
```

- [ ] **Step 2: Lint**

Run: `./env/Scripts/python.exe -m flake8 --max-complexity=10 --max-line-length=127 src/plugins/display_image_tuner/image_tuner_plugin.py`
Expected: no output.

- [ ] **Step 3: Restart the app**

```bash
powershell -NoProfile -Command "Get-Process SwissWindowsKnife -ErrorAction SilentlyContinue | Stop-Process -Force; Get-Process | Where-Object { \$_.Path -like '*\swiss-windows-knife\env\Scripts\python.exe' } | Stop-Process -Force"
./env/Scripts/python.exe -m src.swiss_windows_knife &
sleep 3
```

Expected: process is up; opening Configuration shows two tabs: "Sun strength" and "Display tuning". The Display tuning tab renders both control groups, the preview graph, and the shared smoothing/day controls.

- [ ] **Step 4: Commit**

```bash
git add src/plugins/display_image_tuner/image_tuner_plugin.py
git commit -m "feat: surface DisplayTuningConfigPanel in the configuration dialog"
```

---

### Task 10: Manual end-to-end verification

**Files:** none — interactive test pass.

- [ ] **Step 1: Verify sliders move the preview live**

Open Configuration → Display tuning. Drag Brightness Min from 0 → 30. The amber line in the preview should rise off the bottom of the chart. Drag Brightness γ left (toward 1/3): line bows up. Drag right (toward 3): line bows down.

- [ ] **Step 2: Verify Min/Max coupling**

Drag Brightness Min above Brightness Max — Max should follow up. Drag Max below Min — Min should follow down. No crossing.

- [ ] **Step 3: Verify the year scrubber**

Drag Day of year to ~172 (Jun 21). Curve broadens (longer daylight, higher peak). Drag to ~355 (Dec 21). Curve narrows and peaks lower. Label updates to "Jun 21" / "Dec 21".

- [ ] **Step 4: Verify the now marker**

With Day on today's value, a dashed vertical line appears at the current hour. Move the slider one day off; the dashed line disappears.

- [ ] **Step 5: Verify Apply persists settings**

Pick a non-default config (e.g., Brightness Min=20, Max=80, γ=0.7, smoothing=10). Click OK. Reopen the dialog — values should round-trip back. Inspect the registry to confirm:

```bash
powershell -NoProfile -Command "Get-ItemProperty 'HKCU:\Software\Swiss Windows Knife\UserSettings' | Select-Object brightness_auto_min, brightness_auto_max, brightness_auto_gamma, contrast_auto_min, contrast_auto_max, contrast_auto_gamma, auto_smoothing_seconds | Format-List"
```

Expected: the values you saved.

- [ ] **Step 6: Verify the running monitor responds**

With both axes set to "Automatic" via the tray menus, observe over a few minutes that the monitor brightness/contrast match the predicted curve at the current time on the preview. With smoothing > 0, transitions over the next minute or two should be visibly gradual rather than stepped.

- [ ] **Step 7: Run the full test suite**

```bash
QT_QPA_PLATFORM=offscreen ./env/Scripts/python.exe -m pytest tests/ -q
```

Expected: all tests pass.

---

## Self-review notes

- **Spec coverage:** Settings keys (Task 5), curve math (Task 1), easing math (Task 2), gamma slider mapping (Task 3 — adds precision the spec hand-waved), `compute_sun_strength` extraction (Task 4), `DisplayImageTunerPlugin` plumbing changes (Tasks 5, 6, 9), `DisplayTuningPreview` (Task 7), `DisplayTuningConfigPanel` (Task 8), tests (Tasks 1–4), manual verification (Task 10). All spec sections covered.
- **Cold-start initialization** (added in spec self-review) is implemented in Task 6 via the `_actual[axis] is None` branch in `_tick`.
- **Min/Max coupling**: the spec calls for clamp-on-cross; implemented via paired `valueChanged` lambdas in Task 8.
- **Slider mapping for γ**: spec said "0.3–3.0", plan uses precise [1/3, 3] for log symmetry — close enough; documented in Task 3 commentary.
