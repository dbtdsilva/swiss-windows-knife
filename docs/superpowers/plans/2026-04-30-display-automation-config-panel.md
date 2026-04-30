# Display Automation Config Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the per-monitor "Display automation" submenu (per-monitor on-connect/on-disconnect input choices and USB-watcher selection) out of the tray menu and into a new `DisplayAutomationConfigPanel` shown in the unified Configuration dialog. This eliminates synchronous DDC/CI capability reads and WMI PnP enumeration from the startup path — they happen only when the user opens Configuration and the panel populates itself asynchronously.

**Architecture:** A new `DisplayAutomationConfigPanel(ConfigPanel)` lives next to the device_display_mapper plugin. `DeviceDisplayMapperPlugin.retrieve_menus()` returns `[]`; `retrieve_config_panels()` returns `[DisplayAutomationConfigPanel(self)]`. The panel takes injectable `list_monitors` / `list_usb_devices` callables (defaulted to real impls); tests pass fakes so they don't need hardware. The panel renders a "Loading…" placeholder, dispatches monitor discovery on the existing `runner()` (DDC/CI thread) and USB discovery on a `QThread` worker, then rebuilds its widgets when results arrive over Qt signals. `apply()` writes the same settings keys the menu writes today (`display_usb_watcher`, `display_on_connect_<id>`, `display_on_disconnect_<id>`) so existing user settings carry over with no migration. The runtime hot-path (`device_changed` → `_apply_input_source`) is untouched.

**Tech Stack:** PySide6 (`QGroupBox`, `QComboBox`, `QFormLayout`, `QThread`, `Signal`/`Slot`), existing `runner()` from `src/base/monitor_runner.py`, `monitorcontrol`, `wmi`, pytest + pytest-qt.

---

### Task 1: Discovery helpers (extracted, injectable)

Pulls the synchronous discovery code out of the plugin so the panel can call it from a worker, and tests can replace it. No behavior change yet.

**Files:**
- Create: `src/plugins/device_display_mapper/discovery.py`
- Test: none (these helpers wrap third-party calls — covered by the panel test via fakes in Task 4)

- [ ] **Step 1: Create `discovery.py` with two pure helper functions**

```python
import logging

import monitorcontrol

from .device_listener import DeviceListener
from .monitor_info import MonitorInfo, MonitorInfoCtx


def list_monitors(monitor_info_ctx: MonitorInfoCtx) -> list[MonitorInfo]:
    """Read DDC/CI capabilities for every attached monitor.

    MUST run on the dedicated monitor-runner thread (see
    `src/base/monitor_runner.py`); calling from the GUI thread will block
    for seconds per monitor.
    """
    out: list[MonitorInfo] = []
    for monitor in monitorcontrol.get_monitors():
        with monitor:
            info = monitor_info_ctx.get_monitor_info_by_monitor(monitor=monitor)
            if info is None:
                logging.warning("No monitor info available for one of the attached displays")
                continue
            out.append(info)
    return out


def list_usb_devices(device_listener: DeviceListener):
    """Enumerate currently-attached real USB devices via WMI.

    MUST run off the GUI thread; `Win32_PnPEntity` enumeration is multi-second.
    """
    return device_listener.get_real_usb_devices()
```

- [ ] **Step 2: Run the test suite to confirm nothing regressed**

Run: `./env/Scripts/python.exe -m pytest tests/ -q`
Expected: all existing tests still pass (no new tests yet).

- [ ] **Step 3: Commit**

```bash
git add src/plugins/device_display_mapper/discovery.py
git commit -m "refactor: extract display-automation discovery helpers"
```

---

### Task 2: `DisplayAutomationConfigPanel` — failing test for empty state

A panel constructed with empty fakes shows the placeholder, has no monitor groups, and `apply()` is a no-op.

**Files:**
- Test: `tests/test_display_automation_panel.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_display_automation_panel.py`:

