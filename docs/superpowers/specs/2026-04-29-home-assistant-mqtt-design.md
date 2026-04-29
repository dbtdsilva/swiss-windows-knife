# Home Assistant MQTT Plugin — Design

**Date:** 2026-04-29
**Status:** Approved (brainstorming complete; ready for implementation plan)
**Owner:** Diogo Silva
**Replaces:** the WIP code in `src/plugins/home_assistant_mqtt_pub/` flagged in `CLAUDE.md`.

## Goal

Replace the WIP Home Assistant MQTT plugin with a working publish-side integration that exposes a curated set of Windows-host signals to Home Assistant via MQTT discovery, plus a small command surface (lock, sleep, shutdown) callable from HA.

The user wants to see things like host power state, locked/unlocked state, CPU temperature/frequency, and other host metrics on a HA dashboard, and to issue basic commands back. The user also wants the integration to never leave orphaned entities ("hanging devices") in HA after configuration changes.

## Non-goals (v1)

- Exposing the existing plugins (display image tuner, device-display mapper) as HA controls.
- Per-disk write-rate, GPU temperature, multi-broker support, TLS.
- Auto-detecting hostname changes; the device name is user-set.
- Sub-second freshness for any signal.

## Entity set

| Key | Type | Default enabled | Default interval |
|---|---|---|---|
| `lock_state` | binary_sensor | yes | event-driven |
| `cpu_temperature` | sensor (°C) | yes | 30 s |
| `cpu_frequency` | sensor (MHz) | yes | 30 s |
| `cpu_usage` | sensor (%) | yes | 30 s |
| `memory_usage` | sensor (%) | yes | 30 s |
| `uptime` | sensor (s since boot) | yes | 60 s |
| `battery_state` | binary_sensor (on AC?) | yes (unavailable on desktops) | 60 s |
| `disk_free_<drive>` | sensor (GB), one per fixed drive | yes | 300 s |
| `network_tx_bytes` | sensor (bytes) | yes | 30 s |
| `network_rx_bytes` | sensor (bytes) | yes | 30 s |
| `monitor_count` | sensor (count) | yes | 60 s |
| `current_user` | sensor (string) | **no** (privacy) | 300 s |
| `foreground_window` | sensor (string) | **no** (privacy) | 30 s |

Per-entity intervals are configurable in the config panel. `lock_state` has no configurable interval — it is event-driven via Windows session-change notifications.

## Command set

| Key | Display | Mechanism |
|---|---|---|
| `lock` | Lock screen | `user32.LockWorkStation` |
| `sleep` | Sleep | `PowrProf.SetSuspendState(0, 0, 0)` |
| `shutdown` | Shutdown | adjust `SeShutdownPrivilege` then `ExitWindowsEx(EWX_SHUTDOWN \| EWX_FORCEIFHUNG, 0)` |

Each is published to HA as a `button` discovery entity with no state, only a `command_topic`. If `SeShutdownPrivilege` cannot be acquired at plugin start, the `shutdown` command is omitted from discovery and shown as unavailable in the panel.

## Topic structure

`device_id = slugify(homeassistant_device_name)` ; the `swk_` prefix namespaces this app to avoid colliding with anything else publishing to the same broker.

| Purpose | Topic | Retained |
|---|---|---|
| Discovery (sensors/binary_sensors/buttons) | `homeassistant/<component>/swk_<device_id>/<entity_key>/config` | yes |
| State | `homeassistant/<component>/swk_<device_id>/<entity_key>/state` | yes |
| Availability (LWT) | `homeassistant/swk_<device_id>/availability` | yes |
| Command (incoming) | `homeassistant/button/swk_<device_id>/<command_key>/set` | n/a |

State topics are published `retain=True` so HA recovers values across HA restarts without waiting for the next interval. Every entity's discovery payload includes `availability_topic = homeassistant/swk_<device_id>/availability` so HA marks the entity unavailable as soon as the LWT fires.

## Settings keys

Existing broker keys are unchanged: `homeassistant_host`, `homeassistant_port`, `homeassistant_username`, `homeassistant_password`, `homeassistant_client_id`.

Added:

