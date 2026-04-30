# Swiss Windows Knife

Personal Windows tray app (PySide6) bundling small plugins. Frozen with cx_Freeze, packaged as an Inno Setup `.exe`. Single maintainer.

## Run / build

Build helpers live in `tools/build.py` (resources / dev / exe / installer). `pyproject.toml` declares the build system and packages — there is no `setup.py`.

- **Dev (no build step):** `./env/Scripts/python.exe -m swiss_windows_knife`
- **Resources:** `python tools/build.py resources` regenerates `swiss_windows_knife/resources.py` from `resources.qrc` via `pyside6-rcc`. `swiss_windows_knife/resources.py` and the legacy `resources_rc.py` are gitignored — do not commit.
- **Frozen exe:** `python tools/build.py exe` (cx_Freeze, declared in the `build` optional dep group).
- **Installer:** `python tools/build.py installer` — calls Inno Setup at `C:\Program Files (x86)\Inno Setup 6\ISCC.exe`. Output under `build/installer/`.

Python floor is 3.12 (uses `typing.override`, `enum.StrEnum`). Runtime deps in `[project.dependencies]`; build dep `cx_Freeze` only in `[project.optional-dependencies].build`.

## Tests / dev hooks

- **Tests:** `pytest tests/` (deps under `[project.optional-dependencies].test`: `pytest`, `pytest-qt`). CI runs them with `QT_QPA_PLATFORM=offscreen` between flake8 and the cx_Freeze build.
- **Pre-commit:** `pip install pre-commit && pre-commit install` once per clone — runs flake8 (matching CI args) on staged files before each commit. Config in `.pre-commit-config.yaml`.

## Architecture

- Entry: `swiss_windows_knife/__main__.py` → `TrayWidget` (`swiss_windows_knife/ui/tray_widget.py`).
- Plugins are `BaseWidget` subclasses listed in `TrayWidget.__init__`. Hooks each plugin can opt into:
  - `display_name` — class attr, label in the Plugins toggle menu.
  - `retrieve_menus()` → top-level menu/action entries on the tray.
  - `retrieve_config_panels()` → list of `ConfigPanel` (in `swiss_windows_knife/base/config_panel.py`); shown as tabs in the unified Configuration dialog (`swiss_windows_knife/ui/configuration_dialog.py`).
  - `set_enabled(bool)` / `status_changed(bool)` for the toggle.
- **DDC/CI rule:** every `monitorcontrol` operation (luminance, contrast, input source) must go through `runner().submit(fn, ...)` from `swiss_windows_knife/base/monitor_runner.py`. Single daemon worker thread serializes calls so the GUI stays responsive and operations don't race each other. Don't call `monitorcontrol.get_monitors()` directly from a Qt slot.
- **Settings:** `UserSettings.instance()` singleton over `QSettings`, backed by Windows registry at `HKEY_CURRENT_USER\Software\Swiss Windows Knife\UserSettings`.
- **Adding a new setting:** add a `ConfigPanel` subclass (defined in `swiss_windows_knife/base/config_panel.py`) next to the plugin, return it from the plugin's `retrieve_config_panels()`. Do not build a new top-level dialog — the unified one auto-tabs panels.

## Conventions

- Commits follow angular conventional commits. `pyproject.toml` configures `python-semantic-release`: `feat:` ⇒ minor, `fix:` / `perf:` ⇒ patch, anything else ⇒ no bump. Allowed tags: `build`, `chore`, `ci`, `docs`, `feat`, `fix`, `perf`, `style`, `refactor`, `test`.
- PRs may be rebase-merged or squash-merged. Either way ensure each commit's tag (or the PR title for squash) carries the intended bump.
- `main` is protected against force-push and deletion; direct pushes are still allowed (semantic-release bumps version on `main`).
- Default to writing no comments and no new docs/READMEs unless asked. Don't narrate code that names already explain.

## Gotchas

- The dev venv is at `./env/`. The base Python on PATH does not have the deps installed.
- When testing runtime changes locally, kill the running tray Python (`Get-Process | Where-Object { $_.Path -eq "...env\Scripts\python.exe" } | Stop-Process -Force`) before relaunching — only one instance should hold the tray icon and the registry singleton.