```python
import pytest


class _FakeMonitorInfo:
    def __init__(self, device_id, device_name, model, inputs):
        self.device_id = device_id
        self.device_name = device_name
        self.model = model
        self.inputs = inputs


class _FakeDevice:
    def __init__(self, id, name, description="", manufacturer=""):
        self.id = id
        self.name = name
        self.description = description
        self.manufacturer = manufacturer


@pytest.fixture
def make_panel(qtbot, fake_user_settings, silent_messagebox):
    """Build a panel with controllable, sync providers."""
    from src.plugins.device_display_mapper.display_automation_panel import (
        DisplayAutomationConfigPanel,
    )

    def _make(monitors=None, usb_devices=None):
        panel = DisplayAutomationConfigPanel(
            parent=None,
            list_monitors=lambda: list(monitors or []),
            list_usb_devices=lambda: list(usb_devices or []),
            schedule_discovery=lambda fn: fn(),  # run inline for tests
        )
        qtbot.addWidget(panel)
        return panel

    return _make


def test_panel_with_no_monitors_or_devices_apply_is_noop(make_panel, fake_user_settings):
    panel = make_panel(monitors=[], usb_devices=[])
    assert panel.apply() is True
    # No settings should be written when there is nothing to choose from.
    assert fake_user_settings.get('display_usb_watcher') is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `./env/Scripts/python.exe -m pytest tests/test_display_automation_panel.py -q`
Expected: FAIL with `ModuleNotFoundError: src.plugins.device_display_mapper.display_automation_panel`.

---

### Task 3: `DisplayAutomationConfigPanel` — minimal skeleton

Build a panel that renders nothing (just the placeholder), with the constructor signature the tests expect. No discovery yet — that comes when we add the monitor/USB tests.

**Files:**
- Create: `src/plugins/device_display_mapper/display_automation_panel.py`

- [ ] **Step 1: Implement the panel skeleton**

```python
from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ...base.config_panel import ConfigPanel
from ...base.user_settings import UserSettings


