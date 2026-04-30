# Plugin Health Status Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface per-plugin health in the tray menu — a worst-state summary line plus a `Health` submenu listing each plugin's state and short status message.

**Architecture:** Each plugin owns a `_current_health: HealthReport` attribute that it updates eagerly from inside its existing event paths (paho callbacks, monitor-runner result handlers, QThread `finished` signals). `BaseWidget.health()` is a pure read; the tray pulls all reports on `aboutToShow` and aggregates worst-state. No new threads, no signals.

**Tech Stack:** Python 3.12, PySide6, paho-mqtt, monitorcontrol, pytest-qt. Design doc: `docs/superpowers/specs/2026-04-30-plugin-health-status-design.md`.

**Branch:** `feat/plugin-health-status` (already created; design doc already committed).

**Commit style:** angular conventional commits. Whole feature ships as `feat:` (one minor bump). The internal `MqttSession.on_disconnected` hook lands in the same `feat:` series. Per-task commits are encouraged; squash-merge is fine.

---

### Task 1: Health types

**Files:**
- Create: `src/base/health.py`
- Test: `tests/test_health_types.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_health_types.py`:

```python
import pytest

from src.base.health import HealthReport, HealthState


def test_health_state_has_four_values():
    assert {s.value for s in HealthState} == {"ok", "warning", "error", "disabled"}


def test_health_report_holds_state_and_message():
    r = HealthReport(HealthState.OK, "Connected")
    assert r.state is HealthState.OK
    assert r.message == "Connected"


def test_health_report_is_frozen():
    r = HealthReport(HealthState.OK, "Connected")
    with pytest.raises((AttributeError, Exception)):
        r.message = "Other"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./env/Scripts/python.exe -m pytest tests/test_health_types.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.base.health'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/base/health.py`:

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

- [ ] **Step 4: Run test to verify it passes**

Run: `./env/Scripts/python.exe -m pytest tests/test_health_types.py -v`
Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/base/health.py tests/test_health_types.py
git commit -m "feat: add HealthState enum and HealthReport dataclass"
```

---

### Task 2: BaseWidget health hook

**Files:**
- Modify: `src/base/base_widget.py`
- Modify: `tests/test_base_widget.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_base_widget.py`:

```python
def test_health_defaults_to_ok_with_empty_message(qtbot, fake_user_settings):
    from src.base.health import HealthReport, HealthState
    widget = BaseWidget(None)
    qtbot.addWidget(widget)
    assert widget.health() == HealthReport(HealthState.OK, "")


def test_set_health_updates_current_health(qtbot, fake_user_settings):
    from src.base.health import HealthReport, HealthState
    widget = BaseWidget(None)
    qtbot.addWidget(widget)
    widget._set_health(HealthState.WARNING, "broker down")
    assert widget.health() == HealthReport(HealthState.WARNING, "broker down")


def test_health_returns_disabled_for_toggleable_off(qtbot, fake_user_settings):
    from src.base.health import HealthReport, HealthState
    widget = BaseWidget(None, is_toggleable=True, is_enabled=False)
    qtbot.addWidget(widget)
    widget._set_health(HealthState.WARNING, "ignored while off")
    assert widget.health() == HealthReport(HealthState.DISABLED, "")


def test_health_ignores_is_enabled_for_non_toggleable_widget(qtbot, fake_user_settings):
    from src.base.health import HealthReport, HealthState
    widget = BaseWidget(None, is_toggleable=False, is_enabled=False)
    qtbot.addWidget(widget)
    widget._set_health(HealthState.OK, "running")
    assert widget.health() == HealthReport(HealthState.OK, "running")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./env/Scripts/python.exe -m pytest tests/test_base_widget.py -v`
Expected: 4 new tests FAIL — `AttributeError: 'BaseWidget' object has no attribute 'health'`.

- [ ] **Step 3: Write minimal implementation**

Modify `src/base/base_widget.py`. Add an import at the top:

```python
from .health import HealthReport, HealthState
```

In `BaseWidget.__init__`, after the existing `self._is_enabled = …` block, add:

```python
        self._current_health: HealthReport = HealthReport(HealthState.OK, "")
```

Add two new methods at the end of the class:

```python
    def health(self) -> HealthReport:
        """Return the plugin's current health snapshot.

        MUST be cheap and non-blocking — no I/O, no DDC calls, no socket
        reads. Subclasses do not override this; instead they call
        `_set_health` from inside whatever event path changed their state.
        """
        if self._is_toggleable and not self._is_enabled:
            return HealthReport(HealthState.DISABLED, "")
        return self._current_health

    def _set_health(self, state: HealthState, message: str) -> None:
        self._current_health = HealthReport(state, message)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./env/Scripts/python.exe -m pytest tests/test_base_widget.py -v`
Expected: All tests PASS (existing + 4 new).

- [ ] **Step 5: Commit**

```bash
git add src/base/base_widget.py tests/test_base_widget.py
git commit -m "feat: BaseWidget exposes health() with disabled short-circuit"
```

---

### Task 3: MqttSession on_disconnected hook

**Files:**
- Modify: `src/plugins/home_assistant_mqtt_pub/mqtt_session.py`
- Modify: `tests/test_ha_session.py`
- Modify: `tests/conftest.py` (add `fire_on_disconnect` to `_FakePahoClient`)

- [ ] **Step 1: Add a `fire_on_disconnect` helper to the existing fake**

Edit `tests/conftest.py`. Add after the existing `fire_on_message` method on `_FakePahoClient`:

```python
    def fire_on_disconnect(self, rc=0):
        self.connected = False
        if self.on_disconnect is not None:
            self.on_disconnect(self, None, None, rc, None)
