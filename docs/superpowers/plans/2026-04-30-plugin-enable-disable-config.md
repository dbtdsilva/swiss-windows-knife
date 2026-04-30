# Plugin Enable/Disable in Configuration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move plugin enable/disable from the tray "Plugins" submenu to a "Plugins" tab in Configuration, persist the state across launches, and make disable actually stop the plugin's runtime work. Hide a disabled plugin's tray actions and config-tab.

**Architecture:** `BaseWidget` gains a `UserSettings`-backed `_is_enabled` keyed by class name; subclasses must skip startup if `not self.is_enabled()` and override `status_changed` to start/stop their work idempotently. A new `PluginsConfigPanel` lists toggleable plugins with checkboxes and applies the toggles last (so per-plugin panels can save settings before plugins restart with fresh config). `ConfigurationDialog` is restructured to take a list of plugins instead of a flat list of panels — it builds the Plugins tab itself and inserts/removes per-plugin tabs live as the user toggles checkboxes inside the dialog. `TrayWidget` rebuilds its main menu lazily via `aboutToShow` and skips the disabled plugins' menu contributions; the old "Plugins" submenu is removed.

**Tech Stack:** PySide6 (`QCheckBox`, `QTabWidget`, `Signal`, `QMenu.aboutToShow`, `QTimer`), existing `BaseWidget` / `ConfigPanel` infrastructure, `UserSettings` (QSettings → Windows registry), pytest + pytest-qt.

---

### Task 1: BaseWidget persists enabled state via UserSettings

Adds a `_is_enabled` flag backed by `UserSettings`, keyed by `f"plugin_enabled_{ClassName}"`. Subclasses constructed for the first time use the `is_enabled` constructor default; subsequent runs read whatever was persisted. `set_enabled` writes through.

**Files:**
- Modify: `src/base/base_widget.py`
- Test: `tests/test_base_widget.py`

- [ ] **Step 1: Read the existing base widget tests to understand the convention**

Run: `Get-Content tests/test_base_widget.py -TotalCount 60`
Expected: shows the test file's existing fixtures and patterns.

- [ ] **Step 2: Add failing tests for persistence**

Append to `tests/test_base_widget.py`:

```python
def test_enabled_state_persists_via_user_settings(qtbot, fake_user_settings):
    from src.base.base_widget import BaseWidget

    class _Persisted(BaseWidget):
        pass

    parent = None
    w1 = _Persisted(parent)
    qtbot.addWidget(w1)
    assert w1.is_enabled() is True  # default

    w1.set_enabled(False)
    assert w1.is_enabled() is False
    assert fake_user_settings.get('plugin_enabled__Persisted') is False

    # New instance picks up the persisted value.
    w2 = _Persisted(parent)
    qtbot.addWidget(w2)
    assert w2.is_enabled() is False


def test_enabled_state_normalises_string_values(qtbot, fake_user_settings):
    """QSettings on Windows returns booleans as the strings 'true' / 'false'."""
    from src.base.base_widget import BaseWidget

    class _StrBool(BaseWidget):
        pass

    fake_user_settings.set('plugin_enabled__StrBool', 'false')
    w = _StrBool(None)
    qtbot.addWidget(w)
    assert w.is_enabled() is False


def test_set_enabled_no_change_does_not_invoke_status_changed(qtbot, fake_user_settings):
    from src.base.base_widget import BaseWidget

    class _Spy(BaseWidget):
        def __init__(self, parent):
            super().__init__(parent)
            self.calls: list[bool] = []

        def status_changed(self, status: bool) -> None:
            self.calls.append(status)

    w = _Spy(None)
    qtbot.addWidget(w)
    w.set_enabled(True)  # already True
    assert w.calls == []

    w.set_enabled(False)
    assert w.calls == [False]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `./env/Scripts/python.exe -m pytest tests/test_base_widget.py -q`
Expected: FAIL — the persistence assertion fails because `BaseWidget` doesn't read/write `UserSettings`.

- [ ] **Step 4: Implement persistence in BaseWidget**

Replace the contents of `src/base/base_widget.py` with:

```python
import logging

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QWidget

from .config_panel import ConfigPanel
from .user_settings import UserSettings


def _settings_key(cls: type) -> str:
    return f"plugin_enabled_{cls.__name__}"


