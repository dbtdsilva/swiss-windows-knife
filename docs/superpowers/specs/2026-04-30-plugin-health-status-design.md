# Plugin health status design

## Goal

Surface, in the tray menu, whether each plugin is functioning. Today only `HomeAssistantMqttPubPlugin` exposes any status (a disabled `Configured` / `Not configured` action), and even that doesn't reflect whether the MQTT session is actually connected. The other plugins surface no health information at all, so the user has to open `View Logs` to know whether USB monitoring is alive or whether `monitorcontrol` is failing silently.

The user wants a single consolidated view of plugin health, plus an at-a-glance summary at the top of the tray that says whether *anything* needs attention.

## Behavior

The tray's main menu grows two new elements at the top:

1. **A single summary line** showing the worst aggregate state across all enabled plugins:
   - `Health: All OK` (green dot)
   - `Health: N warning(s), M error(s)` (amber dot if no errors, red if any)

   Disabled plugins do not contribute to the aggregate. The summary line is not clickable; it is purely a status indicator.

2. **A `Health` submenu** with one row per plugin (including non-toggleable ones like `Auto-updater`):
   - `● Display brightness — Auto`
   - `● Monitor input switch — Listening`
   - `● Home Assistant — Connected`
   - `● Auto-updater — Up to date`

   Disabled plugins still appear, greyed out, with state `Disabled`.

Clicking a row in the `Health` submenu does nothing — it is informational. Existing plugin tray actions (brightness/contrast control menus, `Check for updates...`, etc.) remain where they are. The `Home Assistant` submenu's existing `Configured / Not configured` action is removed in favor of the unified Health view.

### State semantics per plugin

| Plugin | OK | Warning | Error | Disabled |
|---|---|---|---|---|
| **Display brightness & contrast** | last `monitorcontrol` op succeeded; message reflects current mode (`Auto` / `Manual N`) | last `monitorcontrol` op raised `VCPError` (auto-clears on next successful op) | (no error state in v1) | user toggled off |
| **Monitor input switch on USB events** | `DeviceListener` running; message `Listening` | (no warning state) | listener failed to start (exception raised in `_start_runtime`) | user toggled off |
| **Home Assistant (MQTT)** | session connected (paho `on_connect` fired); message `Connected` | (a) configured but not yet connected / disconnected; (b) not configured at all; messages `Connecting…` / `Disconnected` / `Not configured` | (no error state in v1; broker auth failures show as warning until reconnect succeeds) | user toggled off |
| **Auto-updater** | last check succeeded; message `Up to date` or `Update available vN.N.N` | last check failed (`result is None` from `_on_check_finished`) or watchdog fired; message `Check failed` | (no error state) | n/a (`is_toggleable=False`) |

### Aggregation rule

Worst-state-wins, ignoring `Disabled`:

- any plugin in `Error` → top line is red, `Health: N warning(s), M error(s)`
- else any plugin in `Warning` → top line is amber, `Health: N warning(s), 0 errors`
- else → top line is green, `Health: All OK`

Counts include only plugins in the corresponding state (so warnings count only warnings, errors count only errors). A purely disabled set yields `Health: All OK` because no enabled plugins are in trouble.

## Architecture

### `src/base/health.py` (new)

```python
from dataclasses import dataclass
from enum import StrEnum


class HealthState(StrEnum):
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"
    DISABLED = "disabled"


@dataclass(frozen=True)
class HealthReport:
    state: HealthState
    message: str
```

`HealthReport` is the single value plugins expose. `message` is a short human-readable string (e.g. `"Connected"`, `"Broker unreachable"`, `"Auto"`, `"Manual 60"`); the tray uses it verbatim as the row label after the dot.

### `src/base/base_widget.py` (modified)

`BaseWidget` gains:

- An attribute `self._current_health: HealthReport = HealthReport(HealthState.OK, "")`, initialized in `__init__`.
- A method `health() -> HealthReport`: returns `HealthReport(HealthState.DISABLED, "")` if `self.is_toggleable() and not self.is_enabled()`, otherwise returns `self._current_health`. Contract: **must be cheap and non-blocking; no I/O, no DDC calls, no socket reads.** Subclasses do not override this — they update `_current_health` instead.
- A protected helper `_set_health(state: HealthState, message: str) -> None`: replaces `self._current_health`. Plugins call this from inside whatever event path changed their health.

The disabled-state short-circuit lives in `BaseWidget.health()` rather than in each plugin so plugins do not need to special-case it.

### Plugin update points