```

- [ ] **Step 2: Write the failing test**

Append to `tests/test_ha_session.py`:

```python
def test_on_disconnect_fires_callback(fake_paho_client):
    sess = MqttSession(broker_config=_broker(), availability_topic=_ctx().availability_topic)
    fired: list[bool] = []
    sess.on_disconnected = lambda: fired.append(True)
    sess.start()
    fake_paho_client[0].fire_on_connect(rc=0)
    fake_paho_client[0].fire_on_disconnect(rc=0)
    assert fired == [True]


def test_on_disconnect_callback_exceptions_are_swallowed(fake_paho_client):
    sess = MqttSession(broker_config=_broker(), availability_topic=_ctx().availability_topic)

    def boom():
        raise RuntimeError("ignored")

    sess.on_disconnected = boom
    sess.start()
    fake_paho_client[0].fire_on_disconnect(rc=0)  # must not raise
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `./env/Scripts/python.exe -m pytest tests/test_ha_session.py -v -k disconnect`
Expected: 2 tests FAIL — `AttributeError: 'MqttSession' object has no attribute 'on_disconnected'`.

- [ ] **Step 4: Write minimal implementation**

Modify `src/plugins/home_assistant_mqtt_pub/mqtt_session.py`:

In `__init__`, after the existing `self.on_connected = None` line, add:

```python
        self.on_disconnected: Callable[[], None] | None = None
```

Replace `_on_disconnect` with:

```python
    def _on_disconnect(self, client, userdata, flags, rc, properties):
        logging.info("MQTT disconnected rc=%s", rc)
        if self.on_disconnected is not None:
            try:
                self.on_disconnected()
            except Exception:
                logging.exception("on_disconnected hook raised")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `./env/Scripts/python.exe -m pytest tests/test_ha_session.py -v`
Expected: All tests PASS (existing + 2 new).

- [ ] **Step 6: Commit**

```bash
git add src/plugins/home_assistant_mqtt_pub/mqtt_session.py tests/test_ha_session.py tests/conftest.py
git commit -m "feat: MqttSession exposes on_disconnected hook"
```

---

### Task 4: HomeAssistantMqttPubPlugin health wiring

**Files:**
- Modify: `src/plugins/home_assistant_mqtt_pub/home_assistant_mqtt_pub_plugin.py`
- Create: `tests/test_ha_plugin_health.py`

This task also removes the now-redundant `Home Assistant → Configured / Not configured` submenu from `retrieve_menus()` (the unified Health view replaces it).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ha_plugin_health.py`:

```python
import pytest

from src.base.health import HealthState


@pytest.fixture
def configured_settings(fake_user_settings):
    fake_user_settings.set("homeassistant_host", "broker")
    fake_user_settings.set("homeassistant_port", 1883)
    fake_user_settings.set("homeassistant_username", "u")
    fake_user_settings.set("homeassistant_password", "p")
    fake_user_settings.set("homeassistant_client_id", "cid")
    fake_user_settings.set("homeassistant_device_name", "TestPC")
    return fake_user_settings


def _make_plugin(qtbot):
    from src.plugins.home_assistant_mqtt_pub.home_assistant_mqtt_pub_plugin import (
        HomeAssistantMqttPubPlugin,
    )
    plugin = HomeAssistantMqttPubPlugin(parent=None)
    qtbot.addWidget(plugin)
    return plugin


def test_health_is_warning_not_configured_when_no_config(qtbot, fake_user_settings, fake_paho_client):
    plugin = _make_plugin(qtbot)
    report = plugin.health()
    assert report.state is HealthState.WARNING
    assert report.message == "Not configured"


def test_health_is_warning_connecting_after_session_starts(qtbot, configured_settings, fake_paho_client):
    plugin = _make_plugin(qtbot)
    report = plugin.health()
    assert report.state is HealthState.WARNING
    assert report.message == "Connecting…"


def test_health_is_ok_connected_after_on_connect(qtbot, configured_settings, fake_paho_client):
    plugin = _make_plugin(qtbot)
    fake_paho_client[0].fire_on_connect(rc=0)
    qtbot.wait(20)  # cross to GUI thread via QMetaObject.invokeMethod
    report = plugin.health()
    assert report.state is HealthState.OK
    assert report.message == "Connected"


def test_health_returns_to_warning_after_disconnect(qtbot, configured_settings, fake_paho_client):
    plugin = _make_plugin(qtbot)
    fake_paho_client[0].fire_on_connect(rc=0)
    fake_paho_client[0].fire_on_disconnect(rc=0)
    qtbot.wait(20)  # cross to GUI thread via QMetaObject.invokeMethod
    report = plugin.health()
    assert report.state is HealthState.WARNING
    assert report.message == "Disconnected"


def test_retrieve_menus_no_longer_returns_status_submenu(qtbot, configured_settings, fake_paho_client):
    plugin = _make_plugin(qtbot)
    assert plugin.retrieve_menus() == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./env/Scripts/python.exe -m pytest tests/test_ha_plugin_health.py -v`
