# Swiss Windows Knife

A personal tray-app toolkit for taming Windows monitors, displays, and home-automation bridges. Single maintainer, single user — me — but the code is here in case you want to fork it.

## What it does

Each feature is a plugin loaded by the tray. Toggle them on/off from the tray's **Plugins** menu; tune them from a unified **Configuration** dialog (tabbed).

- **Display brightness & contrast (auto)** — pick a sun-anchored keyframe schedule (night level, day level, sunrise/sunset offsets, ramp duration, ramp smoothness) and the app drives every detected monitor over DDC/CI through the day. Live preview graph in the configuration panel, with a year-of-day scrubber to see how the curve shifts seasonally.
- **Sun strength location** — coordinates and timezone are picked from an embedded OpenStreetMap (Leaflet via `QtWebEngine`); IANA timezone is auto-resolved from the chosen point with `timezonefinder`. No manual lat/lng/timezone fields.
- **Display input switcher (USB-aware)** — when a configured USB device (e.g. a KVM-shared keyboard or mouse) connects or disconnects, swaps every monitor's input source over DDC/CI to the matching pair you configured per-display.
- **Home Assistant MQTT publisher** — exposes host metrics (CPU usage / temperature / frequency, memory, disk free per drive, network rx/tx, uptime, monitor count, current user, foreground window, lock state, battery) as MQTT discovery entities, plus a few command entities (lock, sleep, shutdown). Per-entity publish toggles and intervals are configurable.
- **Auto-updater** — checks the GitHub releases page on a 30-minute interval and on a manual click; prompts before downloading and silently runs the Inno Setup installer when accepted.
- **Tray utilities** — log viewer, About dialog, Configuration dialog with tab persistence and remembered window sizes.

## Install (just use the app)

Grab the latest installer from [Releases](https://github.com/dbtdsilva/swiss-windows-knife/releases/latest) — it's a per-user Inno Setup `.exe`, no admin rights needed. The app then auto-updates itself when newer releases land.

## Build from source

```sh
# clone, set up a venv at ./env/, then:
./env/Scripts/python.exe -m pip install -e .[build,test]

# run from source (no freeze)
./env/Scripts/python.exe -m src.swiss_windows_knife

# regenerate Qt resources after editing resources.qrc
python setup.py resources

# freeze with cx_Freeze
python setup.py exe

# package the Inno Setup installer (Windows only)
python setup.py installer
```

`pre-commit install` once per clone wires the [ruff](https://github.com/astral-sh/ruff) lint hook the same way CI runs it.

## Project layout

| Path | What's there |
| --- | --- |
| `src/swiss_windows_knife.py` | Entry point — constructs `QApplication` and `TrayWidget`. |
| `src/ui/` | Tray widget, configuration dialog, log viewer, About dialog. |
| `src/base/` | Reusable infrastructure: `BaseWidget`, `ConfigPanel`, `UserSettings`, `PersistentSizeDialog`, the DDC/CI `monitor_runner`. |
| `src/plugins/` | One package per plugin (display tuner, device-display mapper, Home Assistant MQTT). |
| `src/components/update_checker.py` | The auto-updater. |
| `tests/` | `pytest` + `pytest-qt`, headless via `QT_QPA_PLATFORM=offscreen`. |

More project conventions (commit tags, monitor runner rules, settings storage) live in [`CLAUDE.md`](CLAUDE.md).

## License

[MIT](https://github.com/dbtdsilva/swiss-windows-knife/blob/main/LICENSE).