def _coerce_bool(value: object, default: bool) -> bool:
    """QSettings on Windows returns booleans as the literal strings 'true'
    or 'false'. Accept either form, falling back to `default` for unknown."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("true", "1", "yes"):
            return True
        if lowered in ("false", "0", "no"):
            return False
    if value is None:
        return default
    return bool(value)


class BaseWidget(QWidget):

    display_name: str = ""

    def __init__(self, parent: QWidget, is_toggleable: bool = True, is_enabled: bool = True) -> None:
        super().__init__(parent)
        self._is_toggleable = is_toggleable

        settings = UserSettings.instance()
        key = _settings_key(self.__class__)
        if settings.has_key(key):
            self._is_enabled = _coerce_bool(settings.get(key), is_enabled)
        else:
            self._is_enabled = is_enabled

    def get_display_name(self) -> str:
        return self.display_name or self.__class__.__name__

    def set_enabled(self, enabled: bool) -> None:
        if self._is_enabled == enabled:
            return
        self._is_enabled = enabled
        UserSettings.instance().set(_settings_key(self.__class__), enabled)
        logging.info(f'Plugin {self.__class__.__name__} is enabled: {enabled}')
        self.status_changed(enabled)

    def is_enabled(self) -> bool:
        return self._is_enabled

    def is_toggleable(self) -> bool:
        return self._is_toggleable

    def retrieve_menus(self) -> list[QMenu | QAction]:
        return []

    def retrieve_config_panels(self) -> list[ConfigPanel]:
        return []

    def status_changed(self, status: bool) -> None:
        return None
```

- [ ] **Step 5: Run all tests**

Run: `./env/Scripts/python.exe -m pytest tests/ -q`
Expected: all pass (the new ones plus 167 existing).

- [ ] **Step 6: Commit**

```bash
git add src/base/base_widget.py tests/test_base_widget.py
git commit -m "feat: persist plugin enabled state via UserSettings"
```

---

### Task 2: DisplayImageTunerPlugin honors disabled state

The plugin's tick timer keeps tracking sunlight even when "disabled". Override `status_changed` to stop/start the timer, and skip starting it in `__init__` when persisted state says disabled.

**Files:**
- Modify: `src/plugins/display_image_tuner/image_tuner_plugin.py`
- Test: `tests/test_display_image_tuner_plugin.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_display_image_tuner_plugin.py`:

```python
import pytest


@pytest.fixture
def plugin(qtbot, fake_user_settings):
    """Construct the plugin in isolation, with no UserSettings preconditions."""
    from src.plugins.display_image_tuner.image_tuner_plugin import DisplayImageTunerPlugin
    p = DisplayImageTunerPlugin(None)
    qtbot.addWidget(p)
    return p


def test_tick_timer_runs_when_enabled(plugin):
    assert plugin._tick_timer.isActive()


def test_status_changed_false_stops_tick_timer(plugin):
    plugin.status_changed(False)
    assert not plugin._tick_timer.isActive()


def test_status_changed_true_starts_tick_timer(plugin):
    plugin.status_changed(False)
    plugin.status_changed(True)
    assert plugin._tick_timer.isActive()


def test_construction_skips_timer_when_persisted_disabled(qtbot, fake_user_settings):
    fake_user_settings.set('plugin_enabled_DisplayImageTunerPlugin', False)
    from src.plugins.display_image_tuner.image_tuner_plugin import DisplayImageTunerPlugin
    p = DisplayImageTunerPlugin(None)
    qtbot.addWidget(p)
    assert not p._tick_timer.isActive()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `./env/Scripts/python.exe -m pytest tests/test_display_image_tuner_plugin.py -q`
Expected: FAIL — `status_changed(False)` is a no-op so the timer keeps running; the persisted-disabled case fails because `__init__` always starts the timer.

- [ ] **Step 3: Modify the plugin to honor enabled state**

In `src/plugins/display_image_tuner/image_tuner_plugin.py`, replace the lines that currently do:

```python
        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._tick)
        self._tick_timer.start(TICK_MS)
```

with:

```python
        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._tick)
        if self.is_enabled():
            self._tick_timer.start(TICK_MS)
```

Then add (just below `closeEvent` so it lives near the timer it manages):

```python
    def status_changed(self, status: bool) -> None:
        if status:
            if not self._tick_timer.isActive():
                self._tick_timer.start(TICK_MS)
        else:
            self._tick_timer.stop()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `./env/Scripts/python.exe -m pytest tests/test_display_image_tuner_plugin.py tests/ -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/plugins/display_image_tuner/image_tuner_plugin.py tests/test_display_image_tuner_plugin.py
git commit -m "feat: image tuner plugin actually stops/starts on disable/enable"
```

---

### Task 3: DeviceDisplayMapperPlugin honors disabled state

The device-listener watcher threads keep firing on USB events even when "disabled". Tear them down on disable; recreate on enable. Also skip pre-warming the caches when constructed disabled.

**Files:**
- Modify: `src/plugins/device_display_mapper/device_display_mapper_plugin.py`
- Test: `tests/test_device_display_mapper_plugin.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_device_display_mapper_plugin.py`:

```python
import pytest


class _FakeDeviceListener:
    """Minimal stand-in: tracks construction and close calls without
    spinning up real WMI watchers."""

    instances: list["_FakeDeviceListener"] = []

    def __init__(self, parent):
        self.closed = False
        self.parent = parent

        class _Sig:
            def connect(self, *_args, **_kwargs):
                pass

        self.change_detected = _Sig()
        _FakeDeviceListener.instances.append(self)

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def _reset_fake_instances():
    _FakeDeviceListener.instances.clear()
    yield
    _FakeDeviceListener.instances.clear()


@pytest.fixture
def plugin(qtbot, fake_user_settings, monkeypatch):
    """Construct the plugin with the WMI device-listener stubbed out."""
    monkeypatch.setattr(
        "src.plugins.device_display_mapper.device_display_mapper_plugin.DeviceListener",
        _FakeDeviceListener,
    )
    monkeypatch.setattr(
        "src.plugins.device_display_mapper.device_display_mapper_plugin."
        "DeviceDisplayMapperPlugin._prewarm_monitor_cache",
        lambda self: None,
    )
    monkeypatch.setattr(
        "src.plugins.device_display_mapper.device_display_mapper_plugin."
        "DeviceDisplayMapperPlugin.request_usb_devices",
        lambda self, cb: None,
    )

    from src.plugins.device_display_mapper.device_display_mapper_plugin import (
        DeviceDisplayMapperPlugin,
    )
    p = DeviceDisplayMapperPlugin(None)
    qtbot.addWidget(p)
    return p


def test_listener_started_when_enabled(plugin):
    assert plugin.device_listener is not None
    assert len(_FakeDeviceListener.instances) == 1


def test_status_changed_false_closes_listener(plugin):
    plugin.status_changed(False)
    assert plugin.device_listener is None
    assert _FakeDeviceListener.instances[-1].closed is True


def test_status_changed_true_creates_new_listener(plugin):
    plugin.status_changed(False)
    plugin.status_changed(True)
    assert plugin.device_listener is not None
    assert len(_FakeDeviceListener.instances) == 2


def test_construction_skips_listener_when_persisted_disabled(qtbot, fake_user_settings, monkeypatch):
    fake_user_settings.set('plugin_enabled_DeviceDisplayMapperPlugin', False)
    monkeypatch.setattr(
        "src.plugins.device_display_mapper.device_display_mapper_plugin.DeviceListener",
        _FakeDeviceListener,
    )
    monkeypatch.setattr(
        "src.plugins.device_display_mapper.device_display_mapper_plugin."
        "DeviceDisplayMapperPlugin._prewarm_monitor_cache",
        lambda self: None,
    )
    monkeypatch.setattr(
        "src.plugins.device_display_mapper.device_display_mapper_plugin."
        "DeviceDisplayMapperPlugin.request_usb_devices",
        lambda self, cb: None,
    )

    from src.plugins.device_display_mapper.device_display_mapper_plugin import (
        DeviceDisplayMapperPlugin,
    )
    p = DeviceDisplayMapperPlugin(None)
    qtbot.addWidget(p)
    assert p.device_listener is None
    assert _FakeDeviceListener.instances == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `./env/Scripts/python.exe -m pytest tests/test_device_display_mapper_plugin.py -q`
Expected: FAIL — `status_changed` is a no-op; `__init__` always creates the listener.

- [ ] **Step 3: Modify the plugin**

In `src/plugins/device_display_mapper/device_display_mapper_plugin.py`, replace:

```python
        self.last_changed = 0
        self.device_listener = DeviceListener(self)
        self.device_listener.change_detected.connect(self.device_changed)

        self._usb_device_cache: list[Device] | None = None
        self._usb_fetch_subscriptions: list[tuple[Token, Callable[[list[Device]], None]]] = []
        self._usb_fetch_thread: QThread | None = None

        # Pre-warm both caches in the background so the first time the user
        # opens Configuration the panel populates instantly. Both calls
        # schedule work off the GUI thread (runner / QThread) and return
        # immediately; results land in `monitor_info_ctx` and the USB
        # cache. No-op callback because no live receiver is interested yet.
        runner().submit(self._prewarm_monitor_cache)
        self.request_usb_devices(lambda _devices: None)
```

with:

```python
        self.last_changed = 0
        self.device_listener: DeviceListener | None = None

        self._usb_device_cache: list[Device] | None = None
        self._usb_fetch_subscriptions: list[tuple[Token, Callable[[list[Device]], None]]] = []
        self._usb_fetch_thread: QThread | None = None

        if self.is_enabled():
            self._start_runtime()

    def _start_runtime(self) -> None:
        """Spin up the USB watcher and warm caches. Idempotent."""
        if self.device_listener is None:
            self.device_listener = DeviceListener(self)
            self.device_listener.change_detected.connect(self.device_changed)
        # Pre-warm both caches in the background so the first time the user
        # opens Configuration the panel populates instantly. Both calls
        # schedule work off the GUI thread (runner / QThread) and return
        # immediately; results land in `monitor_info_ctx` and the USB
        # cache. No-op callback because no live receiver is interested yet.
        runner().submit(self._prewarm_monitor_cache)
        self.request_usb_devices(lambda _devices: None)

    def _stop_runtime(self) -> None:
        """Tear down the USB watcher. Pre-warmed caches stay (harmless)."""
        if self.device_listener is not None:
            self.device_listener.close()
            self.device_listener = None
```

Then add (anywhere convenient, e.g., just above `closeEvent`):

```python
    def status_changed(self, status: bool) -> None:
        if status:
            self._start_runtime()
        else:
            self._stop_runtime()
```

Also update `closeEvent` to cope with `device_listener` being `None`:

```python
    def closeEvent(self, event):
        if self.device_listener is not None:
            self.device_listener.close()
        event.accept()
```

- [ ] **Step 4: Run the tests**

Run: `./env/Scripts/python.exe -m pytest tests/test_device_display_mapper_plugin.py tests/ -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/plugins/device_display_mapper/device_display_mapper_plugin.py tests/test_device_display_mapper_plugin.py
git commit -m "feat: device-display-mapper actually stops/starts on disable/enable"
```

---

### Task 4: PluginsConfigPanel

A new `ConfigPanel` that lists every toggleable plugin with a checkbox. `apply()` calls `set_enabled` for each. The panel exposes a Qt signal `plugin_toggled(plugin, enabled)` so the dialog can show/hide the corresponding per-plugin tabs live.

**Files:**
- Create: `src/ui/plugins_config_panel.py`
- Test: `tests/test_plugins_config_panel.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_plugins_config_panel.py`:

```python
import pytest


class _FakePlugin:
    """Stand-in for a BaseWidget plugin: just enough surface for the panel."""

    def __init__(self, name: str, enabled: bool = True, toggleable: bool = True):
        self._name = name
        self._enabled = enabled
        self._toggleable = toggleable
        self.toggle_log: list[bool] = []

    def get_display_name(self) -> str:
        return self._name

    def is_enabled(self) -> bool:
        return self._enabled

    def is_toggleable(self) -> bool:
        return self._toggleable

    def set_enabled(self, value: bool) -> None:
        self._enabled = value
        self.toggle_log.append(value)


@pytest.fixture
def make_panel(qtbot, fake_user_settings):
    from src.ui.plugins_config_panel import PluginsConfigPanel

    def _make(plugins):
        panel = PluginsConfigPanel(plugins)
        qtbot.addWidget(panel)
        return panel

    return _make


def test_panel_lists_only_toggleable_plugins(make_panel):
    plugins = [
        _FakePlugin("First", enabled=True, toggleable=True),
        _FakePlugin("Locked", enabled=True, toggleable=False),
        _FakePlugin("Third", enabled=False, toggleable=True),
    ]
    panel = make_panel(plugins)
    assert set(panel._checkboxes.keys()) == {plugins[0], plugins[2]}
    assert panel._checkboxes[plugins[0]].isChecked() is True
    assert panel._checkboxes[plugins[2]].isChecked() is False


def test_apply_calls_set_enabled_only_for_changed_state(make_panel):
    plugins = [
        _FakePlugin("On", enabled=True),
        _FakePlugin("Off", enabled=False),
    ]
    panel = make_panel(plugins)
    panel._checkboxes[plugins[0]].setChecked(False)  # changed
    # plugins[1]: untouched

    assert panel.apply() is True
    assert plugins[0].toggle_log == [False]
    assert plugins[1].toggle_log == []


def test_panel_emits_signal_when_a_checkbox_is_toggled(qtbot, make_panel):
    plugin = _FakePlugin("First")
    panel = make_panel([plugin])

    received: list[tuple] = []
    panel.plugin_toggled.connect(lambda p, val: received.append((p, val)))

    panel._checkboxes[plugin].setChecked(False)
    assert received == [(plugin, False)]

    panel._checkboxes[plugin].setChecked(True)
    assert received == [(plugin, False), (plugin, True)]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `./env/Scripts/python.exe -m pytest tests/test_plugins_config_panel.py -q`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement the panel**

Create `src/ui/plugins_config_panel.py`:

```python
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QLabel, QVBoxLayout, QWidget

from ..base.config_panel import ConfigPanel


class PluginsConfigPanel(ConfigPanel):
    """Master on/off switches for the toggleable plugins.

    `plugin_toggled(plugin, enabled)` fires every time a checkbox state
    changes — `ConfigurationDialog` listens so it can insert/remove the
    matching per-plugin tab live, before the user clicks OK.
    Persistence happens in `apply()`: only changed checkboxes call into
    `plugin.set_enabled` so a no-op OK doesn't trigger restart side
    effects.
    """

    title = "Plugins"

    plugin_toggled = Signal(object, bool)

    def __init__(self, plugins, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._plugins = list(plugins)
        self._checkboxes: dict = {}

        layout = QVBoxLayout(self)
        intro = QLabel("Enable or disable individual plugins. Disabled "
                       "plugins stop their work and are hidden from the "
                       "tray menu and Configuration tabs.", self)
        intro.setWordWrap(True)
        layout.addWidget(intro)

        for plugin in self._plugins:
            if not plugin.is_toggleable():
                continue
            box = QCheckBox(plugin.get_display_name(), self)
            box.setChecked(plugin.is_enabled())
            box.toggled.connect(
                lambda checked, p=plugin: self.plugin_toggled.emit(p, checked))
            layout.addWidget(box)
            self._checkboxes[plugin] = box

        layout.addStretch(1)

    def apply(self) -> bool:
        for plugin, box in self._checkboxes.items():
            checked = box.isChecked()
            if checked != plugin.is_enabled():
                plugin.set_enabled(checked)
        return True
```

- [ ] **Step 4: Run the tests**

Run: `./env/Scripts/python.exe -m pytest tests/test_plugins_config_panel.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/ui/plugins_config_panel.py tests/test_plugins_config_panel.py
git commit -m "feat: plugins config panel with per-plugin enable/disable checkboxes"
```

---

### Task 5: ConfigurationDialog takes plugins, builds Plugins tab, lives-tabs

Restructure the dialog to take `plugins: list[BaseWidget]` instead of `panels: list[ConfigPanel]`. The dialog builds the `PluginsConfigPanel` itself, displays it as the first tab, and renders each enabled plugin's panels behind it. When the Plugins panel emits `plugin_toggled`, the dialog inserts/removes the corresponding panel tabs in place.

`apply()` order: per-plugin panels first (so settings are saved), then the Plugins panel last (so `set_enabled` triggers `status_changed` which reads the freshly-saved settings).

**Files:**
- Modify: `src/ui/configuration_dialog.py`
- Modify: `src/ui/tray_widget.py`
- Test: `tests/test_configuration_dialog.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_configuration_dialog.py`:

```python
import pytest

from src.base.config_panel import ConfigPanel


class _NamedPanel(ConfigPanel):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.title = title
        self.applied = False

    def apply(self) -> bool:
        self.applied = True
        return True


class _FakePlugin:
    instances: list = []

    def __init__(self, name: str, enabled: bool, panels: list[ConfigPanel]):
        self._name = name
        self._enabled = enabled
        self._panels = panels
        self._toggleable = True
        self.set_enabled_log: list[bool] = []
        _FakePlugin.instances.append(self)

    def get_display_name(self):
        return self._name

    def is_enabled(self):
        return self._enabled

    def is_toggleable(self):
        return self._toggleable

    def set_enabled(self, value: bool) -> None:
        self._enabled = value
        self.set_enabled_log.append(value)

    def retrieve_config_panels(self):
        return list(self._panels)


@pytest.fixture(autouse=True)
def _reset():
    _FakePlugin.instances.clear()
    yield
    _FakePlugin.instances.clear()


@pytest.fixture
def make_dialog(qtbot, fake_user_settings):
    from src.ui.configuration_dialog import ConfigurationDialog

    def _make(plugins):
        dlg = ConfigurationDialog(None, plugins)
        qtbot.addWidget(dlg)
        return dlg

    return _make


def test_dialog_includes_plugins_tab_first(make_dialog):
    enabled = _FakePlugin("Enabled", True, [_NamedPanel("EnabledPanel")])
    dlg = make_dialog([enabled])
    tabs = dlg._tabs
    assert tabs.tabText(0) == "Plugins"
    assert tabs.tabText(1) == "EnabledPanel"


def test_disabled_plugin_panels_are_hidden_initially(make_dialog):
    enabled = _FakePlugin("E", True, [_NamedPanel("EPanel")])
    disabled = _FakePlugin("D", False, [_NamedPanel("DPanel")])
    dlg = make_dialog([enabled, disabled])
    titles = [dlg._tabs.tabText(i) for i in range(dlg._tabs.count())]
    assert titles == ["Plugins", "EPanel"]


def test_enabling_via_plugins_panel_inserts_tab(make_dialog):
    enabled = _FakePlugin("E", True, [_NamedPanel("EPanel")])
    disabled = _FakePlugin("D", False, [_NamedPanel("DPanel")])
    dlg = make_dialog([enabled, disabled])
    plugins_panel = dlg._plugins_panel
    plugins_panel._checkboxes[disabled].setChecked(True)

    titles = [dlg._tabs.tabText(i) for i in range(dlg._tabs.count())]
    assert "DPanel" in titles


def test_disabling_via_plugins_panel_removes_tab(make_dialog):
    enabled = _FakePlugin("E", True, [_NamedPanel("EPanel")])
    dlg = make_dialog([enabled])
    plugins_panel = dlg._plugins_panel
    plugins_panel._checkboxes[enabled].setChecked(False)

    titles = [dlg._tabs.tabText(i) for i in range(dlg._tabs.count())]
    assert "EPanel" not in titles


def test_apply_runs_per_plugin_panels_before_plugins_panel(make_dialog):
    enabled = _FakePlugin("E", True, [_NamedPanel("EPanel")])
    dlg = make_dialog([enabled])
    plugins_panel = dlg._plugins_panel
    plugins_panel._checkboxes[enabled].setChecked(False)

    dlg._on_accept()

    # Per-plugin panel applied before the Plugins panel toggled the plugin off.
    panel_apply_call_index = [
        i for i, p in enumerate(dlg._all_panels) if p is enabled._panels[0]
    ][0]
    plugins_panel_index = dlg._all_panels.index(plugins_panel)
    assert panel_apply_call_index < plugins_panel_index
    assert enabled.set_enabled_log == [False]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./env/Scripts/python.exe -m pytest tests/test_configuration_dialog.py -q`
Expected: FAIL — current `ConfigurationDialog` takes a flat list of panels and has no `_tabs` / `_plugins_panel` attributes.

- [ ] **Step 3: Replace `ConfigurationDialog`**

Replace the contents of `src/ui/configuration_dialog.py` with:

```python
import logging

from PySide6.QtCore import QSize
from PySide6.QtWidgets import (
    QDialogButtonBox,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..base.config_panel import ConfigPanel
from ..base.persistent_dialog import PersistentSizeDialog
from .plugins_config_panel import PluginsConfigPanel

DEFAULT_PADDING = QSize(80, 60)


class ConfigurationDialog(PersistentSizeDialog):

    size_settings_prefix = "config_dialog"

    def __init__(self, parent: QWidget | None, plugins) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configuration")
        self._plugins = list(plugins)

        # `_panels_by_plugin` is the persistent record of "which panels does
        # this plugin contribute" (queried once at construction). `_tab_index`
        # tracks which of those are currently inserted in the QTabWidget so
        # we can show/hide them as the user toggles checkboxes.
        self._panels_by_plugin: dict = {}
        self._tab_index: dict = {}

        layout = QVBoxLayout(self)

        self._tabs = QTabWidget(self)
        layout.addWidget(self._tabs)

        self._plugins_panel = PluginsConfigPanel(self._plugins, self)
        self._plugins_panel.plugin_toggled.connect(self._on_plugin_toggled)
        self._tabs.addTab(
            self._wrap_in_scroll(self._plugins_panel),
            self._plugins_panel.title or "Plugins",
        )

        for plugin in self._plugins:
            panels = list(plugin.retrieve_config_panels())
            self._panels_by_plugin[plugin] = panels
            if plugin.is_enabled():
                for panel in panels:
                    self._insert_plugin_panel(plugin, panel)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.adjustSize()
        self.restore_size(self.size() + DEFAULT_PADDING)

    @property
    def _all_panels(self) -> list[ConfigPanel]:
        """Apply order: every per-plugin panel, then the Plugins panel last
        so `set_enabled` runs after per-plugin settings have been saved."""
        out: list[ConfigPanel] = []
        for plugin in self._plugins:
            out.extend(self._panels_by_plugin.get(plugin, []))
        out.append(self._plugins_panel)
        return out

    @staticmethod
    def _wrap_in_scroll(panel: ConfigPanel) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(panel)
        return scroll

    def _insert_plugin_panel(self, plugin, panel: ConfigPanel) -> None:
        if panel in self._tab_index:
            return
        index = self._tabs.addTab(
            self._wrap_in_scroll(panel),
            panel.title or panel.__class__.__name__,
        )
        self._tab_index[panel] = index

    def _remove_plugin_panel(self, panel: ConfigPanel) -> None:
        index = self._tab_index.pop(panel, None)
        if index is None:
            return
        # Removing a tab shifts indices of later tabs; rebuild the map by
        # rescanning what's still in the QTabWidget.
        self._tabs.removeTab(index)
        self._tab_index.clear()
        for i in range(self._tabs.count()):
            scroll = self._tabs.widget(i)
            inner = scroll.widget() if isinstance(scroll, QScrollArea) else scroll
            if isinstance(inner, ConfigPanel) and inner is not self._plugins_panel:
                self._tab_index[inner] = i

    def _on_plugin_toggled(self, plugin, enabled: bool) -> None:
        panels = self._panels_by_plugin.get(plugin, [])
        if enabled:
            for panel in panels:
                self._insert_plugin_panel(plugin, panel)
        else:
            for panel in panels:
                self._remove_plugin_panel(panel)

    def _on_accept(self) -> None:
        for panel in self._all_panels:
            if not panel.apply():
                return
        self.accept()

    def done(self, result: int) -> None:
        # Fires on OK (`accept()`), Cancel (`reject()`), and X (`closeEvent`
        # → default `done(Rejected)`). Run panel cleanup *before* Qt starts
        # destroying anything so panels can cancel in-flight async work
        # while their child widgets are still alive.
        for panel in self._all_panels:
            try:
                panel.cleanup()
            except Exception:
                logging.exception("ConfigPanel.cleanup raised")
        super().done(result)
```

- [ ] **Step 4: Update `tray_widget.open_configuration_dialog` to pass plugins**

In `src/ui/tray_widget.py`, replace the body of `open_configuration_dialog`:

```python
    @Slot()
    def open_configuration_dialog(self) -> None:
        if self._config_dialog is not None:
            self._config_dialog.raise_()
            self._config_dialog.activateWindow()
            return
        self._config_dialog = ConfigurationDialog(None, self.child_components)
        try:
            self._config_dialog.exec()
        finally:
            self._config_dialog = None
```

Drop the now-unused `panels: list[ConfigPanel] = []` block and the `if not panels:` guard — the dialog always opens (Plugins tab is always there).

Drop the now-unused import of `ConfigPanel` if there are no other references. Run `ruff` after to confirm.

- [ ] **Step 5: Run the suite**

Run: `./env/Scripts/python.exe -m pytest tests/ -q && ./env/Scripts/python.exe -m ruff check src/ tests/`
Expected: all pass; ruff clean.

- [ ] **Step 6: Commit**

```bash
git add src/ui/configuration_dialog.py src/ui/tray_widget.py tests/test_configuration_dialog.py
git commit -m "feat: configuration dialog hosts plugins tab and live-toggles per-plugin tabs"
```

---

### Task 6: Tray menu hides disabled plugins; Plugins submenu removed

The tray's main menu is built once at startup. With enable/disable, it must reflect the current state every time the user opens the menu. Switch to a lazy build via `aboutToShow`. Drop the `createPluginsMenu` submenu (its job is now in Configuration).

**Files:**
- Modify: `src/ui/tray_widget.py`

- [ ] **Step 1: Replace the menu wiring**

In `src/ui/tray_widget.py`, drop `createPluginsMenu` entirely. Replace `createMainMenu` so it rebuilds on each `aboutToShow`:

```python
    def createMainMenu(self) -> QMenu:
        menu = QMenu(self)
        menu.aboutToShow.connect(lambda m=menu: self._populate_main_menu(m))
        return menu

    def _populate_main_menu(self, menu: QMenu) -> None:
        menu.clear()

        for plugin in self.child_components:
            if plugin.is_toggleable() and not plugin.is_enabled():
                continue
            for action in plugin.retrieve_menus():
                if isinstance(action, QMenu):
                    menu.addMenu(action)
                elif isinstance(action, QAction):
                    menu.addAction(action)
        menu.addSeparator()

        config_action = QAction('Configuration...', self)
        config_action.triggered.connect(self.open_configuration_dialog)
        menu.addAction(config_action)
        menu.addSeparator()

        logs_action = QAction('View Logs', self)
        logs_action.triggered.connect(self.open_logs_window)
        menu.addAction(logs_action)

        about_action = QAction('About...', self)
        about_action.triggered.connect(self.open_about_dialog)
        menu.addAction(about_action)
        menu.addSeparator()

        quit_action = QAction('Quit', self)
        quit_action.triggered.connect(self.close_slot)
        menu.addAction(quit_action)
```

Also remove the now-unused `createMenu` helper if nothing else uses it (use Grep to verify before deleting). Same for `QActionGroup` import.

- [ ] **Step 2: Verify no callers reference the removed methods**

Run: `Grep("createPluginsMenu|createMenu", path="src/")`
Expected: no remaining hits.

- [ ] **Step 3: Run the suite**

Run: `./env/Scripts/python.exe -m pytest tests/ -q && ./env/Scripts/python.exe -m ruff check src/ tests/`
Expected: all pass; ruff clean.

- [ ] **Step 4: Manual smoke test**

Kill any running tray:

```powershell
Get-Process | Where-Object { $_.Path -eq "$PWD\env\Scripts\python.exe" } | Stop-Process -Force
```

Launch:

```bash
./env/Scripts/python.exe -m src.swiss_windows_knife
```

Verify:
- Right-click the tray → no "Plugins" submenu. The brightness/contrast and HA actions are present (since those plugins are enabled).
- Open Configuration → "Plugins" tab is the first tab. Uncheck "Display brightness & contrast", click OK.
- Right-click the tray → the brightness/contrast menus are gone.
- Open Configuration → the "Sun strength" / "Display tuning" tabs are gone too. Re-check the Image-Tuner checkbox in the Plugins tab → those tabs reappear immediately. Click OK.
- Right-click the tray → brightness/contrast menus are back.
- Quit, relaunch → previously-disabled plugins remain disabled (persistence).

- [ ] **Step 5: Commit**

```bash
git add src/ui/tray_widget.py
git commit -m "feat: tray menu hides disabled plugins, drops the plugins submenu"
```
