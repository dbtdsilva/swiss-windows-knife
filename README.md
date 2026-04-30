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

## Installation

Grab the latest installer from the [releases page](https://github.com/dbtdsilva/swiss-windows-knife/releases/latest) and run it — it's a per-user Inno Setup `.exe` and does not need administrator rights. Once installed, the application keeps itself up-to-date through the built-in auto-updater.

## Build from source

The project pins **Python 3.12** and uses a virtual environment at `./env/`. From a fresh clone:

```sh
# install runtime, build, and test dependencies
./env/Scripts/python.exe -m pip install -e .[build,test]

# run the tray straight from source (no freeze)
./env/Scripts/python.exe -m swiss_windows_knife

# regenerate Qt resources after editing resources.qrc
python tools/build.py resources

# freeze the executable with cx_Freeze
python tools/build.py exe

# package the Inno Setup installer (Windows only)
python tools/build.py installer
```

Wire the same lint hook CI uses:

```sh
pip install pre-commit
pre-commit install   # runs ruff on staged files before each commit
```

## Releases

Releases follow [semantic versioning](https://semver.org/) and are cut automatically by [`python-semantic-release`](https://github.com/python-semantic-release/python-semantic-release) from [conventional commit](https://www.conventionalcommits.org/) messages on `main`. Each release publishes the Inno Setup installer as an asset and the changelog body is generated from the commit history.

## License

Released under the [MIT License](LICENSE).