- `homeassistant_device_name` (str) — user-set, drives the device id.
- `homeassistant_previous_device_name` (str, transient) — used by reconciliation to clean up the old device's discovery topics on rename. Cleared after a successful reconcile.
- `homeassistant_publish_<entity_key>` (bool) — per entity.
- `homeassistant_interval_<entity_key>` (int seconds) — per entity; absent for event-driven.
- `homeassistant_command_enabled_<command_key>` (bool) — per command.

`port` is coerced to `int` before `client.connect`; the panel validates and rejects non-numeric input.

## Architecture

```
src/plugins/home_assistant_mqtt_pub/
├── home_assistant_mqtt_pub_plugin.py   # BaseWidget; lifecycle; wires components together
├── mqtt_session.py                     # paho client wrapper (connect, LWT, dispatch, publish)
├── device_context.py                   # device_id slug, topic builders, HA "device" JSON block
├── publisher.py                        # per-entity QTimers + reconciliation + publish
├── sampler_runner.py                   # daemon worker thread (mirrors src/base/monitor_runner.py)
├── entity_settings.py                  # per-entity enable/interval persistence + previous-state tracking
├── entities/
│   ├── __init__.py                     # ENTITIES list (static + dynamic disk_free)
│   ├── base.py                         # Entity protocol + SampleResult dataclass
│   ├── lock_state.py                   # event-driven via WTSRegisterSessionNotification
│   ├── cpu_temperature.py              # wmi MSAcpi_ThermalZoneTemperature; SampleResult.is_available=False on failure
│   ├── cpu_frequency.py                # wmi Win32_Processor.CurrentClockSpeed
│   ├── cpu_usage.py
│   ├── memory_usage.py
│   ├── uptime.py
│   ├── battery_state.py
│   ├── disk_free.py                    # multi-instance; psutil.disk_partitions() at startup
│   ├── network_io.py                   # tx/rx bytes (two entity instances from one module)
│   ├── monitor_count.py                # uses src.base.monitor_runner — never raw paho thread
│   ├── current_user.py
│   └── foreground_window.py
├── commands/
│   ├── __init__.py                     # COMMANDS list
│   ├── base.py                         # Command protocol
│   ├── lock.py
│   ├── sleep.py
│   └── shutdown.py
└── mqtt_config_panel.py                # extended UI (broker / device / entities / commands)
```

### Component responsibilities

**`MqttSession`** wraps `paho.mqtt.Client(MQTTv5, CallbackAPIVersion.VERSION2)`. Owns: connect/disconnect, LWT, `loop_start`, `on_connect`/`on_message`/`on_disconnect`, topic-prefix dispatch to registered handlers, thread-safe `publish(topic, payload, retain)`. Uses `connect_async` + `reconnect_delay_set(min_delay=1, max_delay=30)`.

**`Publisher`** holds the entity instances; manages per-entity QTimers; runs reconciliation. On each timer tick, submits sampling to `SamplerRunner`. The sampler's completion callback publishes via `MqttSession`. For event-driven entities, calls `entity.subscribe(on_change)` once at startup; the entity is responsible for emitting via the callback.

**`SamplerRunner`** is a daemon thread with a queue, mirroring `src/base/monitor_runner.py`. `submit(fn, on_done)` runs `fn` off the Qt thread and calls `on_done(result)` from the worker thread. Justification: WMI calls block ~100–500 ms; multiple per-entity timers may overlap; the GUI thread must stay responsive.

**`CommandDispatcher`** (lives inside `commands/__init__.py`): registers each command's `set` topic with `MqttSession`; `on_message` for that topic invokes the handler. Handlers are wrapped to catch exceptions (logged, do not kill the loop).

**`DeviceContext`** centralizes the slug, topic builders, and the HA `device` JSON block (identifiers, manufacturer, model, name, sw_version) that every discovery payload embeds.

**`EntitySettings`** is a small helper around `UserSettings` for per-entity reads/writes (defaults applied here, not in the entities themselves) and for tracking the previous-published set used in reconciliation.

## Data flow

### Startup