class DisplayAutomationConfigPanel(ConfigPanel):

    title = "Display automation"

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        list_monitors: Callable[[], list[Any]] | None = None,
        list_usb_devices: Callable[[], list[Any]] | None = None,
        schedule_discovery: Callable[[Callable[[], None]], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._user_settings = UserSettings.instance()
        self._list_monitors = list_monitors
        self._list_usb_devices = list_usb_devices
        self._schedule = schedule_discovery or (lambda fn: fn())

        self._monitors: list[Any] = []
        self._usb_devices: list[Any] = []

        self._layout = QVBoxLayout(self)
        self._placeholder = QLabel("Reading monitor capabilities…", self)
        self._layout.addWidget(self._placeholder)

        self._monitor_groups: dict[str, dict] = {}  # device_id -> {connect_combo, disconnect_combo}
        self._usb_combo = None

        if list_monitors is not None or list_usb_devices is not None:
            self._schedule(self._populate)

    def _populate(self) -> None:
        self._monitors = list(self._list_monitors()) if self._list_monitors else []
        self._usb_devices = list(self._list_usb_devices()) if self._list_usb_devices else []
        # Widgets are added in Task 5; for now the placeholder stays.

    def apply(self) -> bool:
        return True
```

- [ ] **Step 2: Run the test to verify it passes**

Run: `./env/Scripts/python.exe -m pytest tests/test_display_automation_panel.py -q`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add src/plugins/device_display_mapper/display_automation_panel.py tests/test_display_automation_panel.py
git commit -m "feat: scaffold display-automation config panel"
```

---

### Task 4: Render USB watcher combobox + persist on apply (failing test → impl → pass)

**Files:**
- Modify: `src/plugins/device_display_mapper/display_automation_panel.py`
- Modify: `tests/test_display_automation_panel.py`

- [ ] **Step 1: Add failing tests for USB rendering and persistence**

Append to `tests/test_display_automation_panel.py`:

```python
def test_panel_renders_usb_devices_and_persists_selection(make_panel, fake_user_settings):
    devices = [
        _FakeDevice(id="USB\\VID_1234&PID_5678\\AAA", name="Dock A", description="USB-C dock"),
        _FakeDevice(id="USB\\VID_9999&PID_1111\\BBB", name="Mouse", description="Optical mouse"),
    ]
    panel = make_panel(monitors=[], usb_devices=devices)

    assert panel._usb_combo is not None
    # First entry is the "(none)" option, then one entry per device, in input order.
    assert panel._usb_combo.count() == 1 + len(devices)

    panel._usb_combo.setCurrentIndex(2)  # Select "Mouse"
    assert panel.apply() is True
    assert fake_user_settings.get('display_usb_watcher') == "USB\\VID_9999&PID_1111\\BBB"


def test_panel_preselects_existing_usb_watcher(make_panel, fake_user_settings):
    fake_user_settings.set('display_usb_watcher', "USB\\VID_1234&PID_5678\\AAA")
    devices = [
        _FakeDevice(id="USB\\VID_1234&PID_5678\\AAA", name="Dock A"),
        _FakeDevice(id="USB\\VID_9999&PID_1111\\BBB", name="Mouse"),
    ]
    panel = make_panel(monitors=[], usb_devices=devices)

    # Index 1 is the first device in our list; 0 is the "(none)" sentinel.
    assert panel._usb_combo.currentIndex() == 1


def test_panel_apply_with_none_clears_usb_watcher(make_panel, fake_user_settings):
    fake_user_settings.set('display_usb_watcher', "USB\\VID_1234&PID_5678\\AAA")
    devices = [_FakeDevice(id="USB\\VID_1234&PID_5678\\AAA", name="Dock A")]
    panel = make_panel(monitors=[], usb_devices=devices)
    panel._usb_combo.setCurrentIndex(0)  # "(none)"

    assert panel.apply() is True
    assert fake_user_settings.get('display_usb_watcher') is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `./env/Scripts/python.exe -m pytest tests/test_display_automation_panel.py -q`
Expected: FAIL — `_usb_combo` is `None`, count check fails.

- [ ] **Step 3: Implement USB rendering and persistence**

Replace the `_populate` method and `apply` in `display_automation_panel.py`, and add helpers:

```python
from PySide6.QtWidgets import QComboBox, QFormLayout, QGroupBox, QLabel, QVBoxLayout, QWidget

USB_WATCHER_KEY = 'display_usb_watcher'


class DisplayAutomationConfigPanel(ConfigPanel):
    # ... (constructor unchanged from Task 3, but call _populate unconditionally now)

    def __init__(self, parent=None, *, list_monitors=None, list_usb_devices=None, schedule_discovery=None):
        super().__init__(parent)
        self._user_settings = UserSettings.instance()
        self._list_monitors = list_monitors
        self._list_usb_devices = list_usb_devices
        self._schedule = schedule_discovery or (lambda fn: fn())

        self._monitors = []
        self._usb_devices = []

        self._layout = QVBoxLayout(self)
        self._placeholder = QLabel("Reading monitor capabilities…", self)
        self._layout.addWidget(self._placeholder)

        self._monitor_groups: dict[str, dict] = {}
        self._usb_combo: QComboBox | None = None

        self._schedule(self._populate)

    def _populate(self) -> None:
        self._monitors = list(self._list_monitors()) if self._list_monitors else []
        self._usb_devices = list(self._list_usb_devices()) if self._list_usb_devices else []

        self._placeholder.hide()
        self._build_usb_section()

    def _build_usb_section(self) -> None:
        box = QGroupBox("USB trigger for display switch", self)
        form = QFormLayout(box)

        combo = QComboBox(box)
        combo.addItem("(none)", userData=None)
        for device in self._usb_devices:
            label = f"{device.name} ({device.id})"
            combo.addItem(label, userData=device.id)

        current = self._user_settings.get(USB_WATCHER_KEY)
        if current is not None:
            for i in range(combo.count()):
                if combo.itemData(i) == current:
                    combo.setCurrentIndex(i)
                    break

        form.addRow("Watch:", combo)
        self._usb_combo = combo
        self._layout.addWidget(box)

    def apply(self) -> bool:
        if self._usb_combo is not None:
            data = self._usb_combo.currentData()
            self._user_settings.set(USB_WATCHER_KEY, data)
        return True
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `./env/Scripts/python.exe -m pytest tests/test_display_automation_panel.py -q`
Expected: PASS (all tests in this file).

- [ ] **Step 5: Commit**

```bash
git add src/plugins/device_display_mapper/display_automation_panel.py tests/test_display_automation_panel.py
git commit -m "feat: render USB-watcher combobox in display-automation panel"
```

---

### Task 5: Render per-monitor input pickers + persist on apply (failing test → impl → pass)

**Files:**
- Modify: `src/plugins/device_display_mapper/display_automation_panel.py`
- Modify: `tests/test_display_automation_panel.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_display_automation_panel.py`:

```python
def test_panel_renders_per_monitor_input_choices_and_persists(make_panel, fake_user_settings):
    monitors = [
        _FakeMonitorInfo(
            device_id="MON-A-DEVID",
            device_name="\\\\.\\DISPLAY1",
            model="Dell U2723QE",
            inputs=["DP1", "HDMI1", "USBC"],
        ),
        _FakeMonitorInfo(
            device_id="MON-B-DEVID",
            device_name="\\\\.\\DISPLAY2",
            model="LG 27UP850",
            inputs=["DP1", "HDMI2"],
        ),
    ]
    panel = make_panel(monitors=monitors, usb_devices=[])

    assert "MON-A-DEVID" in panel._monitor_groups
    assert "MON-B-DEVID" in panel._monitor_groups

    a = panel._monitor_groups["MON-A-DEVID"]
    # Each combobox has the inputs plus a "(unchanged)" sentinel at index 0.
    assert a["connect_combo"].count() == 1 + 3
    assert a["disconnect_combo"].count() == 1 + 3

    a["connect_combo"].setCurrentIndex(2)     # "HDMI1" on connect
    a["disconnect_combo"].setCurrentIndex(1)  # "DP1" on disconnect

    assert panel.apply() is True
    assert fake_user_settings.get('display_on_connect_MON-A-DEVID') == "HDMI1"
    assert fake_user_settings.get('display_on_disconnect_MON-A-DEVID') == "DP1"
    # Untouched monitor keeps its "(unchanged)" sentinel — no key written.
    assert fake_user_settings.get('display_on_connect_MON-B-DEVID') is None


def test_panel_preselects_existing_per_monitor_choice(make_panel, fake_user_settings):
    fake_user_settings.set('display_on_connect_MON-A-DEVID', "HDMI1")
    fake_user_settings.set('display_on_disconnect_MON-A-DEVID', "DP1")
    monitors = [
        _FakeMonitorInfo(
            device_id="MON-A-DEVID",
            device_name="\\\\.\\DISPLAY1",
            model="Dell U2723QE",
            inputs=["DP1", "HDMI1", "USBC"],
        ),
    ]
    panel = make_panel(monitors=monitors, usb_devices=[])

    a = panel._monitor_groups["MON-A-DEVID"]
    # "HDMI1" is index 2 (after the "(unchanged)" sentinel + "DP1" at index 1).
    assert a["connect_combo"].currentText() == "HDMI1"
    assert a["disconnect_combo"].currentText() == "DP1"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `./env/Scripts/python.exe -m pytest tests/test_display_automation_panel.py -q`
Expected: FAIL — no monitor groups built yet.

- [ ] **Step 3: Implement per-monitor rendering and persistence**

Add to `display_automation_panel.py`:

```python
ON_CONNECT_KEY_PREFIX = 'display_on_connect_'
ON_DISCONNECT_KEY_PREFIX = 'display_on_disconnect_'

UNCHANGED_LABEL = "(unchanged)"
```

Add a `_build_monitor_section` method and call it from `_populate` after `_build_usb_section()`:

```python
    def _populate(self) -> None:
        self._monitors = list(self._list_monitors()) if self._list_monitors else []
        self._usb_devices = list(self._list_usb_devices()) if self._list_usb_devices else []

        self._placeholder.hide()
        self._build_usb_section()
        for info in self._monitors:
            self._build_monitor_section(info)

    def _build_monitor_section(self, info) -> None:
        box = QGroupBox(f"{info.model} ({info.device_name})", self)
        form = QFormLayout(box)

        connect_combo = self._make_input_combo(info.inputs, info.device_id, ON_CONNECT_KEY_PREFIX, box)
        disconnect_combo = self._make_input_combo(info.inputs, info.device_id, ON_DISCONNECT_KEY_PREFIX, box)

        form.addRow("On USB connect:", connect_combo)
        form.addRow("On USB disconnect:", disconnect_combo)

        self._monitor_groups[info.device_id] = {
            "connect_combo": connect_combo,
            "disconnect_combo": disconnect_combo,
        }
        self._layout.addWidget(box)

    def _make_input_combo(self, inputs, device_id, key_prefix, parent) -> QComboBox:
        combo = QComboBox(parent)
        combo.addItem(UNCHANGED_LABEL, userData=None)
        for entry in inputs:
            combo.addItem(str(entry), userData=entry)

        current = self._user_settings.get(key_prefix + device_id)
        if current is not None:
            for i in range(combo.count()):
                if str(combo.itemData(i)) == str(current):
                    combo.setCurrentIndex(i)
                    break
        return combo
```

Update `apply()` to also persist per-monitor choices:

```python
    def apply(self) -> bool:
        if self._usb_combo is not None:
            self._user_settings.set(USB_WATCHER_KEY, self._usb_combo.currentData())
        for device_id, widgets in self._monitor_groups.items():
            for key_prefix, combo_key in (
                (ON_CONNECT_KEY_PREFIX, "connect_combo"),
                (ON_DISCONNECT_KEY_PREFIX, "disconnect_combo"),
            ):
                data = widgets[combo_key].currentData()
                if data is None:
                    # "(unchanged)" — leave existing setting alone.
                    continue
                self._user_settings.set(key_prefix + device_id, data)
        return True
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `./env/Scripts/python.exe -m pytest tests/test_display_automation_panel.py -q`
Expected: PASS (all panel tests).

- [ ] **Step 5: Commit**

```bash
git add src/plugins/device_display_mapper/display_automation_panel.py tests/test_display_automation_panel.py
git commit -m "feat: render per-monitor input choices in display-automation panel"
```

---

### Task 6: Async discovery wiring (real `runner()` + WMI worker `QThread`)

The default `schedule_discovery` callable should put discovery off the GUI thread. Monitor reads go via `runner()`; the WMI USB enumeration goes onto a one-shot `QThread`.

**Files:**
- Modify: `src/plugins/device_display_mapper/display_automation_panel.py`
- Modify: `tests/test_display_automation_panel.py`

- [ ] **Step 1: Add a failing test that the panel works with async-style schedulers**

Append to `tests/test_display_automation_panel.py`:

```python
def test_panel_populates_when_discovery_completes_async(make_panel, fake_user_settings):
    """When schedule_discovery defers `_populate`, the panel still shows the
    placeholder before discovery and the widgets after."""
    deferred: list = []

    def make_panel_async(**kwargs):
        from src.plugins.device_display_mapper.display_automation_panel import (
            DisplayAutomationConfigPanel,
        )
        panel = DisplayAutomationConfigPanel(
            parent=None,
            list_monitors=lambda: [],
            list_usb_devices=lambda: [_FakeDevice(id="X", name="X")],
            schedule_discovery=lambda fn: deferred.append(fn),
        )
        return panel

    panel = make_panel_async()
    assert panel._placeholder.isHidden() is False  # placeholder visible
    assert panel._usb_combo is None  # not yet populated

    # Simulate async completion.
    for fn in deferred:
        fn()

    assert panel._placeholder.isHidden() is True
    assert panel._usb_combo is not None
```

- [ ] **Step 2: Run to verify it passes against the existing implementation**

Run: `./env/Scripts/python.exe -m pytest tests/test_display_automation_panel.py -q`
Expected: PASS — the existing implementation already supports custom schedulers.

(If it fails, the most likely cause is that `_placeholder.isHidden()` is True before show — adjust by asserting `_placeholder.text() == "Reading monitor capabilities…"` instead of visibility.)

- [ ] **Step 3: Implement the real default schedulers**

Add at the bottom of `display_automation_panel.py`:

```python
from PySide6.QtCore import QObject, QThread, Qt, Signal

from ...base.monitor_runner import runner
from .device_listener import DeviceListener
from .discovery import list_monitors as _list_monitors_default
from .discovery import list_usb_devices as _list_usb_devices_default
from .monitor_info import MonitorInfoCtx


class _UsbWorker(QObject):
    finished = Signal(list)

    def __init__(self, device_listener: DeviceListener) -> None:
        super().__init__()
        self._device_listener = device_listener

    def run(self) -> None:
        try:
            devices = list(_list_usb_devices_default(self._device_listener))
        except Exception:
            import logging
            logging.exception("USB discovery failed")
            devices = []
        self.finished.emit(devices)


def _default_schedule(panel: "DisplayAutomationConfigPanel", plugin) -> None:
    """Real-world scheduler: monitor discovery on `runner()`, USB on a QThread.

    Both results land back on the GUI thread via queued Qt signals so the
    panel can rebuild widgets safely.
    """
    monitor_results: dict = {"value": None}
    usb_results: dict = {"value": None}

    def _maybe_finalize() -> None:
        if monitor_results["value"] is None or usb_results["value"] is None:
            return
        panel._monitors = monitor_results["value"]
        panel._usb_devices = usb_results["value"]
        panel._placeholder.hide()
        panel._build_usb_section()
        for info in panel._monitors:
            panel._build_monitor_section(info)

    def _on_monitors_done(monitors):
        monitor_results["value"] = monitors
        _maybe_finalize()

    def _on_usb_done(devices):
        usb_results["value"] = devices
        _maybe_finalize()

    # Bridge the runner-thread callback back to the GUI thread.
    class _Bridge(QObject):
        monitors_ready = Signal(list)

    bridge = _Bridge(panel)
    bridge.monitors_ready.connect(_on_monitors_done, Qt.ConnectionType.QueuedConnection)

    def _read_monitors():
        try:
            monitors = _list_monitors_default(plugin.monitor_info_ctx)
        except Exception:
            import logging
            logging.exception("Monitor discovery failed")
            monitors = []
        bridge.monitors_ready.emit(monitors)

    runner().submit(_read_monitors)

    thread = QThread(panel)
    worker = _UsbWorker(plugin.device_listener)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(_on_usb_done, Qt.ConnectionType.QueuedConnection)
    worker.finished.connect(thread.quit)
    thread.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    thread.start()
```

Update the panel constructor to accept a `plugin` reference and use the real scheduler when nothing is injected:

```python
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        list_monitors=None,
        list_usb_devices=None,
        schedule_discovery=None,
    ) -> None:
        super().__init__(parent)
        self._user_settings = UserSettings.instance()
        self._list_monitors = list_monitors
        self._list_usb_devices = list_usb_devices
        self._monitors = []
        self._usb_devices = []

        self._layout = QVBoxLayout(self)
        self._placeholder = QLabel("Reading monitor capabilities…", self)
        self._layout.addWidget(self._placeholder)

        self._monitor_groups: dict[str, dict] = {}
        self._usb_combo: QComboBox | None = None

        if schedule_discovery is not None:
            schedule_discovery(self._populate)
        elif list_monitors is not None or list_usb_devices is not None:
            # Synchronous test path with explicit fakes but no scheduler.
            self._populate()
        else:
            # Production: parent must be the plugin so we can reach its
            # monitor_info_ctx and device_listener.
            _default_schedule(self, parent)
```

- [ ] **Step 4: Run all tests to verify nothing regressed**

Run: `./env/Scripts/python.exe -m pytest tests/ -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/plugins/device_display_mapper/display_automation_panel.py tests/test_display_automation_panel.py
git commit -m "feat: dispatch display-automation discovery off the GUI thread"
```

---

### Task 7: Wire the panel into the plugin and remove the tray submenu

**Files:**
- Modify: `src/plugins/device_display_mapper/device_display_mapper_plugin.py`

- [ ] **Step 1: Replace the menu/panel methods**

Open `src/plugins/device_display_mapper/device_display_mapper_plugin.py` and replace the body of `retrieve_menus` (lines 40-63) and add `retrieve_config_panels`:

```python
    def retrieve_menus(self) -> list[QMenu | QAction]:
        return []

    def retrieve_config_panels(self) -> list[ConfigPanel]:
        from .display_automation_panel import DisplayAutomationConfigPanel
        return [DisplayAutomationConfigPanel(parent=self)]
```

Add the import at the top:

```python
from ...base.config_panel import ConfigPanel
```

Then delete `create_usb_selection_menu` (lines 65-78) and `create_display_selection_menu` (lines 80-95) — they have no other callers.

`change_usb_watcher`, `device_changed`, `_apply_input_source`, and `closeEvent` stay untouched. The runtime hot-path still reads the same settings keys the panel writes.

- [ ] **Step 2: Run the full suite**

Run: `./env/Scripts/python.exe -m pytest tests/ -q`
Expected: PASS.

- [ ] **Step 3: Run flake8 the way pre-commit does**

Run: `./env/Scripts/python.exe -m flake8 src/ tests/`
Expected: clean output.

- [ ] **Step 4: Manual smoke test**

Kill any running tray instance:

```powershell
Get-Process | Where-Object { $_.Path -eq "$PWD\env\Scripts\python.exe" } | Stop-Process -Force
```

Launch from the dev venv:

```bash
./env/Scripts/python.exe -m src.swiss_windows_knife
```

Verify:
- Tray icon appears within ~1 s (previously it took several seconds while DDC/CI capability strings were read).
- Right-clicking the tray no longer shows a "Display automation" submenu.
- Opening "Configuration…" shows a "Display automation" tab. The tab initially shows "Reading monitor capabilities…", then renders the USB combobox and per-monitor input pickers within a few seconds.
- Selecting an input + USB device + clicking OK persists. Re-opening Configuration shows the choices preselected.
- Plug/unplug the configured USB device — input source still switches as before (the runtime path is unchanged).

- [ ] **Step 5: Commit**

```bash
git add src/plugins/device_display_mapper/device_display_mapper_plugin.py
git commit -m "feat: move display automation from tray menu to Configuration"
```
