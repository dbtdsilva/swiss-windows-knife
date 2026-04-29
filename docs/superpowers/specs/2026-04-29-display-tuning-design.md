# Display tuning design

## Goal

Make the existing automatic brightness/contrast feel right without forcing a fall-back to a fixed value. Today, when "Automatic" is on for an axis, the monitor's luminance (or contrast) is set verbatim to the 0–100 sun strength computed from solar geometry. There are no bounds, no curve shape, no smoothing — so the only escape from "auto feels off" is to pick a fixed value, losing automation entirely.

The user wants tunable auto-mode behavior: bound the output range, reshape the response curve, and ease transitions. Brightness and contrast are tuned independently because they may behave differently. A live preview graph in the configuration dialog shows both curves through the day at the user's location, with a year scrubber so seasonal differences are visible during tuning.

## Behavior

Auto mode for each axis (brightness, contrast) is governed by three per-axis parameters and one shared parameter:

| Setting key | Range | Default | Meaning |
|---|---|---|---|
| `brightness_auto_min` | 0–100 | 0 | output floor when auto is on |
| `brightness_auto_max` | 0–100 | 100 | output ceiling when auto is on |
| `brightness_auto_gamma` | 0.3–3.0 | 1.0 | curve shape (γ<1 boosted, γ=1 linear, γ>1 lazy) |
| `contrast_auto_min` | 0–100 | 0 | same, contrast |
| `contrast_auto_max` | 0–100 | 100 | same, contrast |
| `contrast_auto_gamma` | 0.3–3.0 | 1.0 | same, contrast |
| `auto_smoothing_seconds` | 0–60 | 0 | ease time when target changes (shared) |

Defaults reproduce today's behavior exactly: `output = sun_strength` for the full 0–100 range with no easing. Nothing visibly changes on first run; tuning is opt-in via the new config panel.

The existing per-axis `brightness` / `contrast` settings (`None` = auto, `int` = fixed) keep their current semantics unchanged. The new keys take effect only while a given axis is in auto mode.

## Math

For each axis in auto mode:

```
target  = min + (max − min) × (sun_strength / 100)^γ
actual ←─ actual + (target − actual) × dt / smoothing_seconds
```

When `smoothing_seconds == 0`, `actual = target` instantly (no easing). The monitor receives the integer rounding of `actual`, but only when that integer changes from the last write — the existing "no DDC write if value unchanged" guard in `_apply_brightness` / `_apply_contrast` is preserved.

`dt` is the easing tick period (1 second). The closed-form behavior of the easing rule above with constant `target` is exponential decay: after `smoothing_seconds`, the actual value has closed ~63% of the gap, after `2 × smoothing_seconds` ~86%, etc.

## Config panel layout

A new `ConfigPanel` titled **Display tuning**, separate from the existing **Sun strength** location panel (lat/lng/timezone stays where it is — both panels appear as tabs in the unified Configuration dialog).

Layout, top to bottom:

```
┌─ Display tuning ──────────────────────────────────────────────┐
│  Brightness                                                    │
│    Min  ●────────  20    Max  ──────●──  80    γ ─●── 1.0     │
│                                                                │
│  Contrast                                                      │
│    Min  ●────────  20    Max  ──────●──  80    γ ─●── 1.0     │
│                                                                │
│  ┌─────────── 24-hour preview ─────────────────┐              │
│  │ 100│                                         │              │
│  │  80│       ╭──╮     ── Brightness            │              │
│  │  50│     ╭─╯  ╰─╮   ── Contrast              │              │
│  │  20│─────╯      ╰───                         │              │
│  │   0│                                         │              │
│  │     0    6    12    18    24                 │              │
│  └────────────────────────────────────────────────┘            │
│                                                                │
│  Smoothing  ●──── 0 s … 60 s                                  │
│  Day of year  ●─────────────────  Apr 29                      │
└────────────────────────────────────────────────────────────────┘
```

- Min and Max are `QSlider` widgets, range 0–100. The Max slider is constrained to be ≥ Min (and vice versa) — moving one above/below the other clamps the partner.
- γ is a `QSlider` with logarithmic mapping from slider position 0–100 → γ ∈ [0.3, 3.0], so γ = 1.0 sits at the slider midpoint and small drags near 1.0 don't feel coarse.
- The graph is a single shared widget showing both curves on the same 0–100 y-axis; legend identifies the colors.
- Smoothing is one shared slider (0–60 s).
- Day-of-year is a shared scrubber (1–366) with a label that resolves to a date string (e.g. "Apr 29"). Defaults to today; changing it recomputes both graph lines for the new date's solar geometry.
- A vertical "now" marker is drawn on the graph only when the scrubber is on today's date.
- All control changes update the graph live without writing to settings. `apply()` writes all new keys atomically when the user clicks OK on the Configuration dialog.