1. Plugin `__init__` loads broker config from `UserSettings`. If incomplete, `is_homeassistant_configured = False` and no MQTT connection is attempted.
2. If configured: build `MqttSession` with LWT (`<availability_topic>` → `offline`).
3. `MqttSession.start()` calls `connect_async` + `loop_start`. On `on_connect`:
   - Subscribe to `homeassistant/status` and to each enabled command's `set` topic.
   - Call `Publisher.on_connected()`:
     1. Reconcile discovery (see *Reconciliation*).
     2. Publish `availability=online`.
     3. Publish a fresh state for every enabled entity.
     4. Start per-entity QTimers; subscribe to event-driven entities.

### Per-tick

QTimer fires (Qt thread) → `sampler_runner.submit(entity.sample, on_done)` → worker thread runs `sample()` → on success the worker calls `client.publish(state_topic, value, retain=True)`.

### Lock event

A hidden message-only `QWidget` registered with `WTSRegisterSessionNotification(NOTIFY_FOR_THIS_SESSION)` receives `WM_WTSSESSION_CHANGE`. `wparam == WTS_SESSION_LOCK` → publish `ON`; `WTS_SESSION_UNLOCK` → publish `OFF`. Initial state at startup is queried via `WTSQuerySessionInformation` to publish a correct first value.

### HA command incoming

`MqttSession.on_message` routes by topic prefix → `CommandDispatcher.run(command_key)` → handler runs synchronously (commands are quick OS calls). Exceptions caught + logged.

### HA reboot recovery

When `homeassistant/status = online` arrives, `Publisher` re-publishes discovery and a fresh state snapshot. Covers HA upgrades that wipe retained payloads.

### Apply settings

1. Diff `previous_device_name` vs current. If changed: publish empty payloads to *all* old-device discovery topics. Update `previous_device_name = current` on success.
2. Diff per-entity `publish_*` flags. Newly disabled → empty payload to discovery topic. Newly enabled → full discovery payload.
3. Diff per-command `command_enabled_*` flags. Same logic.
4. Restart Publisher's per-entity timers with the new intervals.

### Plugin disabled (`set_enabled(False)`)

Publish empty payloads to all discovery topics (full deletion in HA). Publish `availability=offline`. Stop timers, unregister event subscriptions, `loop_stop` + `disconnect`.

Re-enable runs the startup path.

### App quit (`closeEvent`)

Publish `availability=offline`. `loop_stop` + `disconnect`. Discovery topics intact; HA shows entities as unavailable. LWT serves as broker-side backstop.

### Forget device button

Confirmation prompt. On confirm: publish empty payloads to all discovery topics under the current device id; clear all per-entity `publish_*` flags; leave the plugin enabled and the broker config intact so the user can re-enable individual entities later.

## Reconciliation

The single source of truth for "what is currently published to HA" is the union of:

- Per-entity `publish_<key>` flags (enabled set).
- The `previous_device_name` setting (the device id whose topics were last touched).

On every reconciliation pass (`Publisher._reconcile`):

```
desired = { (component, entity_key) : enabled-and-publishable } under current device_id
previous = read from settings (per-entity) under previous_device_name
to_delete = previous - desired   →  publish empty payload to discovery topic
to_create = desired - previous   →  publish full discovery payload
to_keep = desired ∩ previous     →  no-op
```

Plus, if `previous_device_name != current_device_name`, *all* of `previous` is added to `to_delete` first. On first run, `previous_device_name` is unset and `previous = {}`; reconciliation then reduces to publishing discovery for every enabled entity/command, which is the desired behavior.

The reconciliation logic is pure given (previous_state, desired_state) and is the most-tested component in the design.

## Error handling

| Failure | Behavior |
|---|---|
| Broker unreachable on startup | paho retries via `connect_async` + `reconnect_delay_set`; entities continue sampling; panel still works; warnings logged, no modal popups |
| Sample raises | caught in `SamplerRunner`; `SampleResult.is_available = False`; nothing published (LWT/availability covers it); DEBUG log |
| Invalid broker fields on apply | panel `apply()` validates, `QMessageBox.warning`, returns False (dialog stays open) |
| Empty / non-slug device name | same |
| Command handler raises | caught + logged; loop continues |
| `SeShutdownPrivilege` unavailable | `shutdown` command omitted from discovery + shown unavailable in panel |
| Plugin disabled mid-session | full discovery deletion + offline availability |

The previously-known WIP bugs are subsumed by this redesign:

- `is_homeassistant_online` initialization → state machine in `MqttSession`.
- `status_changed(bool)` signature → `BaseWidget.status_changed(status: bool)` correctly overridden.
- Port coerced to `int` at apply time.
- `loop_stop()` then `disconnect()` order; `on_disconnect` registered for logging.
- Hardcoded `camelotaorus` and UUID → `DeviceContext` from `homeassistant_device_name`.

## Config panel

One `ConfigPanel` (no tabs), four `QGroupBox` sections:

```
Broker:    Login / Password / Host / Port / Client ID
Device:    Name [_____]   [Forget device in Home Assistant]
Entities:  table — Name | Value | Unit | Publish | Interval (s)
                  rows show "Loading…" then sampled values; unavailable rows force Publish off and disable the row
           [Refresh values]
Commands:  per-command checkbox; rows for unavailable commands are disabled with a reason label
```

Sampling at panel open: each row submits a sample to `SamplerRunner`; results land asynchronously. Because the worker thread cannot touch widgets directly, the panel exposes a Qt signal `sample_arrived(entity_key, result)` that the worker emits via `QMetaObject.invokeMethod(..., Qt.QueuedConnection)`; the slot updates the row on the Qt thread. Refresh re-submits.

`apply()` validates broker fields + device name; persists per-entity enable+interval and per-command enable; triggers `Publisher.reconcile()`. Returns False (and shows a `QMessageBox.warning`) on validation failure.

## Threading

- Qt main thread: UI, QTimer ticks, `on_message` (paho's network thread *delivers* on its loop thread; we keep handlers fast and let publishes happen from any thread).
- paho network thread: managed by `loop_start`; we don't touch it directly.
- `SamplerRunner` thread: blocking system calls (`wmi`, `psutil`, `win32api`).
- `monitor_runner` thread (existing): `monitor_count` entity routes through this for any `monitorcontrol` access, per `CLAUDE.md` rule.

`paho.mqtt.Client.publish` is thread-safe, so any thread can call it. State topic publishes happen from the `SamplerRunner` thread; discovery + lifecycle publishes from the Qt thread.

## Testing

| Layer | Coverage |
|---|---|
| Per-entity (one `tests/test_entity_<key>.py` each) | `sample()` available + unavailable paths, mocked `wmi` / `psutil` / `win32api` / `ctypes` |
| `MqttSession` | spy paho `Client`; assert connect/LWT/subscribe args, dispatch, thread-safe publish |
| Discovery payloads | per entity + per command, `assert payload == expected_dict` snapshot |
| `Publisher._reconcile` | feed (previous, desired) tuples; assert exact `(topic, payload)` publishes |
| Config panel | extends `tests/test_mqtt_config_panel.py`: instantiate, simulate apply with valid + invalid input, assert settings + warning paths |
| Commands | route fake message; assert handler called; OS calls patched so CI does not lock/sleep/shutdown |

CI does not require a real MQTT broker; all paho usage is behind `MqttSession` and tests substitute a fake client.

## Dependencies

Add `psutil==5.9.8` to `[project.dependencies]` in `pyproject.toml` (matching the project's exact-pin style). Required for: cpu_usage, memory_usage, uptime, battery_state, disk_free, network_io.

Already present and reused: `wmi`, `pywin32`, `paho.mqtt`, `pyside6`.

## Migration / cleanup

The existing WIP files (`home_assistant_mqtt_pub_plugin.py`, `mqtt_config.py`, `mqtt_config_panel.py`) are largely rewritten. `MqttConfig`'s shape is preserved (the existing tests in `tests/test_mqtt_config.py` and `tests/test_mqtt_config_panel.py` continue to pass against unchanged broker-config behavior).

The hardcoded `camelotaorus` device id and `120f167c-...` UUID are removed. Any existing retained discovery topics on the user's broker under those names will become orphans on the *broker side*; they are not the new plugin's responsibility to clean up automatically (the user can remove them once via an MQTT client). This is a one-time migration cost.

## Out of scope

- Exposing existing plugins (brightness, monitor input) as HA entities.
- Per-disk write rate; GPU temperature; per-process metrics.
- Multi-broker; TLS.
- Auto-detecting hostname changes.
- A "Test connection" button in the broker config (could be added later).