Expected: 5 tests FAIL — health is OK with empty message (default), and `retrieve_menus()` still returns the legacy submenu.

- [ ] **Step 3: Write minimal implementation**

Modify `src/plugins/home_assistant_mqtt_pub/home_assistant_mqtt_pub_plugin.py`.

Add imports near the top, with the other base imports:

```python
from ...base.health import HealthState
```

In `__init__`, replace the section starting at the `cfg = MqttConfig.load_from_settings(...)` line with:

```python
        cfg = MqttConfig.load_from_settings(self._user_settings)
        self.is_homeassistant_configured = cfg.is_complete()
        if self.is_homeassistant_configured:
            self._set_health(HealthState.WARNING, "Connecting…")
            self._start_session(cfg)
        else:
            self._set_health(HealthState.WARNING, "Not configured")
```

In `_start_session`, after `self._session.on_connected = self._dispatch_on_connected`, add:

```python
        self._session.on_disconnected = self._dispatch_on_disconnected
```

Add a new dispatcher and slot, mirroring `_dispatch_on_connected` / `_run_on_connected`:

```python
    def _dispatch_on_disconnected(self) -> None:
        QMetaObject.invokeMethod(self, "_run_on_disconnected", Qt.ConnectionType.QueuedConnection)

    @Slot()
    def _run_on_disconnected(self) -> None:
        self._set_health(HealthState.WARNING, "Disconnected")
```

In `_run_on_connected`, prepend `self._set_health(HealthState.OK, "Connected")`:

```python
    @Slot()
    def _run_on_connected(self) -> None:
        self._set_health(HealthState.OK, "Connected")
        if self._publisher is not None:
            self._publisher.on_connected()
```

In `status_changed`, ensure the message reflects the new state. Replace the method with:

```python
    @override
    def status_changed(self, status: bool) -> None:
        if status and self._session is None and self.is_homeassistant_configured:
            cfg = MqttConfig.load_from_settings(self._user_settings)
            self._set_health(HealthState.WARNING, "Connecting…")
            self._start_session(cfg)
        elif not status and self._publisher is not None and self._session is not None:
            try:
                self._publisher.delete_all_for_current_device()
            finally:
                self._publisher.stop()
                self._session.stop()
                self._publisher = None
                self._session = None
```

(No health update inside the `not status` branch — `BaseWidget.health()` handles `Disabled` via the toggle short-circuit.)

In `reload_session`, after `self.is_homeassistant_configured = cfg.is_complete()`, replace the trailing `if`-block with:

```python
        if self.is_homeassistant_configured and self.is_enabled():
            self._set_health(HealthState.WARNING, "Connecting…")
            self._start_session(cfg)
        elif not self.is_homeassistant_configured:
            self._set_health(HealthState.WARNING, "Not configured")
```

Replace `retrieve_menus`:

```python
    @override
    def retrieve_menus(self) -> list[QMenu | QAction]:
        return []
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./env/Scripts/python.exe -m pytest tests/test_ha_plugin_health.py tests/test_ha_plugin.py -v`
Expected: All HA-plugin tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/plugins/home_assistant_mqtt_pub/home_assistant_mqtt_pub_plugin.py tests/test_ha_plugin_health.py
git commit -m "feat: home-assistant plugin reports health and drops status submenu"
```

---

### Task 5: DisplayImageTunerPlugin health wiring

**Files:**
- Modify: `src/plugins/display_image_tuner/image_tuner_plugin.py`
- Create: `tests/test_display_image_tuner_health.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_display_image_tuner_health.py`:

```python
from unittest.mock import MagicMock, patch

import monitorcontrol
import pytest

from src.base.health import HealthState


@pytest.fixture
def plugin(qtbot, fake_user_settings):
    from src.plugins.display_image_tuner.image_tuner_plugin import DisplayImageTunerPlugin
    p = DisplayImageTunerPlugin(None)
    qtbot.addWidget(p)
    return p


def test_initial_health_is_ok_auto(plugin):
    report = plugin.health()
    assert report.state is HealthState.OK
    assert report.message == "Auto"