## Plumbing

`DisplayImageTunerPlugin` (`src/plugins/display_image_tuner/image_tuner_plugin.py`):

- Drop the direct `sun_strength_changed → brightness_changed.emit` wiring done by `change_brightness_automatic` / `change_contrast_automatic`. Auto-on/auto-off becomes pure state — set the `brightness` / `contrast` user setting to `None` (auto) or a fixed int (fixed), as today.
- Cache the latest `sun_strength` in a member (`_cached_sun: int | None`) — `sun_strength_changed` is connected only to a setter.
- Add a 1 Hz `QTimer` tick. Each tick, for each axis whose setting is `None` (auto):
  1. Compute `target` from `_cached_sun` and the per-axis `min`, `max`, `γ` settings.
  2. Move the float-tracked `_actual_<axis>` toward `target` by `1 / smoothing_seconds` (or snap to `target` if `smoothing_seconds == 0`).
  3. If `round(_actual_<axis>)` differs from the last emitted value, emit `<axis>_changed` and update the last-emitted cache.
- The fixed-value path is unchanged: clicking a value in the tray submenu sets the user setting and emits `<axis>_changed` immediately. Switching back to Auto seeds `_actual_<axis>` from the current fixed value so the easing has a sensible starting point.
- Cold start (auto already on at app launch, no fixed value to seed from): `_actual_<axis>` is initialized to `None`. The first tick that finds a valid `_cached_sun` snaps `_actual_<axis>` to `target` and emits — no easing on the very first apply, regardless of `smoothing_seconds`. Subsequent ticks ease normally.

Pure-function helper `compute_target(sun: float, min: int, max: int, gamma: float) -> float` lives next to the plugin (e.g. `curve.py`) and is unit-testable without Qt.

`SunStrengthNotifier` (`src/plugins/display_image_tuner/sun_strength_notifier.py`):

- Extract a small `compute_sun_strength(when: datetime, lat: float, lng: float) -> int` helper from `calculate_sun_strength`. The existing instance method becomes a thin wrapper that calls the helper with `datetime.now()` and the current settings — same emit behavior as today.
- The new helper is what the graph widget uses to plot the curve at arbitrary datetimes.

New file `src/plugins/display_image_tuner/display_tuning_panel.py`:

- `DisplayTuningConfigPanel(ConfigPanel)` — the panel described above.
- `DisplayTuningPreview(QWidget)` — the graph widget. `paintEvent` draws axes, gridlines, two `QPainterPath` lines (96 sample points at 15-minute resolution), legend, and the optional "now" marker. Inputs are the current control values plus the day-of-year and a callable that returns sun strength at a given datetime — so the widget itself is decoupled from `SunStrengthNotifier`.
- `DisplayImageTunerPlugin.retrieve_config_panels` returns `[SunLocationConfigPanel(...), DisplayTuningConfigPanel(...)]`.

## Tests

Under `tests/`:

- `test_display_tuner_curve.py` — `compute_target` across a matrix of `(sun, min, max, gamma)` checking known points: γ=1 produces a linear ramp; γ=0.5 produces output > linear at mid-sun; γ=2 produces output < linear at mid-sun; clamps at `min` for sun=0 and `max` for sun=100; out-of-range gamma clamped or rejected (decision: clamp into [0.3, 3.0]).
- `test_display_tuner_easing.py` — one-tick easing: snap to target when smoothing=0; ~63% of gap closed after `smoothing_seconds` ticks; never overshoots when target is constant.

UI rendering of the graph is not unit-tested (visual). Manual verification is sufficient.

## Out of scope

- Other curve shapes (S-curve, keyframe-based) — design rejected for now in favor of a single γ knob. Revisit if the gamma curve proves insufficient.
- Multi-day history view — the graph only shows a single 24-hour window; the year scrubber lets the user explore different dates without storing history.
- Cloud / weather adjustment — the sun strength model is purely solar geometry; no external data sources.
- Per-monitor tuning — settings apply uniformly to all detected monitors, matching today's behavior.