Each plugin maintains its own `_current_health` from inside its existing event paths. No new threads, no new timers.

**`DisplayImageTunerPlugin`**
- Initial: `_set_health(OK, mode_message())` where `mode_message()` returns `"Auto"` if `user_settings.get('brightness') is None`, else `f"Manual {value}"`.
- Inside `_apply_brightness` / `_apply_contrast` after a successful `monitor.set_*` call: `_set_health(OK, mode_message())`.
- Inside the `except (ValueError, monitorcontrol.VCPError)` branch: `_set_health(WARNING, f"Monitor error: {e}")`.
- In `change_*_manual` / `change_*_automatic`: re-set health with `mode_message()` while preserving the current state — i.e. if currently OK, stay OK with the new mode message; if currently Warning, keep the Warning message until the next successful apply replaces it.
- In `status_changed(False)`: nothing to do; `BaseWidget.health()` already returns `Disabled`.

**`DeviceDisplayMapperPlugin`**
- Initial: in `__init__` after `_start_runtime()` succeeds, `_set_health(OK, "Listening")`. If the listener constructor raises, catch it, log, and `_set_health(ERROR, str(e))`. Today `_start_runtime` is not wrapped in try/except — it will be, narrowly around the `DeviceListener(self)` construction.
- In `status_changed(True)`: same logic (start succeeded → OK, raised → ERROR).
- In `status_changed(False)`: nothing — covered by `BaseWidget.health()`.