def test_health_message_reflects_manual_brightness(qtbot, fake_user_settings):
    fake_user_settings.set("brightness", 60)
    from src.plugins.display_image_tuner.image_tuner_plugin import DisplayImageTunerPlugin
    p = DisplayImageTunerPlugin(None)
    qtbot.addWidget(p)
    assert p.health().message == "Manual 60"


def _stub_monitor(value: int):
    cm = MagicMock()
    cm.__enter__ = lambda self: self
    cm.__exit__ = lambda self, exc_type, exc, tb: None
    cm.get_luminance = MagicMock(return_value=value)
    cm.set_luminance = MagicMock()
    cm.get_contrast = MagicMock(return_value=value)
    cm.set_contrast = MagicMock()
    return cm


def test_apply_brightness_failure_sets_warning(plugin):
    with patch("monitorcontrol.get_monitors", side_effect=monitorcontrol.VCPError("boom")):
        plugin._apply_brightness(50)
    assert plugin.health().state is HealthState.WARNING
    assert "Monitor error" in plugin.health().message


def test_apply_brightness_success_restores_ok(plugin):
    with patch("monitorcontrol.get_monitors", side_effect=monitorcontrol.VCPError("boom")):
        plugin._apply_brightness(50)
    assert plugin.health().state is HealthState.WARNING

    with patch("monitorcontrol.get_monitors", return_value=[_stub_monitor(0)]):
        plugin._apply_brightness(50)
    assert plugin.health().state is HealthState.OK
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./env/Scripts/python.exe -m pytest tests/test_display_image_tuner_health.py -v`
Expected: 4 tests FAIL — initial message is empty, `_apply_brightness` does not touch health.

- [ ] **Step 3: Write minimal implementation**

Modify `src/plugins/display_image_tuner/image_tuner_plugin.py`.

Add import near the other base imports:

```python
from ...base.health import HealthState
```

In `DisplayImageTunerPlugin.__init__`, after the existing `self.contrast_changed.connect(...)` line and before the `_tick_timer` block, add:

```python
        self._set_health(HealthState.OK, self._mode_message())
```

Add a helper method on the class (anywhere; place it next to `_seed_default_settings`):

```python
    def _mode_message(self) -> str:
        b = self.user_settings.get('brightness')
        if b is None:
            return "Auto"
        return f"Manual {b}"
```

In `_apply_brightness`, replace the body with:

```python
    def _apply_brightness(self, brightness):
        try:
            for i, monitor in enumerate(monitorcontrol.get_monitors()):
                with monitor:
                    if monitor.get_luminance() != brightness:
                        monitor.set_luminance(brightness)
                        logging.info(f"Setting brightness to {brightness} on monitor {i}")
            self._set_health(HealthState.OK, self._mode_message())
        except (ValueError, monitorcontrol.VCPError) as e:
            logging.warning(f"Exception was caught while changing brightness: {e}")
            self._set_health(HealthState.WARNING, f"Monitor error: {e}")
```

Mirror the same change in `_apply_contrast`:

```python
    def _apply_contrast(self, contrast):
        try:
            for i, monitor in enumerate(monitorcontrol.get_monitors()):
                with monitor:
                    if monitor.get_contrast() != contrast:
                        monitor.set_contrast(contrast)
                        logging.info(f"Setting contrast to {contrast} on monitor {i}")
            self._set_health(HealthState.OK, self._mode_message())
        except (ValueError, monitorcontrol.VCPError) as e:
            logging.warning(f"Exception was caught while changing contrast: {e}")
            self._set_health(HealthState.WARNING, f"Monitor error: {e}")
```

In `change_brightness_manual`, after the `self.user_settings.set('brightness', brightness_level)` line, add:

```python
        if self._current_health.state is HealthState.OK:
            self._set_health(HealthState.OK, self._mode_message())
```

Same in `change_contrast_manual` after `self.user_settings.set('contrast', contrast_level)`:

```python
        if self._current_health.state is HealthState.OK:
            self._set_health(HealthState.OK, self._mode_message())
```

In `change_brightness_automatic`, after `self.user_settings.set('brightness', None)`:

```python
        if self._current_health.state is HealthState.OK:
            self._set_health(HealthState.OK, self._mode_message())
```

Same in `change_contrast_automatic` after `self.user_settings.set('contrast', None)`:

```python
        if self._current_health.state is HealthState.OK:
            self._set_health(HealthState.OK, self._mode_message())
```

(The `if state is OK` guard preserves an outstanding Warning until the next successful apply replaces it.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `./env/Scripts/python.exe -m pytest tests/test_display_image_tuner_health.py tests/test_display_image_tuner_plugin.py -v`
Expected: All display-image-tuner tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/plugins/display_image_tuner/image_tuner_plugin.py tests/test_display_image_tuner_health.py
git commit -m "feat: display brightness plugin reports health"
```

---

### Task 6: DeviceDisplayMapperPlugin health wiring

**Files:**
- Modify: `src/plugins/device_display_mapper/device_display_mapper_plugin.py`
- Create: `tests/test_device_display_mapper_health.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_device_display_mapper_health.py`:

```python
import pytest

from src.base.health import HealthState


class _FakeDeviceListener:
    instances: list = []

    def __init__(self, parent):
        self.closed = False

        class _Sig:
            def connect(self, *_args, **_kwargs):
                pass

        self.change_detected = _Sig()
        _FakeDeviceListener.instances.append(self)

    def close(self):
        self.closed = True


class _ExplodingListener:
    def __init__(self, parent):
        raise RuntimeError("WMI unavailable")


@pytest.fixture(autouse=True)
def _reset():
    _FakeDeviceListener.instances.clear()
    yield
    _FakeDeviceListener.instances.clear()


def _patch(monkeypatch, listener_cls):
    monkeypatch.setattr(
        "src.plugins.device_display_mapper.device_display_mapper_plugin.DeviceListener",
        listener_cls,
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


def test_health_is_ok_listening_on_successful_start(qtbot, fake_user_settings, monkeypatch):
    _patch(monkeypatch, _FakeDeviceListener)
    from src.plugins.device_display_mapper.device_display_mapper_plugin import (
        DeviceDisplayMapperPlugin,
    )
    p = DeviceDisplayMapperPlugin(None)
    qtbot.addWidget(p)
    assert p.health().state is HealthState.OK
    assert p.health().message == "Listening"


def test_health_is_error_when_listener_construction_fails(qtbot, fake_user_settings, monkeypatch):
    _patch(monkeypatch, _ExplodingListener)
    from src.plugins.device_display_mapper.device_display_mapper_plugin import (
        DeviceDisplayMapperPlugin,
    )
    p = DeviceDisplayMapperPlugin(None)
    qtbot.addWidget(p)
    assert p.health().state is HealthState.ERROR
    assert "WMI unavailable" in p.health().message
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./env/Scripts/python.exe -m pytest tests/test_device_display_mapper_health.py -v`
Expected: FAIL — first test sees default empty health; second test crashes during `__init__` because `_start_runtime` does not catch the listener exception.

- [ ] **Step 3: Write minimal implementation**

Modify `src/plugins/device_display_mapper/device_display_mapper_plugin.py`.

Add import:

```python
from ...base.health import HealthState
```

Replace `_start_runtime`:

```python
    def _start_runtime(self) -> None:
        """Spin up the USB watcher and warm caches. Idempotent."""
        if self.device_listener is None:
            try:
                self.device_listener = DeviceListener(self)
            except Exception as e:
                logging.exception("Failed to start device listener")
                self._set_health(HealthState.ERROR, str(e))
                return
            self.device_listener.change_detected.connect(self.device_changed)
        runner().submit(self._prewarm_monitor_cache)
        self.request_usb_devices(lambda _devices: None)
        self._set_health(HealthState.OK, "Listening")
```

