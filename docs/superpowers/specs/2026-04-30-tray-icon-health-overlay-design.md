# Tray icon health overlay design

## Goal

Surface aggregate plugin health on the tray icon itself — a small coloured dot in the top-right corner — so the user sees a Warning or Error without opening the menu. The plugin-health-status feature already shipped a `Health: …` submenu (PR #16); this design adds the at-a-glance indicator that the parent design doc explicitly deferred ("Tray icon colour reflecting aggregate health … could be added later if the user wants ambient awareness without opening the menu").

## Behaviour

The tray icon always shows a coloured dot in its top-right corner reflecting the worst non-disabled health state across all plugins:

- **Green** — `HealthState.OK` for every enabled plugin.
- **Amber** — at least one plugin in `HealthState.WARNING` (and none in ERROR).
- **Red** — at least one plugin in `HealthState.ERROR`.

The dot is always visible (the user explicitly chose this over a hide-when-OK policy). DISABLED plugins do not contribute to the aggregate; if every plugin is DISABLED, the aggregate falls back to OK and the dot is green.

## Architecture

### Update mechanism — switch to a push model

The original plugin-health-status design committed to a pull-on-`aboutToShow` model: `_populate_main_menu` reads each plugin's `health()` when the user opens the menu. That's still correct for menu rendering, but it cannot drive the tray icon — the icon must update whenever any plugin's health changes, even if the menu is closed.

Add `health_changed = Signal()` on `BaseWidget` (no payload — receivers call `plugin.health()` to read the current value). The signal fires on every transition that changes the visible health:

- `_set_health` emits the signal when the new `HealthReport` differs from `self._current_health` (skips emission on no-op writes to avoid spurious icon repaints).
- `set_enabled` emits the signal whenever `_is_enabled` actually flips. The toggle changes what `health()` returns (DISABLED vs `_current_health`) without going through `_set_health`, so without this the tray icon would go stale on Plugin enable/disable. The existing early-return guard at the top of `set_enabled` (`if self._is_enabled == enabled: return`) ensures the emit only happens on genuine transitions.

`TrayWidget.__init__` connects each plugin's `health_changed` to a slot that:
1. Computes `aggregate_health(...)` over the current per-plugin reports.
2. Builds a new `QIcon` via `tray_icon_for_state(worst_state)` and calls `self._tray_icon.setIcon(...)`.

The slot also fires once during `__init__` (after `self._tray_icon` is set up) so the icon reflects the starting state without waiting for the first transition.

The menu's pull-on-`aboutToShow` path is unchanged. It happily reads the same `_current_health` attribute the signal-driven slot just refreshed; the two paths converge.

### Icon overlay

A new helper in `src/ui/health_icons.py`:

```python
@cache
def tray_icon_for_state(state: HealthState) -> QIcon:
    """Return the tray icon overlaid with a coloured dot for `state`."""
```

- Base: `QIcon(":/icons/coat-of-arms.ico").pixmap(64, 64)` — render at 64×64; Windows downsamples for the systray slot.
- Overlay: filled antialiased circle, no pen, fill = `_COLORS[state]`. Diameter 24 px (≈ 38 % of edge). Top-right anchor: bounding box at `(40, 0)` to `(64, 24)`.
- Compose: paint the base pixmap, then the overlay, into a fresh `QPixmap(64, 64)`. Wrap in a `QIcon` registered for both Normal and Disabled modes (matches the existing `icon_for_state` policy — defensive in case the systray ever exposes the icon as disabled).
- `@cache` keeps the icon stable across invocations (4 cached entries — one per `HealthState`).

The DISABLED colour is never produced as an aggregate (worst-state ignores DISABLED), but the helper still handles it for API symmetry and to keep the cache key space simple.

## Components

- **`src/base/base_widget.py`** — adds `health_changed = Signal()`. Emits from `_set_health` when the report actually changed, and from `set_enabled` when `_is_enabled` actually flips.
- **`src/ui/health_icons.py`** — adds `tray_icon_for_state(state)` next to the existing `icon_for_state(state)`.
- **`src/ui/tray_widget.py`** — connects each plugin's signal in `__init__`, adds a `_refresh_tray_icon()` slot, calls it once at the end of `__init__`.

## Data flow

```
plugin async event
    └── plugin._set_health(state, message)
              ├── self._current_health = HealthReport(...)
              └── self.health_changed.emit()         (only if value changed)
                          │
                          └── TrayWidget._refresh_tray_icon()
                                     ├── aggregate_health([p.health() for p in child_components])
                                     └── self._tray_icon.setIcon(tray_icon_for_state(worst_state))
```

## Error handling

- If `plugin.health()` raises during the slot, the slot catches the exception, logs `logging.exception`, and substitutes `HealthReport(WARNING, "health() failed")` for that plugin — same defensive pattern `_populate_main_menu` already uses.
- `setIcon` is idempotent; calling it with the same QIcon is a no-op.

## Testing

- `tests/test_base_widget.py` — new tests:
  - `test_health_changed_emits_on_state_change` — `_set_health(WARNING, "x")` emits exactly once when prior state was OK.
  - `test_health_changed_emits_on_message_change` — `_set_health(OK, "Manual 60")` after `_set_health(OK, "Auto")` emits.
  - `test_health_changed_does_not_emit_on_noop` — repeating the same `_set_health` call does not emit.
  - `test_health_changed_emits_on_set_enabled_transition` — `set_enabled(False)` from an enabled state emits exactly once.
  - `test_health_changed_does_not_emit_on_set_enabled_noop` — calling `set_enabled` with the current value does not emit.
- `tests/test_health_icons.py` — new tests:
  - `test_tray_icon_for_state_returns_non_null` — iterate `HealthState`, assert non-null.
  - `test_tray_icon_for_state_is_cached` — identity check on repeated calls.
- `tests/test_tray_widget_health.py` — new test:
  - `test_tray_icon_refreshes_on_plugin_health_change` — given two stub plugins, fire one's `health_changed` after flipping it to WARNING, assert the tray's `setIcon` was called with the amber-overlay icon. Use a `_TrayForTest` subclass with a stub `_tray_icon` (`MagicMock`) to capture the call.

The plugin signal-emission tests are intentionally on `BaseWidget` rather than per-plugin — every plugin inherits the behaviour, so duplicating tests buys nothing.

## PR scoping

Same PR as the parent feature (#16). The icon overlay is < 80 added lines including tests, and the parent feature is incomplete without it (the user explicitly asked for the indicator after seeing the menu in the smoke run). Follow-up PR would split a unit into two PRs for no benefit.

## Out of scope

- Non-Windows behaviour: the systray on Linux/macOS may render the overlay differently (margins, scaling). The app is Windows-only per `CLAUDE.md`; no cross-platform tuning needed.
- Per-axis health (e.g. brightness vs contrast as separate dots): the aggregate is one indicator. If a future plugin wants to surface multiple sub-states, it aggregates internally with worst-state-wins and the tray sees one row.
- Tooltip showing the state on hover: the existing `setToolTip(APP_INFO.APP_NAME)` is unchanged. If the user wants the tooltip to also surface the worst state ("Swiss Windows Knife — 1 warning"), that's a follow-up.
- Animations / pulses on transitions: a static dot is enough; an animation would draw too much attention.

## Conventional-commits / version impact

This is a `feat:` commit (minor bump): a new user-visible capability building on the same plugin-health-status feature. The `health_changed` signal is internal plumbing for the same feature; ships in the same PR.