**`HomeAssistantMqttPubPlugin`**
- Initial: `_set_health(WARNING, "Not configured")` if `not self.is_homeassistant_configured`; otherwise `_set_health(WARNING, "Connecting…")` until paho's `on_connect` fires.
- In `_dispatch_on_connected` (already triggered by paho): `_set_health(OK, "Connected")`.
- New: `MqttSession` gains an `on_disconnected: Callable[[], None] | None` hook called from paho's `on_disconnect` callback (paho-mqtt already invokes `_on_disconnect` on the network thread; we already cross over to the GUI thread for the on-connect case via `QMetaObject.invokeMethod`, so we mirror that pattern). The plugin sets it to a method that posts back to the GUI thread and calls `_set_health(WARNING, "Disconnected")`.
- In `reload_session`: re-emit the appropriate initial state after teardown (`Not configured` if config is incomplete; `Connecting…` if it'll start a new session).
- In `closeEvent`: nothing special; the tray will be tearing down too.

**`UpdateChecker`**
- Initial: `_set_health(OK, "Checking…")` since the first check fires on a `QTimer.singleShot(0, …)` from `__init__`.
- In `_on_check_finished` success branch (no update available): `_set_health(OK, "Up to date")`.
- In `_on_check_finished` "update available": `_set_health(OK, f"Update available {remote_version}")` — this is informational, not a problem.
- In `_on_check_finished` `result is None` branch: `_set_health(WARNING, "Check failed")`.
- In `_check_watchdog` after timeout: `_set_health(WARNING, "Check timed out")`.

### `src/ui/tray_widget.py` (modified)

`_populate_main_menu` is restructured:

1. Read each plugin's `health()` once into a local list `[(plugin, report), …]` (4 attribute reads).
2. Compute aggregate counts: `n_warning = sum(1 for _, r in reports if r.state == WARNING)`, similarly errors. Decide overall worst state.
3. Build the summary `QAction` (disabled, no slot) with text `Health: All OK` / `Health: N warning(s), M error(s)` and a coloured-dot icon based on aggregate worst-state.
4. Build the `Health` submenu: one disabled `QAction` per plugin titled `{display_name} — {message}`, prefixed with a coloured dot icon based on `report.state`. Plugins are listed in the same order as `child_components`; disabled plugins are not separated, just greyed out via the icon.
5. Then continue as today: existing per-plugin tray actions, separator, Configuration / View Logs / About / Quit.

For the coloured-dot icons, generate small `QPixmap`s at runtime (16×16 filled circles, one per state) cached as module-level constants so we are not recomputing them per menu open. No new files in `resources.qrc`.

### Removal of the existing HA status submenu

`HomeAssistantMqttPubPlugin.retrieve_menus()` currently returns a `Home Assistant` submenu containing only a disabled `Configured` / `Not configured` row. With the unified Health view that information is redundant; `retrieve_menus()` returns `[]`. Anything actionable HA grows in the future can be added back to its own submenu.

## Data flow

```
plugin async event (paho callback / monitor runner result / QThread finished)
    │
    └──→ plugin._set_health(state, message)
                │
                └──→ self._current_health = HealthReport(...)
                                 │
                                 ▼
user clicks tray  ──→  aboutToShow  ──→  _populate_main_menu
                                                │
                                                └──→ for each plugin: plugin.health()
                                                                            │
                                                                            └──→ return self._current_health
                                                                                  (unless toggled off → DISABLED)
```

Cost on tray-open: 4 attribute reads + worst-state aggregation + 5 `QAction` creations. Sub-millisecond. The non-blocking contract on `health()` is enforced socially (docstring) and structurally (default implementation is a single attribute read).

## Error handling

- `_set_health` is the only mutator and only accepts `HealthState` enum values, so corrupted states are impossible.
- If a plugin forgets to call `_set_health` after a failure, the worst that happens is the tray shows stale info; nothing crashes.
- If `health()` raises (e.g. due to a future plugin overriding it incorrectly), the tray catches per-plugin exceptions in `_populate_main_menu`, logs `logging.exception("plugin health() raised")`, and falls back to `HealthReport(WARNING, "health() failed")` for that row so one broken plugin cannot prevent the rest of the menu from rendering.

## Testing

`pytest-qt` covers all interactive bits.

**`tests/base/test_base_widget_health.py`** (new)
- `health()` returns `Disabled` when `is_toggleable() and not is_enabled()`, regardless of `_current_health`.
- `health()` returns `_current_health` when enabled.
- `health()` returns `_current_health` for non-toggleable widgets even with `is_enabled() == False` (defensive — `is_toggleable=False` widgets should not have `is_enabled` flipped, but the contract is "DISABLED only for toggleable-and-off").
- `_set_health` updates `_current_health` exactly once per call.

**`tests/plugins/home_assistant_mqtt_pub/test_health.py`** (new)
- With no MQTT config, plugin reports `Warning: Not configured`.
- With config but before `_dispatch_on_connected` fires, plugin reports `Warning: Connecting…`.
- After `_dispatch_on_connected`: `OK: Connected`.
- After the new `on_disconnected` hook fires: `Warning: Disconnected`.

**`tests/plugins/display_image_tuner/test_health.py`** (new)
- Initial state is OK with current mode message.
- Forcing `_apply_brightness` to raise `monitorcontrol.VCPError` flips to `Warning`.
- Next successful apply restores `OK`.

**`tests/plugins/device_display_mapper/test_health.py`** (new)
- Successful start → `OK: Listening`.
- `DeviceListener` constructor raising → `Error: <reason>`.

**`tests/components/test_update_checker_health.py`** (new)
- Initial state `OK: Checking…`.
- `_on_check_finished(None)` → `Warning: Check failed`.
- `_on_check_finished(("v9.9.9", "url"))` (newer) → `OK: Update available v9.9.9` (the version-skipping logic in `_confirm_update` is unrelated to health).
- Watchdog firing → `Warning: Check timed out`.

**`tests/ui/test_tray_widget_health.py`** (new)
- Build a `TrayWidget` with three stub plugins reporting `OK` / `WARNING` / `ERROR`. Assert summary text is `Health: 1 warning(s), 1 error(s)` and the summary action has the red dot icon.
- All-OK plugins → summary text is `Health: All OK`, green icon.
- One disabled plugin + two OK plugins → summary text is `Health: All OK` (disabled does not contribute to counts), and the disabled plugin appears in the submenu with the grey dot.
- A plugin whose `health()` raises → tray still renders; that row shows `Warning: health() failed`.

CI runs all of this with `QT_QPA_PLATFORM=offscreen`.

## Out of scope

- Live updates while the tray menu is open. Tray menus close on click anyway, and pull-on-`aboutToShow` is sufficient.
- Tray icon colour reflecting aggregate health. Could be added later if the user wants ambient awareness without opening the menu.
- Multi-component health per plugin (e.g. HA reporting connection + each entity sampler separately). Plugins that internally have multiple sub-components aggregate worst-state-wins inside themselves; the tray sees one row per plugin.
- Click actions on Health rows (e.g. "click HA error → open MQTT config panel"). Informational only in v1.

## Conventional-commits / version impact

This is a `feat:` commit (minor bump): a new user-visible capability. The MQTT `on_disconnected` hook addition is internal plumbing for the same feature — it ships in the same commit (or a same-PR predecessor commit, also tagged `feat:` since it lands a new public hook on `MqttSession`). Removing the existing `Configured / Not configured` HA submenu row is part of the same `feat:` (the unified Health view replaces it).
