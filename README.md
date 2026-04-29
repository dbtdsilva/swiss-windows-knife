<div align="center">

<img src="icons/coat-of-arms.png" alt="Swiss Windows Knife" width="96" />

# Swiss Windows Knife

**A personal Windows tray-app toolkit:** adaptive monitor brightness/contrast, USB-aware display input switching, Home Assistant MQTT bridge, and more.

[**Releases**](https://github.com/dbtdsilva/swiss-windows-knife/releases/latest) &nbsp;·&nbsp; [**Changelog**](CHANGELOG.md) &nbsp;·&nbsp; [**Conventions**](CLAUDE.md)

[![Build and test](https://github.com/dbtdsilva/swiss-windows-knife/actions/workflows/build-n-test.yml/badge.svg)](https://github.com/dbtdsilva/swiss-windows-knife/actions/workflows/build-n-test.yml)
[![Latest release](https://img.shields.io/github/v/release/dbtdsilva/swiss-windows-knife?label=release&sort=semver&color=blue)](https://github.com/dbtdsilva/swiss-windows-knife/releases/latest)
[![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

</div>

---

- 🌅 &nbsp;**Adaptive brightness & contrast** anchored to real sunrise/sunset, with a live preview graph
- 🗺️ &nbsp;**OpenStreetMap** location picker — coordinates and IANA timezone resolved from a single map click
- 🔌 &nbsp;**USB-aware display switching** — flips monitor inputs over DDC/CI when a KVM device hops machines
- 🏠 &nbsp;**Home Assistant MQTT** publisher exposing host metrics + lock / sleep / shutdown commands
- ⬆️ &nbsp;**Built-in auto-updater** that picks up new releases from GitHub and re-installs silently
- 🪟 &nbsp;**Native Windows tray** with a unified tabbed configuration dialog and remembered window sizes

## Table of contents

- [Installation](#installation)
- [Features](#features)
- [Build from source](#build-from-source)
- [Project layout](#project-layout)
- [Releases](#releases)
- [License](#license)

## Installation

Grab the latest installer from the [releases page](https://github.com/dbtdsilva/swiss-windows-knife/releases/latest) and run it — it's a per-user Inno Setup `.exe` and does not need administrator rights. Once installed, the application keeps itself up-to-date through the built-in auto-updater.

## Features

Each capability ships as an isolated plugin loaded by the tray on start-up. Toggle plugins on or off from **Plugins** in the tray menu, and tune them from a unified, tabbed **Configuration…** dialog.

<details>
<summary><strong>🌅 Adaptive monitor brightness &amp; contrast</strong></summary>

A keyframe-based schedule anchored to your local sunrise and sunset — define a *night level*, *day level*, *sunrise / sunset offsets*, *ramp duration*, and *ramp smoothness* (ease-in / linear / ease-out) per axis. The plugin drives every detected monitor over **DDC/CI** and renders a live preview graph in the configuration panel, with a year-of-day scrubber so you can see how the curve shifts seasonally before committing.

Each axis (brightness, contrast) can be independently set to **Auto** or pinned to a fixed value from the tray menu. Auto-mode reflects in the preview graph as a flat line, fixed-mode as the eased schedule.
</details>

<details>
<summary><strong>🗺️ OpenStreetMap location picker</strong></summary>

Coordinates and timezone are picked from an embedded **Leaflet** map (rendered through `QtWebEngine`); the IANA timezone is auto-resolved from the chosen point with [`timezonefinder`](https://github.com/jannikmi/timezonefinder). No manual lat/lng or timezone entry — drop a pin, click OK, done.
</details>

<details>
<summary><strong>🔌 USB-aware display input switching</strong></summary>

Listens for a configured USB device — typically a keyboard, mouse, or other peripheral shared by a KVM — and, when it connects or disconnects, swaps every monitor's input source over DDC/CI to the matching pair you configured per display. Handy for one-keyboard-many-machines setups.
</details>

<details>
<summary><strong>🏠 Home Assistant MQTT publisher</strong></summary>

Publishes host metrics as MQTT discovery entities so they appear in Home Assistant without manual YAML:

- CPU usage / temperature / frequency
- Memory usage
- Per-drive disk free
- Network rx / tx
- Uptime, monitor count, current user, foreground window, lock state, battery state

A small set of command entities (lock, sleep, shutdown) lets Home Assistant trigger the host. Per-entity publish toggles and per-entity intervals are configurable.
</details>

<details>
<summary><strong>⬆️ Auto-updater</strong></summary>

Checks the GitHub releases endpoint every 30 minutes and on demand. When a newer version is found it prompts the user, downloads the Inno Setup installer to a temp folder, and runs it silently with a post-install relaunch.
</details>

<details>
<summary><strong>🪟 Tray utilities</strong></summary>

Live log viewer with adjustable verbosity, About dialog with version + license + project URL, and a unified configuration dialog that auto-tabs each plugin's panel and remembers its window size between sessions.
</details>

## Build from source

The project pins **Python 3.12** and uses a virtual environment at `./env/`. From a fresh clone:

```sh
# install runtime, build, and test dependencies
./env/Scripts/python.exe -m pip install -e .[build,test]

# run the tray straight from source (no freeze)
./env/Scripts/python.exe -m src.swiss_windows_knife

# regenerate Qt resources after editing resources.qrc
python setup.py resources

# freeze the executable with cx_Freeze
python setup.py exe

# package the Inno Setup installer (Windows only)
python setup.py installer
```

Wire the same lint hook CI uses:

```sh
pip install pre-commit
pre-commit install   # runs ruff on staged files before each commit
```

## Project layout

| Path | Responsibility |
| --- | --- |
| `src/swiss_windows_knife.py` | Entry point — constructs `QApplication` and `TrayWidget`. |
| `src/ui/` | Tray widget, configuration dialog, log viewer, About dialog. |
| `src/base/` | Reusable infrastructure: `BaseWidget`, `ConfigPanel`, `UserSettings`, `PersistentSizeDialog`, the DDC/CI `monitor_runner`. |
| `src/plugins/display_image_tuner/` | Adaptive brightness/contrast plugin and OSM location picker. |
| `src/plugins/device_display_mapper/` | USB-aware display input switcher. |
| `src/plugins/home_assistant_mqtt_pub/` | Home Assistant MQTT publisher and command entities. |
| `src/components/update_checker.py` | Auto-updater. |
| `tests/` | `pytest` + `pytest-qt`, run headless with `QT_QPA_PLATFORM=offscreen`. |

Deeper conventions (commit tags, monitor-runner usage rules, settings storage) live in [`CLAUDE.md`](CLAUDE.md).

## Releases

Releases follow [semantic versioning](https://semver.org/) and are cut automatically by [`python-semantic-release`](https://github.com/python-semantic-release/python-semantic-release) from [conventional commit](https://www.conventionalcommits.org/) messages on `main`. Each release publishes the Inno Setup installer as an asset and the changelog body is generated from the commit history.

## License

Released under the [MIT License](LICENSE).