(`logging` is already imported at the top of the module.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `./env/Scripts/python.exe -m pytest tests/test_device_display_mapper_health.py tests/test_device_display_mapper_plugin.py -v`
Expected: All device-display-mapper tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/plugins/device_display_mapper/device_display_mapper_plugin.py tests/test_device_display_mapper_health.py
git commit -m "feat: usb-display plugin reports health"
```

---

### Task 7: UpdateChecker health wiring

**Files:**
- Modify: `src/components/update_checker.py`
- Create: `tests/test_update_checker_health.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_update_checker_health.py`:

```python
from unittest.mock import patch

import pytest

from src.base.health import HealthState


@pytest.fixture
def checker(qtbot, fake_user_settings):
    from src.components.update_checker import UpdateChecker
    with patch.object(UpdateChecker, "check_updates"):
        c = UpdateChecker(parent=None)
        qtbot.addWidget(c)
    return c


def test_initial_health_is_ok_checking(checker):
    assert checker.health().state is HealthState.OK
    assert checker.health().message == "Checking…"


def test_health_warning_when_check_returns_none(checker):
    checker._busy = True
    checker._on_check_finished(None)
    assert checker.health().state is HealthState.WARNING
    assert checker.health().message == "Check failed"


def test_health_warning_when_watchdog_fires(checker):
    checker._set_busy(True)
    checker._interactive = False
    checker._check_watchdog()
    assert checker.health().state is HealthState.WARNING
    assert checker.health().message == "Check timed out"


def test_health_ok_up_to_date_when_remote_version_not_newer(checker):
    checker._busy = True
    with patch("src.components.update_checker.APP_INFO") as app_info:
        app_info.APP_VERSION = "1.0.0"
        checker._on_check_finished(("1.0.0", "https://example/installer.exe"))
    assert checker.health().state is HealthState.OK
    assert checker.health().message == "Up to date"


def test_health_ok_update_available_when_remote_newer(qtbot, fake_user_settings):
    from src.components.update_checker import UpdateChecker
    with patch.object(UpdateChecker, "check_updates"):
        c = UpdateChecker(parent=None)
        qtbot.addWidget(c)
    c._busy = True
    with patch("src.components.update_checker.APP_INFO") as app_info, \
         patch.object(c, "_confirm_update", return_value=False):
        app_info.APP_VERSION = "1.0.0"
        c._on_check_finished(("9.9.9", "https://example/installer.exe"))
    assert c.health().state is HealthState.OK
    assert c.health().message == "Update available 9.9.9"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./env/Scripts/python.exe -m pytest tests/test_update_checker_health.py -v`
Expected: 5 tests FAIL — health is default OK with empty message.

- [ ] **Step 3: Write minimal implementation**

Modify `src/components/update_checker.py`.

Add import near the other base imports:

```python
from ..base.health import HealthState
```

In `UpdateChecker.__init__`, after `self._active_thread = None`, add:

```python
        self._set_health(HealthState.OK, "Checking…")
```

In `_check_watchdog`, after the `self._set_busy(False)` call, add:

```python
        self._set_health(HealthState.WARNING, "Check timed out")
```

In `_on_check_finished`, modify the `result is None` branch to set health before the `_set_busy(False)`:

```python
        if result is None:
            if self._interactive:
                QMessageBox.warning(
                    self, 'Update check failed',
                    'Could not check for updates. See logs for details.')
            self._set_health(HealthState.WARNING, "Check failed")
            self._set_busy(False)
            return
```

Then in the same method, replace the version-comparison branch (the existing `if _parse_version(remote_version) <= _parse_version(APP_INFO.APP_VERSION):` block) so that both branches set health appropriately:

```python
        remote_version, installer_url = result
        if _parse_version(remote_version) <= _parse_version(APP_INFO.APP_VERSION):
            logging.info(f'No update is needed. Remote: {remote_version}, Local: {APP_INFO.APP_VERSION}')
            if self._interactive:
                QMessageBox.information(
                    self, 'No update available',
                    f'You are on the latest version ({APP_INFO.APP_VERSION}).')
            self._set_health(HealthState.OK, "Up to date")
            self._set_busy(False)
            return

        logging.info(f'Update available: {APP_INFO.APP_VERSION} -> {remote_version}')
        self._set_health(HealthState.OK, f"Update available {remote_version}")
        if not self._confirm_update(remote_version):
            self._set_busy(False)
            return
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./env/Scripts/python.exe -m pytest tests/test_update_checker_health.py tests/test_update_checker_workers.py -v`
Expected: All update-checker tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/components/update_checker.py tests/test_update_checker_health.py
git commit -m "feat: auto-updater reports health"
```

---

### Task 8: Health icon helper

**Files:**
- Create: `src/ui/health_icons.py`
- Create: `tests/test_health_icons.py`

The tray prefixes each row with a coloured 12×12 dot. Generated at runtime via `QPixmap`, cached as module-level constants. No new image assets — keeps `resources.qrc` untouched.

- [ ] **Step 1: Write the failing test**

Create `tests/test_health_icons.py`:

```python
from src.base.health import HealthState


def test_icon_for_state_returns_qicon(qtbot):
    from src.ui.health_icons import icon_for_state

    for state in HealthState:
        icon = icon_for_state(state)
        assert not icon.isNull(), f"icon for {state} is null"


def test_icon_is_cached_per_state(qtbot):
    from src.ui.health_icons import icon_for_state

    a = icon_for_state(HealthState.OK)
    b = icon_for_state(HealthState.OK)
    assert a is b
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./env/Scripts/python.exe -m pytest tests/test_health_icons.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.ui.health_icons'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/ui/health_icons.py`:

```python
from functools import lru_cache

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap

from ..base.health import HealthState

_COLORS: dict[HealthState, QColor] = {
    HealthState.OK: QColor(76, 175, 80),       # green
    HealthState.WARNING: QColor(255, 152, 0),  # amber
    HealthState.ERROR: QColor(244, 67, 54),    # red
    HealthState.DISABLED: QColor(158, 158, 158),  # grey
}

_ICON_SIZE = QSize(12, 12)


@lru_cache(maxsize=None)
def icon_for_state(state: HealthState) -> QIcon:
    pix = QPixmap(_ICON_SIZE)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setBrush(_COLORS[state])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, _ICON_SIZE.width(), _ICON_SIZE.height())
    finally:
        painter.end()
    return QIcon(pix)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./env/Scripts/python.exe -m pytest tests/test_health_icons.py -v`
Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ui/health_icons.py tests/test_health_icons.py
git commit -m "feat: coloured-dot icon helper for health states"
```

---

### Task 9: TrayWidget summary line and Health submenu

**Files:**
- Modify: `src/ui/tray_widget.py`
- Create: `tests/test_tray_widget_health.py`

The tray's `_populate_main_menu` now starts with a disabled summary `QAction` and a `Health` submenu, then continues with each plugin's existing top-level menu actions. The summary text and aggregation rule come from a small helper `aggregate_health` that we test directly.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_tray_widget_health.py`:

```python
import pytest

from src.base.health import HealthReport, HealthState


def test_aggregate_health_all_ok():
    from src.ui.tray_widget import aggregate_health

    reports = [HealthReport(HealthState.OK, ""), HealthReport(HealthState.OK, "")]
    state, text = aggregate_health(reports)
    assert state is HealthState.OK
    assert text == "Health: All OK"


def test_aggregate_health_disabled_does_not_contribute():
    from src.ui.tray_widget import aggregate_health

    reports = [HealthReport(HealthState.OK, ""), HealthReport(HealthState.DISABLED, "")]
    state, text = aggregate_health(reports)
    assert state is HealthState.OK
    assert text == "Health: All OK"


def test_aggregate_health_warning_count():
    from src.ui.tray_widget import aggregate_health

    reports = [
        HealthReport(HealthState.OK, ""),
        HealthReport(HealthState.WARNING, "x"),
        HealthReport(HealthState.WARNING, "y"),
    ]
    state, text = aggregate_health(reports)
    assert state is HealthState.WARNING
    assert text == "Health: 2 warning(s), 0 error(s)"


def test_aggregate_health_error_outranks_warning():
    from src.ui.tray_widget import aggregate_health

    reports = [
        HealthReport(HealthState.WARNING, ""),
        HealthReport(HealthState.ERROR, ""),
    ]
    state, text = aggregate_health(reports)
    assert state is HealthState.ERROR
    assert text == "Health: 1 warning(s), 1 error(s)"


class _StubPlugin:
    def __init__(self, name: str, report: HealthReport):
        self._name = name
        self._report = report

    def get_display_name(self):
        return self._name

    def is_toggleable(self):
        return True

    def is_enabled(self):
        return self._report.state is not HealthState.DISABLED

    def health(self):
        return self._report

    def retrieve_menus(self):
        return []

    def close(self):
        pass


@pytest.fixture
def tray_with_stubs(qtbot, fake_user_settings):
    """Build a TrayWidget-like instance backed by a real QWidget so QAction
    parenting works, but skipping the real plugin construction and the
    QSystemTrayIcon side-effects."""
    from PySide6.QtWidgets import QWidget

    from src.ui.tray_widget import TrayWidget

    class _TrayForTest(TrayWidget):
        def __init__(self, stubs):
            QWidget.__init__(self, parent=None)
            self._config_dialog = None
            self.logger_window = None
            self.child_components = stubs

    def _make(stubs):
        tray = _TrayForTest(stubs)
        qtbot.addWidget(tray)
        return tray

    return _make


def test_main_menu_starts_with_summary_and_health_submenu(qtbot, tray_with_stubs):
    plugins = [
        _StubPlugin("Alpha", HealthReport(HealthState.OK, "Auto")),
        _StubPlugin("Bravo", HealthReport(HealthState.WARNING, "Disconnected")),
    ]
    tray = tray_with_stubs(plugins)

    from PySide6.QtWidgets import QMenu
    menu = QMenu()
    tray._populate_main_menu(menu)
    actions = menu.actions()

    assert actions[0].text() == "Health: 1 warning(s), 0 error(s)"
    assert actions[0].isEnabled() is False  # summary line is informational

    health_submenu = actions[1].menu()
    assert health_submenu is not None
    rows = [a.text() for a in health_submenu.actions()]
    assert rows == ["Alpha — Auto", "Bravo — Disconnected"]


def test_main_menu_summary_all_ok_when_only_disabled_remain(qtbot, tray_with_stubs):
    plugins = [
        _StubPlugin("Alpha", HealthReport(HealthState.DISABLED, "")),
        _StubPlugin("Bravo", HealthReport(HealthState.OK, "Listening")),
    ]
    tray = tray_with_stubs(plugins)

    from PySide6.QtWidgets import QMenu
    menu = QMenu()
    tray._populate_main_menu(menu)
    assert menu.actions()[0].text() == "Health: All OK"


def test_health_row_for_failing_plugin_does_not_break_menu(qtbot, tray_with_stubs):
    class _Bad(_StubPlugin):
        def health(self):
            raise RuntimeError("boom")

    plugins = [
        _Bad("Bad", HealthReport(HealthState.OK, "")),
        _StubPlugin("Good", HealthReport(HealthState.OK, "ok")),
    ]
    tray = tray_with_stubs(plugins)

    from PySide6.QtWidgets import QMenu
    menu = QMenu()
    tray._populate_main_menu(menu)
    health_submenu = menu.actions()[1].menu()
    rows = [a.text() for a in health_submenu.actions()]
    assert rows[0] == "Bad — health() failed"
    assert rows[1] == "Good — ok"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./env/Scripts/python.exe -m pytest tests/test_tray_widget_health.py -v`
Expected: FAIL — `ImportError: cannot import name 'aggregate_health'`, and the menu does not start with a summary line.

- [ ] **Step 3: Write minimal implementation**

Modify `src/ui/tray_widget.py`.

Add imports:

```python
import logging

from ..base.health import HealthReport, HealthState
from .health_icons import icon_for_state
```

Add a module-level helper above the `TrayWidget` class:

```python
def aggregate_health(reports: list[HealthReport]) -> tuple[HealthState, str]:
    """Compute (worst-state, summary-text) for the tray top line.

    Reports in DISABLED state are ignored entirely. When no plugins are
    in WARNING or ERROR, the summary is "Health: All OK"; otherwise it's
    "Health: N warning(s), M error(s)".
    """
    n_warning = sum(1 for r in reports if r.state is HealthState.WARNING)
    n_error = sum(1 for r in reports if r.state is HealthState.ERROR)
    if n_error > 0:
        return HealthState.ERROR, f"Health: {n_warning} warning(s), {n_error} error(s)"
    if n_warning > 0:
        return HealthState.WARNING, f"Health: {n_warning} warning(s), {n_error} error(s)"
    return HealthState.OK, "Health: All OK"
```

Replace `_populate_main_menu` with:

```python
    def _populate_main_menu(self, menu: QMenu) -> None:
        menu.clear()

        reports: list[tuple[BaseWidget, HealthReport]] = []
        for plugin in self.child_components:
            try:
                reports.append((plugin, plugin.health()))
            except Exception:
                logging.exception("plugin %s health() raised", plugin.__class__.__name__)
                reports.append((plugin, HealthReport(HealthState.WARNING, "health() failed")))

        worst_state, summary_text = aggregate_health([r for _, r in reports])
        summary_action = QAction(summary_text, self)
        summary_action.setIcon(icon_for_state(worst_state))
        summary_action.setEnabled(False)
        menu.addAction(summary_action)

        health_submenu = QMenu("Health", menu)
        for plugin, report in reports:
            row = QAction(f"{plugin.get_display_name()} — {report.message}", self)
            row.setIcon(icon_for_state(report.state))
            row.setEnabled(False)
            health_submenu.addAction(row)
        menu.addMenu(health_submenu)
        menu.addSeparator()

        for plugin, _ in reports:
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

- [ ] **Step 4: Run tests to verify they pass**

Run: `./env/Scripts/python.exe -m pytest tests/test_tray_widget_health.py -v`
Expected: 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ui/tray_widget.py tests/test_tray_widget_health.py
git commit -m "feat: tray menu shows health summary line and submenu"
```

---

### Task 10: Manual smoke + full suite

- [ ] **Step 1: Run the full test suite**

Run: `./env/Scripts/python.exe -m pytest tests/ -q`
Expected: full green.

- [ ] **Step 2: Run flake8 to match CI**

Run: `./env/Scripts/python.exe -m flake8 src tests`
Expected: no output (clean).

- [ ] **Step 3: Manual smoke test**

Stop any running tray Python:

```powershell
Get-Process | Where-Object { $_.Path -like "*\swiss-windows-knife\env\Scripts\python.exe" } | Stop-Process -Force
```

Then launch the dev tray:

```bash
./env/Scripts/python.exe -m src.swiss_windows_knife
```

Verify in the tray menu:
- Top line reads `Health: All OK` (green dot) when all plugins are OK; or `Health: N warning(s), M error(s)` with a coloured dot.
- A `Health` submenu lists each plugin with state colour and short message.
- Disabled plugins (toggle one off in `Configuration → Plugins`) appear in the submenu with a grey dot and `Disabled` placeholder.
- Toggling a plugin off/on flips it between `Disabled` and its real state.
- Disconnect the network briefly: the HA row flips from `Connected` to `Disconnected` and back when restored.

- [ ] **Step 4: Push branch**

```bash
git push -u origin feat/plugin-health-status
```

- [ ] **Step 5: Open the PR**

Use whatever PR flow the user prefers. Title example: `feat: plugin health status in tray menu`. Body bullets: summary line + Health submenu, per-plugin states, replaces HA's old status submenu.

---

## Self-review notes

**Spec coverage:**
- Tri-state + Disabled — Task 1.
- `BaseWidget.health()` / `_set_health` / disabled short-circuit — Task 2.
- `MqttSession.on_disconnected` — Task 3.
- HA states (Not configured / Connecting… / Connected / Disconnected) and removal of legacy submenu — Task 4.
- DisplayImageTuner OK/Warning + mode message — Task 5.
- DeviceDisplayMapper OK/Error — Task 6.
- UpdateChecker OK/Warning across all branches — Task 7.
- Coloured-dot icons cached at module level — Task 8.
- TrayWidget summary line + Health submenu + worst-state aggregation + per-plugin failure isolation — Task 9.
- Manual smoke + CI parity — Task 10.

**Type / signature consistency:** `HealthReport(state, message)`, `HealthState.{OK, WARNING, ERROR, DISABLED}`, `BaseWidget.health()`, `BaseWidget._set_health(state, message)`, `MqttSession.on_disconnected: Callable[[], None] | None` — used identically across all tasks.

**Placeholder scan:** No TBDs, no "implement later", no "similar to Task N" handwaves. Every code step shows the actual code.
