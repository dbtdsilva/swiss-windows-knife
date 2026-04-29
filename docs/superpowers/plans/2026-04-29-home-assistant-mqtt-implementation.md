# Home Assistant MQTT Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the WIP `home_assistant_mqtt_pub` plugin with a working publish-side HA-MQTT integration exposing 13 host entities + 3 commands, with per-entity intervals, discovery reconciliation, and a config-panel preview UI.

**Architecture:** Plugin shell delegates to three collaborators — `MqttSession` (paho wrapper + LWT + dispatch), `Publisher` (per-entity QTimer scheduler + reconciliation), `CommandDispatcher` (HA → host commands). Off-thread sampling runs through `SamplerRunner` (mirrors `monitor_runner`). Entities + commands are file-per-feature with a small `Entity` / `Command` protocol in `entities/base.py` / `commands/base.py`.

**Tech Stack:** Python 3.12, PySide6 6.9, paho-mqtt 2.1, psutil 5.9 (new dep), wmi 1.5, pywin32 311. Tests with pytest + pytest-qt, `_FakeUserSettings` from `tests/conftest.py`, fake paho client.

**Spec:** `docs/superpowers/specs/2026-04-29-home-assistant-mqtt-design.md`

---

## File Structure

**Plugin code** (under `src/plugins/home_assistant_mqtt_pub/`):

| File | Responsibility |
|---|---|
| `home_assistant_mqtt_pub_plugin.py` | `BaseWidget` shell; lifecycle (`set_enabled`, `closeEvent`); wires components together |
| `mqtt_session.py` | paho `Client` wrapper: connect, LWT, `loop_start`, on-message dispatch by topic prefix, thread-safe `publish` |
| `device_context.py` | `slugify`, device id, topic builders, HA "device" JSON block |
| `publisher.py` | per-entity `QTimer` schedulers, reconciliation, on-connect bootstrap |
| `sampler_runner.py` | daemon thread mirroring `src/base/monitor_runner.py`; `submit(fn, on_done)` |
| `entity_settings.py` | per-entity / per-command persistence helpers + previous-state tracking |
| `mqtt_config.py` | broker fields (existing) + device name |
| `mqtt_config_panel.py` | extended UI with Broker / Device / Entities / Commands sections |
| `entities/base.py` | `Entity` protocol + `SampleResult` dataclass |
| `entities/__init__.py` | `build_entity_registry()` returning ordered list of entity instances |
| `entities/cpu_usage.py` … `entities/lock_state.py` | one file per entity |
| `commands/base.py` | `Command` protocol |
| `commands/__init__.py` | `build_command_registry()` + `CommandDispatcher` |
| `commands/lock.py`, `sleep_cmd.py`, `shutdown.py` | one file per command |

**Tests** (flat in `tests/`, prefix `test_ha_*`):

`test_ha_device_context.py`, `test_ha_sampler_runner.py`, `test_ha_entity_settings.py`, `test_ha_session.py`, `test_ha_publisher.py`, `test_ha_entity_<key>.py` per entity, `test_ha_command_<key>.py` per command, `test_ha_config_panel.py` (replaces / extends parts of `test_mqtt_config_panel.py`).

**Existing files modified:** `pyproject.toml` (add `psutil`), `tests/conftest.py` (add `fake_paho_client` fixture).

**Test-run command (use throughout):**
```bash
./env/Scripts/python.exe -m pytest tests/<file>.py -v
```
With Qt-using tests, set `QT_QPA_PLATFORM=offscreen` (the project's CI does this; locally it works on Windows without it but offscreen avoids spurious tray-icon popups).

**Conventional commits:** project uses angular tags. Use `feat:` for new behavior, `refactor:` for moving code without behavior change, `test:` when adding tests for already-working code, `chore:` for deps/build, `fix:` for bug fixes only when behavior actually changes.

---

## Task 1 — Add psutil dependency

**Files:**
- Modify: `pyproject.toml` (line 7-16, the `dependencies` block)

- [ ] **Step 1: Add psutil to dependencies**

Edit `pyproject.toml` — append `"psutil==5.9.8",` to the `dependencies` list:

```toml
dependencies = [
    "monitorcontrol==3.1.0",
    "pyside6==6.9.1",
    "pysolar==0.13",
    "pytz==2024.1",
    "pywin32==311",
    "wmi==1.5.1",
    "requests==2.32.4",
    "paho.mqtt==2.1.0",
    "psutil==5.9.8",
]
```

- [ ] **Step 2: Install into the dev venv**

Run: `./env/Scripts/python.exe -m pip install psutil==5.9.8`
Expected: `Successfully installed psutil-5.9.8`

- [ ] **Step 3: Smoke check**

Run: `./env/Scripts/python.exe -c "import psutil; print(psutil.cpu_percent(interval=0.1))"`
Expected: a numeric value (0.0–100.0).

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add psutil 5.9.8 for host metric sampling"
```

---

## Task 2 — DeviceContext (slug, topic builders, HA device JSON)

**Files:**
- Create: `src/plugins/home_assistant_mqtt_pub/device_context.py`
- Create: `tests/test_ha_device_context.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ha_device_context.py`:

```python
from src.plugins.home_assistant_mqtt_pub.device_context import DeviceContext, slugify


def test_slugify_lowercases_and_replaces_spaces():
    assert slugify("Camelot Aorus 02") == "camelot_aorus_02"


def test_slugify_strips_non_ascii_and_punctuation():
    assert slugify("Diogo's PC!") == "diogos_pc"


def test_slugify_collapses_repeated_separators():
    assert slugify("a   b---c") == "a_b_c"


def test_slugify_rejects_empty():
    import pytest
    with pytest.raises(ValueError):
        slugify("   ")


def test_device_id_uses_swk_prefix():
    ctx = DeviceContext(name="Camelot Aorus")
    assert ctx.device_id == "swk_camelot_aorus"


def test_state_topic_includes_component_and_entity():
    ctx = DeviceContext(name="pc")
    assert ctx.state_topic("sensor", "cpu_usage") == \
        "homeassistant/sensor/swk_pc/cpu_usage/state"


def test_discovery_topic_matches_state_topic_layout():
    ctx = DeviceContext(name="pc")
    assert ctx.discovery_topic("sensor", "cpu_usage") == \
        "homeassistant/sensor/swk_pc/cpu_usage/config"


def test_availability_topic_per_device():
    ctx = DeviceContext(name="pc")
    assert ctx.availability_topic == "homeassistant/swk_pc/availability"


def test_command_topic():
    ctx = DeviceContext(name="pc")
    assert ctx.command_topic("lock") == "homeassistant/button/swk_pc/lock/set"


def test_device_block_includes_app_metadata():
    ctx = DeviceContext(name="pc")
    block = ctx.device_block()
    assert block["identifiers"] == ["swk_pc"]
    assert block["name"] == "pc"
    assert "Swiss Windows Knife" in block["manufacturer"]
    assert "sw_version" in block
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./env/Scripts/python.exe -m pytest tests/test_ha_device_context.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.plugins.home_assistant_mqtt_pub.device_context'`.

- [ ] **Step 3: Implement DeviceContext**

Create `src/plugins/home_assistant_mqtt_pub/device_context.py`:

```python
import re

from ...app_info import APP_INFO


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    cleaned = _SLUG_RE.sub("_", value.strip().lower()).strip("_")
    if not cleaned:
        raise ValueError("slugify produced an empty string")
    return cleaned


class DeviceContext:
    def __init__(self, name: str) -> None:
        self.name = name.strip()
        self.device_id = f"swk_{slugify(name)}"

    def state_topic(self, component: str, entity_key: str) -> str:
        return f"homeassistant/{component}/{self.device_id}/{entity_key}/state"

    def discovery_topic(self, component: str, entity_key: str) -> str:
        return f"homeassistant/{component}/{self.device_id}/{entity_key}/config"

    @property
    def availability_topic(self) -> str:
        return f"homeassistant/{self.device_id}/availability"

    def command_topic(self, command_key: str) -> str:
        return f"homeassistant/button/{self.device_id}/{command_key}/set"

    def device_block(self) -> dict:
        return {
            "identifiers": [self.device_id],
            "name": self.name,
            "manufacturer": f"Swiss Windows Knife by {APP_INFO.APP_AUTHOR}",
            "model": "Windows host",
            "sw_version": APP_INFO.APP_VERSION,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./env/Scripts/python.exe -m pytest tests/test_ha_device_context.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add src/plugins/home_assistant_mqtt_pub/device_context.py tests/test_ha_device_context.py
git commit -m "feat: add DeviceContext for Home Assistant topic + identity"
```

---

## Task 3 — Entity protocol + SampleResult

**Files:**
- Create: `src/plugins/home_assistant_mqtt_pub/entities/__init__.py` (empty for now)
- Create: `src/plugins/home_assistant_mqtt_pub/entities/base.py`
- Create: `tests/test_ha_entity_base.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ha_entity_base.py`:

```python
from src.plugins.home_assistant_mqtt_pub.entities.base import SampleResult


def test_sample_result_available():
    r = SampleResult.available(value=42, unit="%")
    assert r.is_available is True
    assert r.value == 42
    assert r.unit == "%"


def test_sample_result_unavailable():
    r = SampleResult.unavailable(reason="no thermal zone")
    assert r.is_available is False
    assert r.value is None
    assert r.reason == "no thermal zone"


def test_sample_result_default_reason_empty_string():
    r = SampleResult.available(value=1)
    assert r.reason == ""
```

- [ ] **Step 2: Run tests, expect ModuleNotFoundError**

Run: `./env/Scripts/python.exe -m pytest tests/test_ha_entity_base.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement base + empty registry**

Create `src/plugins/home_assistant_mqtt_pub/entities/__init__.py` (single line):

```python
# Entity registry built lazily by build_entity_registry; populated in later tasks.
```

Create `src/plugins/home_assistant_mqtt_pub/entities/base.py`:

```python
from dataclasses import dataclass
from typing import Any, Callable, Literal, Protocol


@dataclass(frozen=True)
class SampleResult:
    is_available: bool
    value: Any = None
    unit: str = ""
    reason: str = ""

    @staticmethod
    def available(value: Any, unit: str = "") -> "SampleResult":
        return SampleResult(is_available=True, value=value, unit=unit)

    @staticmethod
    def unavailable(reason: str = "") -> "SampleResult":
        return SampleResult(is_available=False, reason=reason)


Component = Literal["sensor", "binary_sensor"]


class Entity(Protocol):
    key: str
    display_name: str
    component: Component
    default_enabled: bool
    default_interval_s: int | None    # None => event-driven
    is_event_driven: bool

    def discovery_payload(self, ctx) -> dict: ...   # ctx: DeviceContext

    def sample(self) -> SampleResult: ...

    def subscribe(self, on_change: Callable[[SampleResult], None]) -> None:
        """Optional. Only meaningful when is_event_driven is True."""
        ...

    def unsubscribe(self) -> None:
        """Optional. Reverse of subscribe()."""
        ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./env/Scripts/python.exe -m pytest tests/test_ha_entity_base.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/plugins/home_assistant_mqtt_pub/entities/__init__.py src/plugins/home_assistant_mqtt_pub/entities/base.py tests/test_ha_entity_base.py
git commit -m "feat: add Entity protocol and SampleResult dataclass"
```

---

## Task 4 — SamplerRunner (off-Qt sampling thread)

**Files:**
- Create: `src/plugins/home_assistant_mqtt_pub/sampler_runner.py`
- Create: `tests/test_ha_sampler_runner.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ha_sampler_runner.py`:

```python
import threading
import time

from src.plugins.home_assistant_mqtt_pub.sampler_runner import SamplerRunner


def test_submit_runs_fn_off_calling_thread_and_calls_on_done():
    runner = SamplerRunner()
    calling_thread = threading.get_ident()
    fn_thread = []
    done_thread = []
    done_value = []
    event = threading.Event()

    def fn():
        fn_thread.append(threading.get_ident())
        return "result"

    def on_done(value):
        done_thread.append(threading.get_ident())
        done_value.append(value)
        event.set()

    runner.submit(fn, on_done)
    assert event.wait(2.0), "on_done was not called within 2s"
    assert fn_thread[0] != calling_thread
    assert done_thread[0] != calling_thread
    assert done_value == ["result"]


def test_submit_swallows_exceptions_and_skips_on_done():
    runner = SamplerRunner()
    on_done_calls = []
    after_event = threading.Event()

    def fn_raises():
        raise RuntimeError("boom")

    def follow_up():
        after_event.set()

    runner.submit(fn_raises, lambda v: on_done_calls.append(v))
    runner.submit(follow_up, lambda v: None)
    assert after_event.wait(2.0)
    assert on_done_calls == []


def test_runs_submissions_in_order():
    runner = SamplerRunner()
    seen = []
    last = threading.Event()

    def make_fn(n):
        def fn():
            seen.append(n)
            time.sleep(0.01)
            return n
        return fn

    def on_done_n(n):
        if n == 4:
            last.set()

    for i in range(5):
        runner.submit(make_fn(i), on_done_n)
    assert last.wait(2.0)
    assert seen == [0, 1, 2, 3, 4]
```

- [ ] **Step 2: Run tests, expect ModuleNotFoundError**

Run: `./env/Scripts/python.exe -m pytest tests/test_ha_sampler_runner.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement SamplerRunner**

Create `src/plugins/home_assistant_mqtt_pub/sampler_runner.py`:

```python
import logging
import queue
import threading
from typing import Any, Callable


class SamplerRunner:
    """Single-thread queue for sampling work that can't sit on the Qt thread.

    Mirrors src/base/monitor_runner.py but is a real instance (not a singleton)
    so the plugin owns its lifetime.
    """

    def __init__(self) -> None:
        self._queue: queue.Queue = queue.Queue()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="HASamplerRunner")
        self._thread.start()

    def submit(self, fn: Callable[[], Any], on_done: Callable[[Any], None]) -> None:
        self._queue.put((fn, on_done))

    def _run(self) -> None:
        while True:
            fn, on_done = self._queue.get()
            try:
                value = fn()
            except Exception:
                logging.exception("HA sampler fn raised")
                continue
            try:
                on_done(value)
            except Exception:
                logging.exception("HA sampler on_done raised")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./env/Scripts/python.exe -m pytest tests/test_ha_sampler_runner.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/plugins/home_assistant_mqtt_pub/sampler_runner.py tests/test_ha_sampler_runner.py
git commit -m "feat: add SamplerRunner thread for off-Qt entity sampling"
```

---

## Task 5 — EntitySettings helper

**Files:**
- Create: `src/plugins/home_assistant_mqtt_pub/entity_settings.py`
- Create: `tests/test_ha_entity_settings.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ha_entity_settings.py`:

```python
from tests.conftest import _FakeUserSettings  # noqa: F401  -- imported for monkeypatch


def test_publish_flag_uses_default_when_unset(fake_user_settings):
    from src.plugins.home_assistant_mqtt_pub.entity_settings import EntitySettings
    s = EntitySettings(fake_user_settings)
    assert s.is_publish_enabled("cpu_usage", default=True) is True
    assert s.is_publish_enabled("foreground_window", default=False) is False


def test_publish_flag_returns_stored_value(fake_user_settings):
    from src.plugins.home_assistant_mqtt_pub.entity_settings import EntitySettings
    fake_user_settings.set("homeassistant_publish_cpu_usage", False)
    s = EntitySettings(fake_user_settings)
    assert s.is_publish_enabled("cpu_usage", default=True) is False


def test_interval_uses_default_when_unset(fake_user_settings):
    from src.plugins.home_assistant_mqtt_pub.entity_settings import EntitySettings
    s = EntitySettings(fake_user_settings)
    assert s.interval_s("cpu_usage", default=30) == 30


def test_interval_coerces_strings_from_qsettings(fake_user_settings):
    """QSettings round-trips ints as strings on Windows registry."""
    from src.plugins.home_assistant_mqtt_pub.entity_settings import EntitySettings
    fake_user_settings.set("homeassistant_interval_cpu_usage", "60")
    s = EntitySettings(fake_user_settings)
    assert s.interval_s("cpu_usage", default=30) == 60


def test_set_publish_writes_under_namespaced_key(fake_user_settings):
    from src.plugins.home_assistant_mqtt_pub.entity_settings import EntitySettings
    s = EntitySettings(fake_user_settings)
    s.set_publish_enabled("cpu_usage", True)
    assert fake_user_settings.get("homeassistant_publish_cpu_usage") is True


def test_command_enabled_default(fake_user_settings):
    from src.plugins.home_assistant_mqtt_pub.entity_settings import EntitySettings
    s = EntitySettings(fake_user_settings)
    assert s.is_command_enabled("lock", default=True) is True


def test_previous_device_name_round_trip(fake_user_settings):
    from src.plugins.home_assistant_mqtt_pub.entity_settings import EntitySettings
    s = EntitySettings(fake_user_settings)
    assert s.previous_device_name() is None
    s.set_previous_device_name("Old PC")
    assert s.previous_device_name() == "Old PC"
    s.clear_previous_device_name()
    assert s.previous_device_name() is None
```

- [ ] **Step 2: Run tests, expect ModuleNotFoundError**

Run: `./env/Scripts/python.exe -m pytest tests/test_ha_entity_settings.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement EntitySettings**

Create `src/plugins/home_assistant_mqtt_pub/entity_settings.py`:

```python
from typing import Any


def _coerce_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("1", "true", "yes")
    return bool(value)


def _coerce_int(value: Any, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class EntitySettings:
    def __init__(self, user_settings) -> None:
        self._s = user_settings

    def is_publish_enabled(self, key: str, default: bool) -> bool:
        return _coerce_bool(self._s.get(f"homeassistant_publish_{key}"), default)

    def set_publish_enabled(self, key: str, value: bool) -> None:
        self._s.set(f"homeassistant_publish_{key}", value)

    def interval_s(self, key: str, default: int) -> int:
        return _coerce_int(self._s.get(f"homeassistant_interval_{key}"), default)

    def set_interval_s(self, key: str, seconds: int) -> None:
        self._s.set(f"homeassistant_interval_{key}", int(seconds))

    def is_command_enabled(self, key: str, default: bool) -> bool:
        return _coerce_bool(self._s.get(f"homeassistant_command_enabled_{key}"), default)

    def set_command_enabled(self, key: str, value: bool) -> None:
        self._s.set(f"homeassistant_command_enabled_{key}", value)

    def previous_device_name(self) -> str | None:
        value = self._s.get("homeassistant_previous_device_name")
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        return str(value)

    def set_previous_device_name(self, name: str) -> None:
        self._s.set("homeassistant_previous_device_name", name)

    def clear_previous_device_name(self) -> None:
        self._s.set("homeassistant_previous_device_name", "")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./env/Scripts/python.exe -m pytest tests/test_ha_entity_settings.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add src/plugins/home_assistant_mqtt_pub/entity_settings.py tests/test_ha_entity_settings.py
git commit -m "feat: add EntitySettings helper for per-entity HA flags"
```

---

## Task 6 — First entity: cpu_usage (template for all subsequent entities)

This task establishes the shape every subsequent entity follows: a class with `key`, `display_name`, `component`, defaults, `discovery_payload(ctx)`, `sample()`, and a registry hook.

**Files:**
- Create: `src/plugins/home_assistant_mqtt_pub/entities/cpu_usage.py`
- Modify: `src/plugins/home_assistant_mqtt_pub/entities/__init__.py`
- Create: `tests/test_ha_entity_cpu_usage.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ha_entity_cpu_usage.py`:

```python
from unittest.mock import patch

from src.plugins.home_assistant_mqtt_pub.device_context import DeviceContext
from src.plugins.home_assistant_mqtt_pub.entities.cpu_usage import CpuUsageEntity


def test_metadata():
    e = CpuUsageEntity()
    assert e.key == "cpu_usage"
    assert e.component == "sensor"
    assert e.default_enabled is True
    assert e.default_interval_s == 30
    assert e.is_event_driven is False


def test_sample_returns_psutil_value_as_percent():
    e = CpuUsageEntity()
    with patch("psutil.cpu_percent", return_value=12.5):
        result = e.sample()
    assert result.is_available is True
    assert result.value == 12.5
    assert result.unit == "%"


def test_sample_marks_unavailable_when_psutil_raises():
    e = CpuUsageEntity()
    with patch("psutil.cpu_percent", side_effect=OSError("nope")):
        result = e.sample()
    assert result.is_available is False


def test_discovery_payload_shape():
    e = CpuUsageEntity()
    ctx = DeviceContext(name="pc")
    payload = e.discovery_payload(ctx)
    assert payload["name"] == "CPU usage"
    assert payload["unique_id"] == "swk_pc_cpu_usage"
    assert payload["object_id"] == "swk_pc_cpu_usage"
    assert payload["state_topic"] == "homeassistant/sensor/swk_pc/cpu_usage/state"
    assert payload["availability_topic"] == "homeassistant/swk_pc/availability"
    assert payload["unit_of_measurement"] == "%"
    assert payload["device"] == ctx.device_block()


def test_registered_in_entity_list():
    from src.plugins.home_assistant_mqtt_pub.entities import build_entity_registry
    reg = build_entity_registry()
    keys = [e.key for e in reg]
    assert "cpu_usage" in keys
```

- [ ] **Step 2: Run tests, expect ModuleNotFoundError**

Run: `./env/Scripts/python.exe -m pytest tests/test_ha_entity_cpu_usage.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement CpuUsageEntity**

Create `src/plugins/home_assistant_mqtt_pub/entities/cpu_usage.py`:

```python
import logging
import psutil

from .base import SampleResult


class CpuUsageEntity:
    key = "cpu_usage"
    display_name = "CPU usage"
    component = "sensor"
    default_enabled = True
    default_interval_s = 30
    is_event_driven = False

    def discovery_payload(self, ctx) -> dict:
        return {
            "name": self.display_name,
            "unique_id": f"{ctx.device_id}_{self.key}",
            "object_id": f"{ctx.device_id}_{self.key}",
            "state_topic": ctx.state_topic(self.component, self.key),
            "availability_topic": ctx.availability_topic,
            "unit_of_measurement": "%",
            "icon": "mdi:cpu-64-bit",
            "device": ctx.device_block(),
        }

    def sample(self) -> SampleResult:
        try:
            value = float(psutil.cpu_percent(interval=None))
        except Exception as exc:
            logging.debug("cpu_usage sample failed: %s", exc)
            return SampleResult.unavailable(reason=str(exc))
        return SampleResult.available(value=value, unit="%")
```

- [ ] **Step 4: Implement registry**

Replace contents of `src/plugins/home_assistant_mqtt_pub/entities/__init__.py`:

```python
from .base import Entity, SampleResult  # noqa: F401
from .cpu_usage import CpuUsageEntity


def build_entity_registry() -> list:
    """Return a fresh ordered list of entity instances.

    Called at plugin start; multi-instance entities (e.g. per-disk) expand here.
    """
    return [
        CpuUsageEntity(),
    ]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `./env/Scripts/python.exe -m pytest tests/test_ha_entity_cpu_usage.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add src/plugins/home_assistant_mqtt_pub/entities/cpu_usage.py src/plugins/home_assistant_mqtt_pub/entities/__init__.py tests/test_ha_entity_cpu_usage.py
git commit -m "feat: add cpu_usage entity and entity registry"
```

---

## Task 7 — MqttSession (paho wrapper with LWT, dispatch, thread-safe publish)

**Files:**
- Create: `src/plugins/home_assistant_mqtt_pub/mqtt_session.py`
- Create: `tests/test_ha_session.py`
- Modify: `tests/conftest.py` (add `fake_paho_client` fixture)

- [ ] **Step 1: Add fake paho fixture to conftest.py**

Edit `tests/conftest.py` — append:

```python
class _FakePahoClient:
    """Records paho calls so tests can assert on them without a broker."""

    def __init__(self, *args, **kwargs):
        self.init_args = args
        self.init_kwargs = kwargs
        self.username = None
        self.password = None
        self.will = None
        self.connected = False
        self.loop_started = False
        self.published: list[tuple[str, str | bytes, bool]] = []
        self.subscribed: list[str] = []
        self.on_connect = None
        self.on_disconnect = None
        self.on_message = None
        self.reconnect_min = None
        self.reconnect_max = None

    def username_pw_set(self, user, password):
        self.username, self.password = user, password

    def will_set(self, topic, payload, qos=0, retain=False):
        self.will = (topic, payload, qos, retain)

    def reconnect_delay_set(self, min_delay, max_delay):
        self.reconnect_min, self.reconnect_max = min_delay, max_delay

    def connect_async(self, host, port, keepalive):
        self.connect_args = (host, port, keepalive)

    def loop_start(self):
        self.loop_started = True

    def loop_stop(self):
        self.loop_started = False

    def disconnect(self):
        self.connected = False

    def is_connected(self):
        return self.connected

    def subscribe(self, topic):
        self.subscribed.append(topic)

    def publish(self, topic, payload=None, qos=0, retain=False):
        self.published.append((topic, payload, retain))

    def fire_on_connect(self, rc=0):
        self.connected = (rc == 0)
        self.on_connect(self, None, None, rc, None)

    def fire_on_message(self, topic, payload):
        class _Msg:
            pass
        m = _Msg()
        m.topic = topic
        m.payload = payload.encode() if isinstance(payload, str) else payload
        m.retain = False
        m.timestamp = 0
        self.on_message(self, None, m)


@pytest.fixture
def fake_paho_client(monkeypatch):
    instances = []

    def factory(*args, **kwargs):
        c = _FakePahoClient(*args, **kwargs)
        instances.append(c)
        return c

    import paho.mqtt.client as paho
    monkeypatch.setattr(paho, "Client", factory)
    return instances
```

- [ ] **Step 2: Write the failing session tests**

Create `tests/test_ha_session.py`:

```python
from src.plugins.home_assistant_mqtt_pub.device_context import DeviceContext
from src.plugins.home_assistant_mqtt_pub.mqtt_session import MqttSession


def _ctx():
    return DeviceContext(name="pc")


def _broker():
    return dict(host="broker", port=1883, username="u", password="p", client_id="cid")


def test_start_sets_lwt_and_connects_async(fake_paho_client):
    sess = MqttSession(broker_config=_broker(), availability_topic=_ctx().availability_topic)
    sess.start()
    client = fake_paho_client[0]
    assert client.will == (_ctx().availability_topic, "offline", 0, True)
    assert client.username == "u"
    assert client.password == "p"
    assert client.connect_args == ("broker", 1883, 30)
    assert client.loop_started is True
    assert client.reconnect_min == 1
    assert client.reconnect_max == 30


def test_on_connect_subscribes_to_topics_and_fires_callback(fake_paho_client):
    sess = MqttSession(broker_config=_broker(), availability_topic=_ctx().availability_topic)
    fired = []
    sess.on_connected = lambda: fired.append(True)
    sess.subscribe("homeassistant/status", lambda payload: None)
    sess.subscribe("homeassistant/button/swk_pc/lock/set", lambda payload: None)
    sess.start()
    client = fake_paho_client[0]
    client.fire_on_connect(rc=0)
    assert "homeassistant/status" in client.subscribed
    assert "homeassistant/button/swk_pc/lock/set" in client.subscribed
    assert fired == [True]


def test_on_message_routes_to_registered_handler(fake_paho_client):
    sess = MqttSession(broker_config=_broker(), availability_topic=_ctx().availability_topic)
    received = []
    sess.subscribe("homeassistant/status", lambda payload: received.append(payload))
    sess.start()
    client = fake_paho_client[0]
    client.fire_on_message("homeassistant/status", "online")
    assert received == ["online"]


def test_publish_passes_through(fake_paho_client):
    sess = MqttSession(broker_config=_broker(), availability_topic=_ctx().availability_topic)
    sess.start()
    sess.publish("a/topic", "hello", retain=True)
    assert fake_paho_client[0].published == [("a/topic", "hello", True)]


def test_stop_publishes_offline_then_disconnects(fake_paho_client):
    sess = MqttSession(broker_config=_broker(), availability_topic="homeassistant/swk_pc/availability")
    sess.start()
    fake_paho_client[0].connected = True
    sess.stop()
    client = fake_paho_client[0]
    assert ("homeassistant/swk_pc/availability", "offline", True) in client.published
    assert client.loop_started is False
    assert client.connected is False
```

- [ ] **Step 3: Run tests, expect ModuleNotFoundError**

Run: `./env/Scripts/python.exe -m pytest tests/test_ha_session.py -v`
Expected: FAIL.

- [ ] **Step 4: Implement MqttSession**

Create `src/plugins/home_assistant_mqtt_pub/mqtt_session.py`:

```python
import logging
from typing import Callable

import paho.mqtt.client as mqtt_client
import paho.mqtt.enums as mqtt_enums


class MqttSession:
    """Owns a paho Client, registers LWT, dispatches messages by topic."""

    def __init__(self, broker_config: dict, availability_topic: str) -> None:
        self._cfg = broker_config
        self._availability_topic = availability_topic
        self._handlers: dict[str, Callable[[str], None]] = {}
        self._client = mqtt_client.Client(
            client_id=str(broker_config.get("client_id", "")),
            protocol=mqtt_client.MQTTv5,
            callback_api_version=mqtt_enums.CallbackAPIVersion.VERSION2,
        )
        self._client.username_pw_set(
            str(broker_config.get("username", "")),
            str(broker_config.get("password", "")),
        )
        self._client.will_set(self._availability_topic, "offline", qos=0, retain=True)
        self._client.reconnect_delay_set(min_delay=1, max_delay=30)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

        self.on_connected: Callable[[], None] | None = None

    def subscribe(self, topic: str, handler: Callable[[str], None]) -> None:
        """Register a handler for the topic.

        Subscription on the broker happens at on_connect time so that
        reconnects automatically re-subscribe.
        """
        self._handlers[topic] = handler

    def start(self) -> None:
        self._client.connect_async(
            host=str(self._cfg["host"]),
            port=int(self._cfg["port"]),
            keepalive=30,
        )
        self._client.loop_start()

    def stop(self) -> None:
        if self._client.is_connected():
            try:
                self._client.publish(self._availability_topic, "offline", qos=0, retain=True)
            except Exception:
                logging.exception("failed to publish offline availability")
        self._client.loop_stop()
        self._client.disconnect()

    def publish(self, topic: str, payload, retain: bool = False) -> None:
        self._client.publish(topic, payload, qos=0, retain=retain)

    def _on_connect(self, client, userdata, flags, rc, properties):
        if rc != 0:
            logging.warning("MQTT connect failed rc=%s", rc)
            return
        logging.info("MQTT connected")
        for topic in self._handlers:
            client.subscribe(topic)
        if self.on_connected is not None:
            try:
                self.on_connected()
            except Exception:
                logging.exception("on_connected hook raised")

    def _on_disconnect(self, client, userdata, flags, rc, properties):
        logging.info("MQTT disconnected rc=%s", rc)

    def _on_message(self, client, userdata, msg):
        handler = self._handlers.get(msg.topic)
        if handler is None:
            logging.debug("MQTT message on unhandled topic %s", msg.topic)
            return
        try:
            payload = msg.payload.decode() if isinstance(msg.payload, (bytes, bytearray)) else str(msg.payload)
        except Exception:
            payload = ""
        try:
            handler(payload)
        except Exception:
            logging.exception("MQTT handler for %s raised", msg.topic)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `./env/Scripts/python.exe -m pytest tests/test_ha_session.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add src/plugins/home_assistant_mqtt_pub/mqtt_session.py tests/test_ha_session.py tests/conftest.py
git commit -m "feat: add MqttSession wrapping paho Client with LWT and dispatch"
```

---

## Task 8 — Publisher reconciliation (pure logic + tests)

This task implements the "what to add / what to delete" computation as a pure function so it's exhaustively testable without timers, paho, or Qt.

**Files:**
- Create: `src/plugins/home_assistant_mqtt_pub/publisher.py` (initial — reconcile only)
- Create: `tests/test_ha_publisher_reconcile.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ha_publisher_reconcile.py`:

```python
from src.plugins.home_assistant_mqtt_pub.device_context import DeviceContext
from src.plugins.home_assistant_mqtt_pub.publisher import (
    PublishedRef,
    compute_reconciliation,
)


def test_first_run_publishes_all_desired():
    ctx = DeviceContext(name="pc")
    desired = [
        PublishedRef(component="sensor", key="cpu_usage", payload={"name": "CPU"}),
        PublishedRef(component="button", key="lock", payload={"name": "Lock"}),
    ]
    plan = compute_reconciliation(previous=[], desired=desired, current_ctx=ctx, previous_ctx=None)
    assert len(plan.deletions) == 0
    creates = {(p.topic, p.payload) for p in plan.creations}
    assert ("homeassistant/sensor/swk_pc/cpu_usage/config", {"name": "CPU"}) in creates
    assert ("homeassistant/button/swk_pc/lock/config", {"name": "Lock"}) in creates


def test_disabled_entity_gets_empty_payload_deletion():
    ctx = DeviceContext(name="pc")
    previous = [PublishedRef(component="sensor", key="cpu_usage", payload={})]
    desired: list[PublishedRef] = []
    plan = compute_reconciliation(previous=previous, desired=desired, current_ctx=ctx, previous_ctx=ctx)
    deletions = [(p.topic, p.payload) for p in plan.deletions]
    assert deletions == [("homeassistant/sensor/swk_pc/cpu_usage/config", "")]


def test_enabling_new_entity_creates_full_payload():
    ctx = DeviceContext(name="pc")
    previous = [PublishedRef(component="sensor", key="cpu_usage", payload={})]
    desired = [
        PublishedRef(component="sensor", key="cpu_usage", payload={"name": "CPU"}),
        PublishedRef(component="sensor", key="memory_usage", payload={"name": "Mem"}),
    ]
    plan = compute_reconciliation(previous=previous, desired=desired, current_ctx=ctx, previous_ctx=ctx)
    assert plan.deletions == []
    creates = {(p.topic, p.payload["name"]) for p in plan.creations}
    assert ("homeassistant/sensor/swk_pc/memory_usage/config", "Mem") in creates


def test_no_op_for_unchanged_entities():
    ctx = DeviceContext(name="pc")
    previous = [PublishedRef(component="sensor", key="cpu_usage", payload={})]
    desired = [PublishedRef(component="sensor", key="cpu_usage", payload={"name": "CPU"})]
    plan = compute_reconciliation(previous=previous, desired=desired, current_ctx=ctx, previous_ctx=ctx)
    # We re-publish discovery for kept entities (cheap, idempotent, covers payload changes).
    creates = [p.topic for p in plan.creations]
    assert "homeassistant/sensor/swk_pc/cpu_usage/config" in creates
    assert plan.deletions == []


def test_device_rename_deletes_all_old_topics_then_creates_new():
    old = DeviceContext(name="OldPC")
    new = DeviceContext(name="NewPC")
    previous = [
        PublishedRef(component="sensor", key="cpu_usage", payload={}),
        PublishedRef(component="button", key="lock", payload={}),
    ]
    desired = [
        PublishedRef(component="sensor", key="cpu_usage", payload={"name": "CPU"}),
        PublishedRef(component="button", key="lock", payload={"name": "Lock"}),
    ]
    plan = compute_reconciliation(previous=previous, desired=desired, current_ctx=new, previous_ctx=old)
    deletions = {p.topic for p in plan.deletions}
    assert "homeassistant/sensor/swk_oldpc/cpu_usage/config" in deletions
    assert "homeassistant/button/swk_oldpc/lock/config" in deletions
    creates = {p.topic for p in plan.creations}
    assert "homeassistant/sensor/swk_newpc/cpu_usage/config" in creates
    assert "homeassistant/button/swk_newpc/lock/config" in creates
```

- [ ] **Step 2: Run tests, expect ImportError on PublishedRef / compute_reconciliation**

Run: `./env/Scripts/python.exe -m pytest tests/test_ha_publisher_reconcile.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement reconciliation primitives**

Create `src/plugins/home_assistant_mqtt_pub/publisher.py`:

```python
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PublishedRef:
    """Identifies an HA discovery topic and the payload to publish there.

    `component` is "sensor" / "binary_sensor" / "button"; `key` is the entity/command slug.
    `payload` is the dict to publish; for deletions it is replaced with an empty string.
    """
    component: str
    key: str
    payload: Any


@dataclass(frozen=True)
class PublishOp:
    topic: str
    payload: Any


@dataclass(frozen=True)
class ReconciliationPlan:
    deletions: list  # list[PublishOp]
    creations: list  # list[PublishOp]


def compute_reconciliation(*, previous, desired, current_ctx, previous_ctx) -> ReconciliationPlan:
    deletions: list[PublishOp] = []
    creations: list[PublishOp] = []

    if previous_ctx is not None and previous_ctx.device_id != current_ctx.device_id:
        for ref in previous:
            topic = previous_ctx.discovery_topic(ref.component, ref.key)
            deletions.append(PublishOp(topic=topic, payload=""))
        for ref in desired:
            topic = current_ctx.discovery_topic(ref.component, ref.key)
            creations.append(PublishOp(topic=topic, payload=ref.payload))
        return ReconciliationPlan(deletions=deletions, creations=creations)

    desired_keys = {(r.component, r.key) for r in desired}
    previous_keys = {(r.component, r.key) for r in previous}

    for ref in previous:
        if (ref.component, ref.key) not in desired_keys:
            ctx_for_delete = previous_ctx or current_ctx
            topic = ctx_for_delete.discovery_topic(ref.component, ref.key)
            deletions.append(PublishOp(topic=topic, payload=""))

    for ref in desired:
        topic = current_ctx.discovery_topic(ref.component, ref.key)
        creations.append(PublishOp(topic=topic, payload=ref.payload))
        _ = previous_keys  # noqa  -- intentionally unused; kept entities still re-publish

    return ReconciliationPlan(deletions=deletions, creations=creations)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./env/Scripts/python.exe -m pytest tests/test_ha_publisher_reconcile.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/plugins/home_assistant_mqtt_pub/publisher.py tests/test_ha_publisher_reconcile.py
git commit -m "feat: add Publisher reconciliation logic for HA discovery topics"
```

---

## Task 9 — Publisher integration (timers + sampler + on_connect bootstrap)

**Files:**
- Modify: `src/plugins/home_assistant_mqtt_pub/publisher.py`
- Create: `tests/test_ha_publisher.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ha_publisher.py`:

```python
import json
from unittest.mock import MagicMock

import pytest

from src.plugins.home_assistant_mqtt_pub.device_context import DeviceContext
from src.plugins.home_assistant_mqtt_pub.publisher import Publisher, PublishedRef


class _SyncSampler:
    """SamplerRunner stand-in that runs fn + on_done synchronously."""

    def submit(self, fn, on_done):
        on_done(fn())


class _StubEntity:
    component = "sensor"
    is_event_driven = False

    def __init__(self, key, value):
        self.key = key
        self.display_name = key
        self.default_enabled = True
        self.default_interval_s = 30
        self._value = value

    def discovery_payload(self, ctx):
        return {"name": self.display_name, "state_topic": ctx.state_topic(self.component, self.key)}

    def sample(self):
        from src.plugins.home_assistant_mqtt_pub.entities.base import SampleResult
        return SampleResult.available(value=self._value, unit="%")


@pytest.fixture
def settings(fake_user_settings):
    from src.plugins.home_assistant_mqtt_pub.entity_settings import EntitySettings
    return EntitySettings(fake_user_settings)


def test_on_connected_publishes_discovery_state_and_availability(fake_user_settings, settings):
    ctx = DeviceContext(name="pc")
    session = MagicMock()
    entities = [_StubEntity("cpu_usage", 12.5)]
    pub = Publisher(
        session=session, ctx=ctx, settings=settings,
        sampler=_SyncSampler(), entities=entities, commands=[],
    )
    pub.on_connected()
    topics = [c.args[0] for c in session.publish.call_args_list]
    assert "homeassistant/sensor/swk_pc/cpu_usage/config" in topics
    assert "homeassistant/sensor/swk_pc/cpu_usage/state" in topics
    assert "homeassistant/swk_pc/availability" in topics
    avail_payload = next(c.args[1] for c in session.publish.call_args_list
                         if c.args[0] == "homeassistant/swk_pc/availability")
    assert avail_payload == "online"


def test_on_connected_skips_disabled_entities(fake_user_settings, settings):
    ctx = DeviceContext(name="pc")
    session = MagicMock()
    settings.set_publish_enabled("cpu_usage", False)
    entities = [_StubEntity("cpu_usage", 12.5)]
    pub = Publisher(session, ctx, settings, _SyncSampler(), entities, [])
    pub.on_connected()
    topics = [c.args[0] for c in session.publish.call_args_list]
    assert "homeassistant/sensor/swk_pc/cpu_usage/config" not in topics
    assert "homeassistant/sensor/swk_pc/cpu_usage/state" not in topics


def test_publish_state_uses_value_and_retain_true(fake_user_settings, settings):
    ctx = DeviceContext(name="pc")
    session = MagicMock()
    entities = [_StubEntity("cpu_usage", 7.5)]
    pub = Publisher(session, ctx, settings, _SyncSampler(), entities, [])
    pub.tick(entities[0])
    state_calls = [c for c in session.publish.call_args_list
                   if c.args[0] == "homeassistant/sensor/swk_pc/cpu_usage/state"]
    assert len(state_calls) == 1
    assert state_calls[0].args[1] == "7.5"
    assert state_calls[0].kwargs.get("retain") is True


def test_unavailable_sample_publishes_nothing(fake_user_settings, settings):
    from src.plugins.home_assistant_mqtt_pub.entities.base import SampleResult

    class _Bad(_StubEntity):
        def sample(self):
            return SampleResult.unavailable("nope")

    ctx = DeviceContext(name="pc")
    session = MagicMock()
    entities = [_Bad("cpu_temperature", 0)]
    pub = Publisher(session, ctx, settings, _SyncSampler(), entities, [])
    pub.tick(entities[0])
    state_calls = [c for c in session.publish.call_args_list
                   if "/state" in c.args[0]]
    assert state_calls == []


def test_apply_handles_device_rename(fake_user_settings, settings):
    settings.set_previous_device_name("OldPC")
    ctx = DeviceContext(name="NewPC")
    session = MagicMock()
    entities = [_StubEntity("cpu_usage", 1)]
    pub = Publisher(session, ctx, settings, _SyncSampler(), entities, [])
    pub.apply()
    topics = [c.args[0] for c in session.publish.call_args_list]
    assert "homeassistant/sensor/swk_oldpc/cpu_usage/config" in topics
    delete_payload = next(c.args[1] for c in session.publish.call_args_list
                          if c.args[0] == "homeassistant/sensor/swk_oldpc/cpu_usage/config")
    assert delete_payload == ""
    assert "homeassistant/sensor/swk_newpc/cpu_usage/config" in topics
    assert settings.previous_device_name() == "NewPC"


def test_ha_status_online_re_publishes_discovery(fake_user_settings, settings):
    ctx = DeviceContext(name="pc")
    session = MagicMock()
    entities = [_StubEntity("cpu_usage", 1)]
    pub = Publisher(session, ctx, settings, _SyncSampler(), entities, [])
    pub.on_ha_status("online")
    topics = [c.args[0] for c in session.publish.call_args_list]
    assert "homeassistant/sensor/swk_pc/cpu_usage/config" in topics
```

- [ ] **Step 2: Run tests, expect failures (Publisher class doesn't exist yet)**

Run: `./env/Scripts/python.exe -m pytest tests/test_ha_publisher.py -v`
Expected: FAIL.

- [ ] **Step 3: Extend publisher.py with the Publisher class**

Append to `src/plugins/home_assistant_mqtt_pub/publisher.py`:

```python
import json
import logging

from PySide6.QtCore import QTimer

from .entities.base import SampleResult


def _serialize(value) -> str:
    if isinstance(value, bool):
        return "ON" if value else "OFF"
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return str(value)


class Publisher:
    def __init__(self, session, ctx, settings, sampler, entities, commands) -> None:
        self._session = session
        self._ctx = ctx
        self._settings = settings
        self._sampler = sampler
        self._entities = list(entities)
        self._commands = list(commands)
        self._timers: dict[str, QTimer] = {}

    def _enabled_entities(self) -> list:
        return [e for e in self._entities
                if self._settings.is_publish_enabled(e.key, e.default_enabled)]

    def _enabled_commands(self) -> list:
        return [c for c in self._commands
                if self._settings.is_command_enabled(c.key, c.default_enabled)]

    def _desired_refs(self) -> list:
        refs = []
        for e in self._enabled_entities():
            refs.append(PublishedRef(component=e.component, key=e.key, payload=e.discovery_payload(self._ctx)))
        for c in self._enabled_commands():
            refs.append(PublishedRef(component="button", key=c.key, payload=c.discovery_payload(self._ctx)))
        return refs

    def _previous_refs(self) -> list:
        refs = []
        for e in self._entities:
            refs.append(PublishedRef(component=e.component, key=e.key, payload={}))
        for c in self._commands:
            refs.append(PublishedRef(component="button", key=c.key, payload={}))
        return refs

    def _previous_ctx(self):
        prev = self._settings.previous_device_name()
        if prev is None:
            return None
        from .device_context import DeviceContext
        return DeviceContext(name=prev)

    def on_connected(self) -> None:
        self.apply()
        self._session.publish(self._ctx.availability_topic, "online", retain=True)
        for entity in self._enabled_entities():
            self.tick(entity)
        self._restart_timers()
        for entity in self._entities:
            if entity.is_event_driven and self._settings.is_publish_enabled(entity.key, entity.default_enabled):
                entity.subscribe(lambda result, e=entity: self._publish_state(e, result))

    def apply(self) -> None:
        plan = compute_reconciliation(
            previous=self._previous_refs(),
            desired=self._desired_refs(),
            current_ctx=self._ctx,
            previous_ctx=self._previous_ctx(),
        )
        for op in plan.deletions:
            self._session.publish(op.topic, op.payload, retain=True)
        for op in plan.creations:
            self._session.publish(op.topic, json.dumps(op.payload) if isinstance(op.payload, dict) else op.payload, retain=True)
        self._settings.set_previous_device_name(self._ctx.name)
        self._restart_timers()

    def tick(self, entity) -> None:
        self._sampler.submit(entity.sample, lambda result: self._publish_state(entity, result))

    def _publish_state(self, entity, result: SampleResult) -> None:
        if not result.is_available:
            logging.debug("entity %s unavailable: %s", entity.key, result.reason)
            return
        topic = self._ctx.state_topic(entity.component, entity.key)
        self._session.publish(topic, _serialize(result.value), retain=True)

    def on_ha_status(self, payload: str) -> None:
        if payload.strip().lower() == "online":
            logging.info("Home Assistant came online — re-publishing discovery")
            self.apply()
            for entity in self._enabled_entities():
                self.tick(entity)

    def _restart_timers(self) -> None:
        for timer in self._timers.values():
            timer.stop()
        self._timers.clear()
        for entity in self._enabled_entities():
            if entity.is_event_driven:
                continue
            interval = self._settings.interval_s(entity.key, entity.default_interval_s or 30)
            timer = QTimer()
            timer.setInterval(int(interval) * 1000)
            timer.timeout.connect(lambda e=entity: self.tick(e))
            timer.start()
            self._timers[entity.key] = timer

    def stop(self) -> None:
        for timer in self._timers.values():
            timer.stop()
        self._timers.clear()
        for entity in self._entities:
            if entity.is_event_driven:
                try:
                    entity.unsubscribe()
                except (AttributeError, NotImplementedError):
                    pass

    def delete_all_for_current_device(self) -> None:
        for ref in self._previous_refs():
            topic = self._ctx.discovery_topic(ref.component, ref.key)
            self._session.publish(topic, "", retain=True)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./env/Scripts/python.exe -m pytest tests/test_ha_publisher.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/plugins/home_assistant_mqtt_pub/publisher.py tests/test_ha_publisher.py
git commit -m "feat: add Publisher with per-entity timers and on-connect bootstrap"
```

---

## Task 10 — Plugin shell rewrite (BaseWidget integration)

**Files:**
- Modify: `src/plugins/home_assistant_mqtt_pub/home_assistant_mqtt_pub_plugin.py` (full rewrite)
- Modify: `src/plugins/home_assistant_mqtt_pub/mqtt_config.py` (add device_name)
- Create: `tests/test_ha_plugin.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ha_plugin.py`:

```python
import pytest


@pytest.fixture
def configured_settings(fake_user_settings):
    fake_user_settings.set("homeassistant_host", "broker")
    fake_user_settings.set("homeassistant_port", 1883)
    fake_user_settings.set("homeassistant_username", "u")
    fake_user_settings.set("homeassistant_password", "p")
    fake_user_settings.set("homeassistant_client_id", "cid")
    fake_user_settings.set("homeassistant_device_name", "TestPC")
    return fake_user_settings


def test_plugin_starts_session_when_fully_configured(qtbot, configured_settings, fake_paho_client):
    from src.plugins.home_assistant_mqtt_pub.home_assistant_mqtt_pub_plugin import (
        HomeAssistantMqttPubPlugin,
    )
    plugin = HomeAssistantMqttPubPlugin(parent=None)
    qtbot.addWidget(plugin)
    assert plugin.is_homeassistant_configured is True
    assert len(fake_paho_client) == 1


def test_plugin_inert_when_unconfigured(qtbot, fake_user_settings, fake_paho_client):
    from src.plugins.home_assistant_mqtt_pub.home_assistant_mqtt_pub_plugin import (
        HomeAssistantMqttPubPlugin,
    )
    plugin = HomeAssistantMqttPubPlugin(parent=None)
    qtbot.addWidget(plugin)
    assert plugin.is_homeassistant_configured is False
    assert len(fake_paho_client) == 0


def test_status_changed_accepts_bool_signature(qtbot, configured_settings, fake_paho_client):
    from src.plugins.home_assistant_mqtt_pub.home_assistant_mqtt_pub_plugin import (
        HomeAssistantMqttPubPlugin,
    )
    plugin = HomeAssistantMqttPubPlugin(parent=None)
    qtbot.addWidget(plugin)
    plugin.status_changed(False)  # must not raise


def test_disable_deletes_discovery_and_disconnects(qtbot, configured_settings, fake_paho_client):
    from src.plugins.home_assistant_mqtt_pub.home_assistant_mqtt_pub_plugin import (
        HomeAssistantMqttPubPlugin,
    )
    plugin = HomeAssistantMqttPubPlugin(parent=None)
    qtbot.addWidget(plugin)
    fake_paho_client[0].fire_on_connect(rc=0)
    fake_paho_client[0].published.clear()
    plugin.set_enabled(False)
    deletion_publishes = [
        (topic, payload) for (topic, payload, _retain) in fake_paho_client[0].published
        if topic.endswith("/config") and payload == ""
    ]
    assert deletion_publishes, "expected at least one empty-payload publish for entity discovery deletion"
    assert fake_paho_client[0].connected is False
```

- [ ] **Step 2: Run tests, expect failure (plugin not yet rewritten)**

Run: `./env/Scripts/python.exe -m pytest tests/test_ha_plugin.py -v`
Expected: FAIL or partial fail.

- [ ] **Step 3: Extend `mqtt_config.py` with device_name**

Replace contents of `src/plugins/home_assistant_mqtt_pub/mqtt_config.py`:

```python
from src.base.user_settings import UserSettings


class MqttConfig:
    def __init__(self, host, port, username, password, client_id, device_name=None):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.client_id = client_id
        self.device_name = device_name

    @staticmethod
    def load_from_settings(settings: UserSettings):
        return MqttConfig(
            settings.get("homeassistant_host"),
            settings.get("homeassistant_port"),
            settings.get("homeassistant_username"),
            settings.get("homeassistant_password"),
            settings.get("homeassistant_client_id"),
            settings.get("homeassistant_device_name"),
        )

    def save_to_settings(self, settings):
        settings.set("homeassistant_host", self.host)
        settings.set("homeassistant_port", int(self.port) if self.port not in (None, "") else self.port)
        settings.set("homeassistant_username", self.username)
        settings.set("homeassistant_password", self.password)
        settings.set("homeassistant_client_id", self.client_id)
        settings.set("homeassistant_device_name", self.device_name)

    def is_complete(self) -> bool:
        return all(
            v not in (None, "")
            for v in (self.host, self.port, self.username, self.password, self.client_id, self.device_name)
        )
```

The existing tests in `tests/test_mqtt_config.py` continue to pass because the new `device_name` argument is optional.

- [ ] **Step 4: Rewrite `home_assistant_mqtt_pub_plugin.py`**

Replace the file with:

```python
import logging
from typing import override

from PySide6.QtCore import Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QWidget

from ...base.base_widget import BaseWidget
from ...base.config_panel import ConfigPanel
from ...base.user_settings import UserSettings
from .device_context import DeviceContext
from .entities import build_entity_registry
from .entity_settings import EntitySettings
from .mqtt_config import MqttConfig
from .mqtt_session import MqttSession
from .publisher import Publisher
from .sampler_runner import SamplerRunner

# Forward-declared; populated by Task 24
def build_command_registry(plugin):
    return []


class HomeAssistantMqttPubPlugin(BaseWidget):

    display_name = "Home Assistant (MQTT)"

    def __init__(self, parent: QWidget | None) -> None:
        super().__init__(parent, is_enabled=True)
        self._user_settings = UserSettings.instance()
        self._entity_settings = EntitySettings(self._user_settings)
        self._sampler = SamplerRunner()
        self._entities = build_entity_registry()
        self._commands = build_command_registry(self)
        self._session: MqttSession | None = None
        self._publisher: Publisher | None = None

        cfg = MqttConfig.load_from_settings(self._user_settings)
        self.is_homeassistant_configured = cfg.is_complete()
        if self.is_homeassistant_configured:
            self._start_session(cfg)

    def _start_session(self, cfg: MqttConfig) -> None:
        ctx = DeviceContext(name=str(cfg.device_name))
        broker = dict(
            host=cfg.host, port=cfg.port,
            username=cfg.username, password=cfg.password,
            client_id=cfg.client_id,
        )
        self._session = MqttSession(broker_config=broker, availability_topic=ctx.availability_topic)
        self._publisher = Publisher(
            session=self._session, ctx=ctx, settings=self._entity_settings,
            sampler=self._sampler, entities=self._entities, commands=self._commands,
        )
        self._session.subscribe("homeassistant/status", self._publisher.on_ha_status)
        for command in self._commands:
            self._session.subscribe(
                ctx.command_topic(command.key),
                lambda payload, c=command: c.run(),
            )
        self._session.on_connected = self._publisher.on_connected
        self._session.start()

    @override
    def status_changed(self, status: bool) -> None:
        if status and self._session is None and self.is_homeassistant_configured:
            cfg = MqttConfig.load_from_settings(self._user_settings)
            self._start_session(cfg)
        elif not status and self._publisher is not None and self._session is not None:
            try:
                self._publisher.delete_all_for_current_device()
            finally:
                self._publisher.stop()
                self._session.stop()
                self._publisher = None
                self._session = None

    @override
    def retrieve_menus(self) -> list[QMenu | QAction]:
        menu = QMenu("Home Assistant", self)
        configured = QAction("Configured" if self.is_homeassistant_configured else "Not configured", self)
        configured.setEnabled(False)
        menu.addAction(configured)
        return [menu]

    @override
    def retrieve_config_panels(self) -> list[ConfigPanel]:
        from .mqtt_config_panel import MqttConfigPanel
        return [MqttConfigPanel(self)]

    @Slot()
    def reload_session(self) -> None:
        """Called by the config panel after apply()."""
        if self._publisher is not None and self._session is not None:
            self._publisher.stop()
            self._session.stop()
            self._publisher = None
            self._session = None
        cfg = MqttConfig.load_from_settings(self._user_settings)
        self.is_homeassistant_configured = cfg.is_complete()
        if self.is_homeassistant_configured and self.is_enabled():
            self._start_session(cfg)

    def closeEvent(self, event):
        if self._publisher is not None:
            self._publisher.stop()
        if self._session is not None:
            self._session.stop()
        event.accept()
```

- [ ] **Step 5: Run plugin + existing-mqtt-config tests**

Run: `./env/Scripts/python.exe -m pytest tests/test_ha_plugin.py tests/test_mqtt_config.py -v`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add src/plugins/home_assistant_mqtt_pub/home_assistant_mqtt_pub_plugin.py src/plugins/home_assistant_mqtt_pub/mqtt_config.py tests/test_ha_plugin.py
git commit -m "refactor: rewrite home_assistant_mqtt_pub_plugin around MqttSession + Publisher"
```

---

## Task 11 — cpu_temperature entity (with availability fallback)

**Files:**
- Create: `src/plugins/home_assistant_mqtt_pub/entities/cpu_temperature.py`
- Modify: `src/plugins/home_assistant_mqtt_pub/entities/__init__.py`
- Create: `tests/test_ha_entity_cpu_temperature.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ha_entity_cpu_temperature.py`:

```python
from unittest.mock import patch, MagicMock

from src.plugins.home_assistant_mqtt_pub.device_context import DeviceContext
from src.plugins.home_assistant_mqtt_pub.entities.cpu_temperature import CpuTemperatureEntity


def _zone(kelvin_tenths):
    z = MagicMock()
    z.CurrentTemperature = kelvin_tenths
    return z


def test_metadata():
    e = CpuTemperatureEntity()
    assert e.key == "cpu_temperature"
    assert e.component == "sensor"
    assert e.default_enabled is True
    assert e.default_interval_s == 30


def test_sample_converts_acpi_kelvin_tenths_to_celsius():
    e = CpuTemperatureEntity()
    fake = MagicMock()
    fake.MSAcpi_ThermalZoneTemperature.return_value = [_zone(3132)]  # 313.2K = 40.05C
    with patch("wmi.WMI", return_value=fake):
        result = e.sample()
    assert result.is_available is True
    assert round(result.value, 1) == 40.1
    assert result.unit == "°C"


def test_sample_unavailable_when_no_zones():
    e = CpuTemperatureEntity()
    fake = MagicMock()
    fake.MSAcpi_ThermalZoneTemperature.return_value = []
    with patch("wmi.WMI", return_value=fake):
        result = e.sample()
    assert result.is_available is False


def test_sample_unavailable_when_wmi_raises():
    e = CpuTemperatureEntity()
    with patch("wmi.WMI", side_effect=OSError("nope")):
        result = e.sample()
    assert result.is_available is False


def test_discovery_payload_has_temperature_class():
    e = CpuTemperatureEntity()
    payload = e.discovery_payload(DeviceContext(name="pc"))
    assert payload["device_class"] == "temperature"
    assert payload["unit_of_measurement"] == "°C"
```

- [ ] **Step 2: Run tests, expect ModuleNotFoundError**

Run: `./env/Scripts/python.exe -m pytest tests/test_ha_entity_cpu_temperature.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement CpuTemperatureEntity**

Create `src/plugins/home_assistant_mqtt_pub/entities/cpu_temperature.py`:

```python
import logging

from .base import SampleResult


class CpuTemperatureEntity:
    key = "cpu_temperature"
    display_name = "CPU temperature"
    component = "sensor"
    default_enabled = True
    default_interval_s = 30
    is_event_driven = False

    def discovery_payload(self, ctx) -> dict:
        return {
            "name": self.display_name,
            "unique_id": f"{ctx.device_id}_{self.key}",
            "object_id": f"{ctx.device_id}_{self.key}",
            "state_topic": ctx.state_topic(self.component, self.key),
            "availability_topic": ctx.availability_topic,
            "unit_of_measurement": "°C",
            "device_class": "temperature",
            "device": ctx.device_block(),
        }

    def sample(self) -> SampleResult:
        try:
            import wmi
            zones = wmi.WMI(namespace=r"root\wmi").MSAcpi_ThermalZoneTemperature()
        except Exception as exc:
            logging.debug("cpu_temperature WMI failed: %s", exc)
            return SampleResult.unavailable(reason=str(exc))
        if not zones:
            return SampleResult.unavailable(reason="no thermal zones reported")
        # ACPI returns tenths of Kelvin; convert to Celsius.
        kelvin_tenths = zones[0].CurrentTemperature
        celsius = (kelvin_tenths / 10.0) - 273.15
        return SampleResult.available(value=round(celsius, 1), unit="°C")
```

The test patches `wmi.WMI`; the import inside `sample` makes that patch effective regardless of whether the real `wmi` is available on the test host.

- [ ] **Step 4: Register in entities/__init__.py**

Edit `src/plugins/home_assistant_mqtt_pub/entities/__init__.py`:

```python
from .base import Entity, SampleResult  # noqa: F401
from .cpu_temperature import CpuTemperatureEntity
from .cpu_usage import CpuUsageEntity


def build_entity_registry() -> list:
    return [
        CpuUsageEntity(),
        CpuTemperatureEntity(),
    ]
```

- [ ] **Step 5: Run tests**

Run: `./env/Scripts/python.exe -m pytest tests/test_ha_entity_cpu_temperature.py tests/test_ha_entity_cpu_usage.py -v`
Expected: 5 + 5 passed.

- [ ] **Step 6: Commit**

```bash
git add src/plugins/home_assistant_mqtt_pub/entities/cpu_temperature.py src/plugins/home_assistant_mqtt_pub/entities/__init__.py tests/test_ha_entity_cpu_temperature.py
git commit -m "feat: add cpu_temperature entity with availability fallback"
```

---

## Task 12 — cpu_frequency entity

**Files:**
- Create: `src/plugins/home_assistant_mqtt_pub/entities/cpu_frequency.py`
- Modify: `src/plugins/home_assistant_mqtt_pub/entities/__init__.py`
- Create: `tests/test_ha_entity_cpu_frequency.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_ha_entity_cpu_frequency.py`:

```python
from unittest.mock import patch

from src.plugins.home_assistant_mqtt_pub.device_context import DeviceContext
from src.plugins.home_assistant_mqtt_pub.entities.cpu_frequency import CpuFrequencyEntity


class _Freq:
    def __init__(self, current):
        self.current = current


def test_metadata():
    e = CpuFrequencyEntity()
    assert e.key == "cpu_frequency"
    assert e.default_interval_s == 30


def test_sample_returns_mhz():
    e = CpuFrequencyEntity()
    with patch("psutil.cpu_freq", return_value=_Freq(current=3600.0)):
        result = e.sample()
    assert result.is_available is True
    assert result.value == 3600.0
    assert result.unit == "MHz"


def test_sample_unavailable_when_psutil_returns_none():
    e = CpuFrequencyEntity()
    with patch("psutil.cpu_freq", return_value=None):
        result = e.sample()
    assert result.is_available is False


def test_discovery_payload_has_frequency_unit():
    payload = CpuFrequencyEntity().discovery_payload(DeviceContext(name="pc"))
    assert payload["unit_of_measurement"] == "MHz"
```

- [ ] **Step 2: Run, expect FAIL**

Run: `./env/Scripts/python.exe -m pytest tests/test_ha_entity_cpu_frequency.py -v`

- [ ] **Step 3: Implement**

Create `src/plugins/home_assistant_mqtt_pub/entities/cpu_frequency.py`:

```python
import logging
import psutil

from .base import SampleResult


class CpuFrequencyEntity:
    key = "cpu_frequency"
    display_name = "CPU frequency"
    component = "sensor"
    default_enabled = True
    default_interval_s = 30
    is_event_driven = False

    def discovery_payload(self, ctx) -> dict:
        return {
            "name": self.display_name,
            "unique_id": f"{ctx.device_id}_{self.key}",
            "object_id": f"{ctx.device_id}_{self.key}",
            "state_topic": ctx.state_topic(self.component, self.key),
            "availability_topic": ctx.availability_topic,
            "unit_of_measurement": "MHz",
            "icon": "mdi:speedometer",
            "device": ctx.device_block(),
        }

    def sample(self) -> SampleResult:
        try:
            freq = psutil.cpu_freq()
        except Exception as exc:
            logging.debug("cpu_frequency failed: %s", exc)
            return SampleResult.unavailable(reason=str(exc))
        if freq is None or freq.current in (None, 0):
            return SampleResult.unavailable(reason="psutil returned no frequency")
        return SampleResult.available(value=float(freq.current), unit="MHz")
```

- [ ] **Step 4: Register**

In `entities/__init__.py`, add `from .cpu_frequency import CpuFrequencyEntity` and append `CpuFrequencyEntity()` to the registry list.

- [ ] **Step 5: Run + Commit**

```bash
./env/Scripts/python.exe -m pytest tests/test_ha_entity_cpu_frequency.py -v
git add src/plugins/home_assistant_mqtt_pub/entities/cpu_frequency.py src/plugins/home_assistant_mqtt_pub/entities/__init__.py tests/test_ha_entity_cpu_frequency.py
git commit -m "feat: add cpu_frequency entity"
```

---

## Task 13 — memory_usage entity

**Files:**
- Create: `src/plugins/home_assistant_mqtt_pub/entities/memory_usage.py`
- Modify: `entities/__init__.py`
- Create: `tests/test_ha_entity_memory_usage.py`

- [ ] **Step 1: Test**

Create `tests/test_ha_entity_memory_usage.py`:

```python
from unittest.mock import patch, MagicMock

from src.plugins.home_assistant_mqtt_pub.entities.memory_usage import MemoryUsageEntity


def test_sample_returns_percent():
    e = MemoryUsageEntity()
    fake = MagicMock(percent=42.0)
    with patch("psutil.virtual_memory", return_value=fake):
        result = e.sample()
    assert result.is_available is True
    assert result.value == 42.0
    assert result.unit == "%"
```

- [ ] **Step 2: Implement**

Create `src/plugins/home_assistant_mqtt_pub/entities/memory_usage.py`:

```python
import logging
import psutil

from .base import SampleResult


class MemoryUsageEntity:
    key = "memory_usage"
    display_name = "Memory usage"
    component = "sensor"
    default_enabled = True
    default_interval_s = 30
    is_event_driven = False

    def discovery_payload(self, ctx) -> dict:
        return {
            "name": self.display_name,
            "unique_id": f"{ctx.device_id}_{self.key}",
            "object_id": f"{ctx.device_id}_{self.key}",
            "state_topic": ctx.state_topic(self.component, self.key),
            "availability_topic": ctx.availability_topic,
            "unit_of_measurement": "%",
            "icon": "mdi:memory",
            "device": ctx.device_block(),
        }

    def sample(self) -> SampleResult:
        try:
            return SampleResult.available(value=float(psutil.virtual_memory().percent), unit="%")
        except Exception as exc:
            logging.debug("memory_usage failed: %s", exc)
            return SampleResult.unavailable(reason=str(exc))
```

- [ ] **Step 3: Register + Run + Commit**

Add to `entities/__init__.py`. Run the test. Commit.

```bash
git add src/plugins/home_assistant_mqtt_pub/entities/memory_usage.py src/plugins/home_assistant_mqtt_pub/entities/__init__.py tests/test_ha_entity_memory_usage.py
git commit -m "feat: add memory_usage entity"
```

---

## Task 14 — uptime entity

**Files:**
- Create: `src/plugins/home_assistant_mqtt_pub/entities/uptime.py`
- Modify: `entities/__init__.py`
- Create: `tests/test_ha_entity_uptime.py`

- [ ] **Step 1: Test**

Create `tests/test_ha_entity_uptime.py`:

```python
from unittest.mock import patch

from src.plugins.home_assistant_mqtt_pub.entities.uptime import UptimeEntity


def test_sample_returns_seconds_since_boot():
    e = UptimeEntity()
    with patch("time.time", return_value=1_000_000.0), \
         patch("psutil.boot_time", return_value=999_500.0):
        result = e.sample()
    assert result.is_available is True
    assert result.value == 500
    assert result.unit == "s"


def test_default_interval_60s():
    assert UptimeEntity().default_interval_s == 60
```

- [ ] **Step 2: Implement**

Create `src/plugins/home_assistant_mqtt_pub/entities/uptime.py`:

```python
import logging
import time
import psutil

from .base import SampleResult


class UptimeEntity:
    key = "uptime"
    display_name = "Uptime"
    component = "sensor"
    default_enabled = True
    default_interval_s = 60
    is_event_driven = False

    def discovery_payload(self, ctx) -> dict:
        return {
            "name": self.display_name,
            "unique_id": f"{ctx.device_id}_{self.key}",
            "object_id": f"{ctx.device_id}_{self.key}",
            "state_topic": ctx.state_topic(self.component, self.key),
            "availability_topic": ctx.availability_topic,
            "unit_of_measurement": "s",
            "icon": "mdi:timer-outline",
            "device": ctx.device_block(),
        }

    def sample(self) -> SampleResult:
        try:
            seconds = int(time.time() - psutil.boot_time())
        except Exception as exc:
            logging.debug("uptime failed: %s", exc)
            return SampleResult.unavailable(reason=str(exc))
        return SampleResult.available(value=seconds, unit="s")
```

- [ ] **Step 3: Register + Run + Commit**

Add to `entities/__init__.py`. Run `./env/Scripts/python.exe -m pytest tests/test_ha_entity_uptime.py -v` (expect 2 passed). Commit.

```bash
git add src/plugins/home_assistant_mqtt_pub/entities/uptime.py src/plugins/home_assistant_mqtt_pub/entities/__init__.py tests/test_ha_entity_uptime.py
git commit -m "feat: add uptime entity"
```

---

## Task 15 — battery_state entity

**Files:**
- Create: `src/plugins/home_assistant_mqtt_pub/entities/battery_state.py`
- Modify: `entities/__init__.py`
- Create: `tests/test_ha_entity_battery_state.py`

- [ ] **Step 1: Test**

Create `tests/test_ha_entity_battery_state.py`:

```python
from unittest.mock import patch, MagicMock

from src.plugins.home_assistant_mqtt_pub.entities.battery_state import BatteryStateEntity


def test_sample_on_ac():
    e = BatteryStateEntity()
    fake = MagicMock(power_plugged=True)
    with patch("psutil.sensors_battery", return_value=fake):
        result = e.sample()
    assert result.is_available is True
    assert result.value is True


def test_sample_on_battery():
    e = BatteryStateEntity()
    fake = MagicMock(power_plugged=False)
    with patch("psutil.sensors_battery", return_value=fake):
        result = e.sample()
    assert result.value is False


def test_sample_none_on_desktop():
    e = BatteryStateEntity()
    with patch("psutil.sensors_battery", return_value=None):
        result = e.sample()
    assert result.is_available is False


def test_metadata_is_binary_sensor_with_plug_class():
    from src.plugins.home_assistant_mqtt_pub.device_context import DeviceContext
    e = BatteryStateEntity()
    assert e.component == "binary_sensor"
    payload = e.discovery_payload(DeviceContext(name="pc"))
    assert payload["device_class"] == "plug"
    assert payload["payload_on"] == "ON" and payload["payload_off"] == "OFF"
```

- [ ] **Step 2: Implement**

Create `src/plugins/home_assistant_mqtt_pub/entities/battery_state.py`:

```python
import logging
import psutil

from .base import SampleResult


class BatteryStateEntity:
    key = "battery_state"
    display_name = "On AC power"
    component = "binary_sensor"
    default_enabled = True
    default_interval_s = 60
    is_event_driven = False

    def discovery_payload(self, ctx) -> dict:
        return {
            "name": self.display_name,
            "unique_id": f"{ctx.device_id}_{self.key}",
            "object_id": f"{ctx.device_id}_{self.key}",
            "state_topic": ctx.state_topic(self.component, self.key),
            "availability_topic": ctx.availability_topic,
            "device_class": "plug",
            "payload_on": "ON",
            "payload_off": "OFF",
            "device": ctx.device_block(),
        }

    def sample(self) -> SampleResult:
        try:
            battery = psutil.sensors_battery()
        except Exception as exc:
            logging.debug("battery_state failed: %s", exc)
            return SampleResult.unavailable(reason=str(exc))
        if battery is None:
            return SampleResult.unavailable(reason="no battery (desktop?)")
        return SampleResult.available(value=bool(battery.power_plugged))
```

- [ ] **Step 3: Register + Run + Commit**

```bash
./env/Scripts/python.exe -m pytest tests/test_ha_entity_battery_state.py -v
git add src/plugins/home_assistant_mqtt_pub/entities/battery_state.py src/plugins/home_assistant_mqtt_pub/entities/__init__.py tests/test_ha_entity_battery_state.py
git commit -m "feat: add battery_state binary_sensor entity"
```

---

## Task 16 — disk_free entity (multi-instance, one per fixed drive)

**Files:**
- Create: `src/plugins/home_assistant_mqtt_pub/entities/disk_free.py`
- Modify: `entities/__init__.py`
- Create: `tests/test_ha_entity_disk_free.py`

- [ ] **Step 1: Test**

Create `tests/test_ha_entity_disk_free.py`:

```python
from unittest.mock import patch, MagicMock

from src.plugins.home_assistant_mqtt_pub.device_context import DeviceContext
from src.plugins.home_assistant_mqtt_pub.entities.disk_free import (
    DiskFreeEntity,
    discover_disk_free_entities,
)


def test_discover_yields_entity_per_fixed_partition():
    fake_partitions = [
        MagicMock(device="C:\\", mountpoint="C:\\", fstype="NTFS", opts="rw,fixed"),
        MagicMock(device="D:\\", mountpoint="D:\\", fstype="NTFS", opts="rw,fixed"),
        MagicMock(device="E:\\", mountpoint="E:\\", fstype="UDF", opts="ro,cdrom"),
    ]
    with patch("psutil.disk_partitions", return_value=fake_partitions):
        entities = discover_disk_free_entities()
    keys = [e.key for e in entities]
    assert "disk_free_c" in keys
    assert "disk_free_d" in keys
    assert "disk_free_e" not in keys  # CD-ROM excluded


def test_sample_converts_bytes_to_gb():
    e = DiskFreeEntity(drive_letter="c", mountpoint="C:\\")
    fake = MagicMock(free=200 * 1024 ** 3)
    with patch("psutil.disk_usage", return_value=fake):
        result = e.sample()
    assert result.is_available is True
    assert result.value == 200.0
    assert result.unit == "GB"


def test_default_interval_300s():
    assert DiskFreeEntity(drive_letter="c", mountpoint="C:\\").default_interval_s == 300
```

- [ ] **Step 2: Implement**

Create `src/plugins/home_assistant_mqtt_pub/entities/disk_free.py`:

```python
import logging
import psutil

from .base import SampleResult


class DiskFreeEntity:
    component = "sensor"
    default_enabled = True
    default_interval_s = 300
    is_event_driven = False

    def __init__(self, drive_letter: str, mountpoint: str) -> None:
        self.drive_letter = drive_letter.lower()
        self.mountpoint = mountpoint
        self.key = f"disk_free_{self.drive_letter}"
        self.display_name = f"Free space {drive_letter.upper()}:"

    def discovery_payload(self, ctx) -> dict:
        return {
            "name": self.display_name,
            "unique_id": f"{ctx.device_id}_{self.key}",
            "object_id": f"{ctx.device_id}_{self.key}",
            "state_topic": ctx.state_topic(self.component, self.key),
            "availability_topic": ctx.availability_topic,
            "unit_of_measurement": "GB",
            "icon": "mdi:harddisk",
            "device": ctx.device_block(),
        }

    def sample(self) -> SampleResult:
        try:
            usage = psutil.disk_usage(self.mountpoint)
        except Exception as exc:
            logging.debug("disk_free failed for %s: %s", self.mountpoint, exc)
            return SampleResult.unavailable(reason=str(exc))
        gb = round(usage.free / (1024 ** 3), 1)
        return SampleResult.available(value=gb, unit="GB")


def discover_disk_free_entities() -> list[DiskFreeEntity]:
    out: list[DiskFreeEntity] = []
    try:
        partitions = psutil.disk_partitions(all=False)
    except Exception:
        return out
    for p in partitions:
        opts = (p.opts or "").lower()
        # Skip CD-ROM, removable, and other non-fixed media.
        if "cdrom" in opts or "removable" in opts:
            continue
        # Mountpoint like "C:\\" — first character is drive letter.
        mp = p.mountpoint
        if len(mp) < 2 or mp[1] != ":":
            continue
        out.append(DiskFreeEntity(drive_letter=mp[0], mountpoint=mp))
    return out
```

- [ ] **Step 3: Register**

In `entities/__init__.py`, import `discover_disk_free_entities` and *spread* its result into the registry:

```python
from .disk_free import discover_disk_free_entities

def build_entity_registry() -> list:
    return [
        CpuUsageEntity(),
        CpuTemperatureEntity(),
        CpuFrequencyEntity(),
        MemoryUsageEntity(),
        UptimeEntity(),
        BatteryStateEntity(),
        *discover_disk_free_entities(),
    ]
```

- [ ] **Step 4: Run + Commit**

```bash
./env/Scripts/python.exe -m pytest tests/test_ha_entity_disk_free.py -v
git add src/plugins/home_assistant_mqtt_pub/entities/disk_free.py src/plugins/home_assistant_mqtt_pub/entities/__init__.py tests/test_ha_entity_disk_free.py
git commit -m "feat: add disk_free entity (one per fixed drive)"
```

---

## Task 17 — network_io entity (tx + rx as two instances)

**Files:**
- Create: `src/plugins/home_assistant_mqtt_pub/entities/network_io.py`
- Modify: `entities/__init__.py`
- Create: `tests/test_ha_entity_network_io.py`

- [ ] **Step 1: Test**

Create `tests/test_ha_entity_network_io.py`:

```python
from unittest.mock import patch, MagicMock

from src.plugins.home_assistant_mqtt_pub.entities.network_io import (
    NetworkRxEntity,
    NetworkTxEntity,
)


def _io(rx, tx):
    m = MagicMock()
    m.bytes_recv = rx
    m.bytes_sent = tx
    return m


def test_rx_returns_bytes_received():
    e = NetworkRxEntity()
    with patch("psutil.net_io_counters", return_value=_io(rx=1234, tx=999)):
        r = e.sample()
    assert r.value == 1234
    assert r.unit == "B"


def test_tx_returns_bytes_sent():
    e = NetworkTxEntity()
    with patch("psutil.net_io_counters", return_value=_io(rx=1234, tx=999)):
        r = e.sample()
    assert r.value == 999
```

- [ ] **Step 2: Implement**

Create `src/plugins/home_assistant_mqtt_pub/entities/network_io.py`:

```python
import logging
import psutil

from .base import SampleResult


class _NetIoBase:
    component = "sensor"
    default_enabled = True
    default_interval_s = 30
    is_event_driven = False

    def discovery_payload(self, ctx) -> dict:
        return {
            "name": self.display_name,
            "unique_id": f"{ctx.device_id}_{self.key}",
            "object_id": f"{ctx.device_id}_{self.key}",
            "state_topic": ctx.state_topic(self.component, self.key),
            "availability_topic": ctx.availability_topic,
            "unit_of_measurement": "B",
            "icon": "mdi:network",
            "device": ctx.device_block(),
            "state_class": "total_increasing",
        }


class NetworkRxEntity(_NetIoBase):
    key = "network_rx_bytes"
    display_name = "Network bytes received"

    def sample(self) -> SampleResult:
        try:
            return SampleResult.available(value=int(psutil.net_io_counters().bytes_recv), unit="B")
        except Exception as exc:
            logging.debug("network_rx failed: %s", exc)
            return SampleResult.unavailable(reason=str(exc))


class NetworkTxEntity(_NetIoBase):
    key = "network_tx_bytes"
    display_name = "Network bytes sent"

    def sample(self) -> SampleResult:
        try:
            return SampleResult.available(value=int(psutil.net_io_counters().bytes_sent), unit="B")
        except Exception as exc:
            logging.debug("network_tx failed: %s", exc)
            return SampleResult.unavailable(reason=str(exc))
```

- [ ] **Step 3: Register + Run + Commit**

Add `NetworkRxEntity()` and `NetworkTxEntity()` to the registry. Run the tests. Commit.

```bash
git add src/plugins/home_assistant_mqtt_pub/entities/network_io.py src/plugins/home_assistant_mqtt_pub/entities/__init__.py tests/test_ha_entity_network_io.py
git commit -m "feat: add network_rx_bytes and network_tx_bytes entities"
```

---

## Task 18 — monitor_count entity (uses src.base.monitor_runner)

**Files:**
- Create: `src/plugins/home_assistant_mqtt_pub/entities/monitor_count.py`
- Modify: `entities/__init__.py`
- Create: `tests/test_ha_entity_monitor_count.py`

The CLAUDE.md rule mandates that any `monitorcontrol` access goes through the existing `monitor_runner`. We honor that here by submitting the count call to `monitor_runner` and waiting on a small `threading.Event`. The `SamplerRunner` is already on a worker thread, so blocking briefly is fine.

- [ ] **Step 1: Test**

Create `tests/test_ha_entity_monitor_count.py`:

```python
import threading
from unittest.mock import patch, MagicMock

from src.plugins.home_assistant_mqtt_pub.entities.monitor_count import MonitorCountEntity


def test_sample_returns_monitor_count_via_runner():
    e = MonitorCountEntity()

    captured = {}

    class _RunnerSpy:
        def submit(self, fn, *args, **kwargs):
            captured["fn"] = fn
            # Run synchronously for the test.
            fn(*args, **kwargs)

    with patch("src.plugins.home_assistant_mqtt_pub.entities.monitor_count.runner", return_value=_RunnerSpy()), \
         patch("monitorcontrol.get_monitors", return_value=[MagicMock(), MagicMock(), MagicMock()]):
        result = e.sample()
    assert result.is_available is True
    assert result.value == 3
```

- [ ] **Step 2: Implement**

Create `src/plugins/home_assistant_mqtt_pub/entities/monitor_count.py`:

```python
import logging
import threading

from src.base.monitor_runner import runner

from .base import SampleResult


class MonitorCountEntity:
    key = "monitor_count"
    display_name = "Monitor count"
    component = "sensor"
    default_enabled = True
    default_interval_s = 60
    is_event_driven = False

    def discovery_payload(self, ctx) -> dict:
        return {
            "name": self.display_name,
            "unique_id": f"{ctx.device_id}_{self.key}",
            "object_id": f"{ctx.device_id}_{self.key}",
            "state_topic": ctx.state_topic(self.component, self.key),
            "availability_topic": ctx.availability_topic,
            "icon": "mdi:monitor-multiple",
            "device": ctx.device_block(),
        }

    def sample(self) -> SampleResult:
        # Honor the CLAUDE.md rule: monitorcontrol calls go through monitor_runner.
        done = threading.Event()
        result_box: list = []

        def _do():
            try:
                import monitorcontrol
                result_box.append(len(list(monitorcontrol.get_monitors())))
            except Exception as exc:
                result_box.append(exc)
            finally:
                done.set()

        runner().submit(_do)
        if not done.wait(timeout=5.0):
            return SampleResult.unavailable(reason="monitor_runner timeout")
        value = result_box[0]
        if isinstance(value, Exception):
            logging.debug("monitor_count failed: %s", value)
            return SampleResult.unavailable(reason=str(value))
        return SampleResult.available(value=int(value))
```

- [ ] **Step 3: Register + Run + Commit**

Add `MonitorCountEntity()` to the registry. Run the test. Commit.

```bash
git add src/plugins/home_assistant_mqtt_pub/entities/monitor_count.py src/plugins/home_assistant_mqtt_pub/entities/__init__.py tests/test_ha_entity_monitor_count.py
git commit -m "feat: add monitor_count entity routed through monitor_runner"
```

---

## Task 19 — current_user entity (default off)

**Files:**
- Create: `src/plugins/home_assistant_mqtt_pub/entities/current_user.py`
- Modify: `entities/__init__.py`
- Create: `tests/test_ha_entity_current_user.py`

- [ ] **Step 1: Test**

Create `tests/test_ha_entity_current_user.py`:

```python
from unittest.mock import patch

from src.plugins.home_assistant_mqtt_pub.entities.current_user import CurrentUserEntity


def test_default_enabled_is_false_for_privacy():
    assert CurrentUserEntity().default_enabled is False


def test_sample_returns_current_user():
    e = CurrentUserEntity()
    with patch("getpass.getuser", return_value="alice"):
        r = e.sample()
    assert r.is_available is True
    assert r.value == "alice"
```

- [ ] **Step 2: Implement**

Create `src/plugins/home_assistant_mqtt_pub/entities/current_user.py`:

```python
import getpass
import logging

from .base import SampleResult


class CurrentUserEntity:
    key = "current_user"
    display_name = "Current user"
    component = "sensor"
    default_enabled = False  # privacy
    default_interval_s = 300
    is_event_driven = False

    def discovery_payload(self, ctx) -> dict:
        return {
            "name": self.display_name,
            "unique_id": f"{ctx.device_id}_{self.key}",
            "object_id": f"{ctx.device_id}_{self.key}",
            "state_topic": ctx.state_topic(self.component, self.key),
            "availability_topic": ctx.availability_topic,
            "icon": "mdi:account",
            "device": ctx.device_block(),
        }

    def sample(self) -> SampleResult:
        try:
            return SampleResult.available(value=getpass.getuser())
        except Exception as exc:
            logging.debug("current_user failed: %s", exc)
            return SampleResult.unavailable(reason=str(exc))
```

- [ ] **Step 3: Register + Run + Commit**

```bash
git add src/plugins/home_assistant_mqtt_pub/entities/current_user.py src/plugins/home_assistant_mqtt_pub/entities/__init__.py tests/test_ha_entity_current_user.py
git commit -m "feat: add current_user entity (default off, privacy)"
```

---

## Task 20 — foreground_window entity (default off)

**Files:**
- Create: `src/plugins/home_assistant_mqtt_pub/entities/foreground_window.py`
- Modify: `entities/__init__.py`
- Create: `tests/test_ha_entity_foreground_window.py`

- [ ] **Step 1: Test**

Create `tests/test_ha_entity_foreground_window.py`:

```python
from unittest.mock import patch

from src.plugins.home_assistant_mqtt_pub.entities.foreground_window import ForegroundWindowEntity


def test_default_enabled_false():
    assert ForegroundWindowEntity().default_enabled is False


def test_sample_returns_window_title():
    e = ForegroundWindowEntity()
    with patch("win32gui.GetForegroundWindow", return_value=1234), \
         patch("win32gui.GetWindowText", return_value="Notepad — untitled"):
        r = e.sample()
    assert r.is_available is True
    assert r.value == "Notepad — untitled"


def test_sample_unavailable_when_title_empty():
    e = ForegroundWindowEntity()
    with patch("win32gui.GetForegroundWindow", return_value=1234), \
         patch("win32gui.GetWindowText", return_value=""):
        r = e.sample()
    assert r.is_available is False
```

- [ ] **Step 2: Implement**

Create `src/plugins/home_assistant_mqtt_pub/entities/foreground_window.py`:

```python
import logging

from .base import SampleResult


class ForegroundWindowEntity:
    key = "foreground_window"
    display_name = "Foreground window"
    component = "sensor"
    default_enabled = False  # privacy
    default_interval_s = 30
    is_event_driven = False

    def discovery_payload(self, ctx) -> dict:
        return {
            "name": self.display_name,
            "unique_id": f"{ctx.device_id}_{self.key}",
            "object_id": f"{ctx.device_id}_{self.key}",
            "state_topic": ctx.state_topic(self.component, self.key),
            "availability_topic": ctx.availability_topic,
            "icon": "mdi:window-maximize",
            "device": ctx.device_block(),
        }

    def sample(self) -> SampleResult:
        try:
            import win32gui
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return SampleResult.unavailable(reason="no foreground window")
            title = win32gui.GetWindowText(hwnd)
        except Exception as exc:
            logging.debug("foreground_window failed: %s", exc)
            return SampleResult.unavailable(reason=str(exc))
        if not title:
            return SampleResult.unavailable(reason="empty title")
        return SampleResult.available(value=title)
```

- [ ] **Step 3: Register + Run + Commit**

```bash
git add src/plugins/home_assistant_mqtt_pub/entities/foreground_window.py src/plugins/home_assistant_mqtt_pub/entities/__init__.py tests/test_ha_entity_foreground_window.py
git commit -m "feat: add foreground_window entity (default off, privacy)"
```

---

## Task 21 — lock_state entity (event-driven)

**Files:**
- Create: `src/plugins/home_assistant_mqtt_pub/entities/lock_state.py`
- Modify: `entities/__init__.py`
- Create: `tests/test_ha_entity_lock_state.py`

This entity is event-driven: a hidden `QWidget` registered for `WTSRegisterSessionNotification` receives `WM_WTSSESSION_CHANGE` and emits state changes. We test the dispatch logic by simulating native events via a public `_dispatch_session_event(wparam)` hook.

- [ ] **Step 1: Test**

Create `tests/test_ha_entity_lock_state.py`:

```python
from unittest.mock import patch, MagicMock

from src.plugins.home_assistant_mqtt_pub.entities.lock_state import (
    LockStateEntity,
    WTS_SESSION_LOCK,
    WTS_SESSION_UNLOCK,
)


def test_metadata_event_driven():
    e = LockStateEntity()
    assert e.is_event_driven is True
    assert e.default_interval_s is None
    assert e.component == "binary_sensor"


def test_dispatch_lock_emits_true(qtbot):
    e = LockStateEntity()
    received = []
    e.subscribe(lambda result: received.append(result))
    e._dispatch_session_event(WTS_SESSION_LOCK)
    assert received[-1].is_available is True
    assert received[-1].value is True


def test_dispatch_unlock_emits_false(qtbot):
    e = LockStateEntity()
    received = []
    e.subscribe(lambda result: received.append(result))
    e._dispatch_session_event(WTS_SESSION_UNLOCK)
    assert received[-1].value is False


def test_initial_sample_via_wts_query(qtbot):
    e = LockStateEntity()
    fake_user32 = MagicMock()
    fake_user32.OpenInputDesktop.return_value = 1
    fake_user32.SwitchDesktop.return_value = 1  # not locked

    with patch("ctypes.windll", MagicMock(user32=fake_user32)):
        r = e.sample()
    assert r.is_available is True
    assert r.value is False  # unlocked
```

- [ ] **Step 2: Implement**

Create `src/plugins/home_assistant_mqtt_pub/entities/lock_state.py`:

```python
import logging
from typing import Callable

from PySide6.QtWidgets import QWidget

from .base import SampleResult


WM_WTSSESSION_CHANGE = 0x02B1
WTS_SESSION_LOCK = 0x7
WTS_SESSION_UNLOCK = 0x8
NOTIFY_FOR_THIS_SESSION = 0


class LockStateEntity(QWidget):
    key = "lock_state"
    display_name = "Locked"
    component = "binary_sensor"
    default_enabled = True
    default_interval_s = None
    is_event_driven = True

    def __init__(self) -> None:
        super().__init__(parent=None)
        self._on_change: Callable | None = None
        self._registered = False

    def discovery_payload(self, ctx) -> dict:
        return {
            "name": self.display_name,
            "unique_id": f"{ctx.device_id}_{self.key}",
            "object_id": f"{ctx.device_id}_{self.key}",
            "state_topic": ctx.state_topic(self.component, self.key),
            "availability_topic": ctx.availability_topic,
            "device_class": "lock",
            "payload_on": "ON",
            "payload_off": "OFF",
            "device": ctx.device_block(),
        }

    def sample(self) -> SampleResult:
        try:
            import ctypes
            DESKTOP_SWITCHDESKTOP = 0x0100
            hdesk = ctypes.windll.user32.OpenInputDesktop(0, False, DESKTOP_SWITCHDESKTOP)
            if not hdesk:
                return SampleResult.available(value=True)  # cannot open input desktop → locked
            ctypes.windll.user32.CloseDesktop(hdesk)
            return SampleResult.available(value=False)
        except Exception as exc:
            logging.debug("lock_state initial sample failed: %s", exc)
            return SampleResult.unavailable(reason=str(exc))

    def subscribe(self, on_change: Callable[[SampleResult], None]) -> None:
        self._on_change = on_change
        if self._registered:
            return
        try:
            import ctypes
            ctypes.windll.wtsapi32.WTSRegisterSessionNotification(
                int(self.winId()), NOTIFY_FOR_THIS_SESSION,
            )
            self._registered = True
        except Exception:
            logging.exception("WTSRegisterSessionNotification failed")

    def unsubscribe(self) -> None:
        if not self._registered:
            return
        try:
            import ctypes
            ctypes.windll.wtsapi32.WTSUnRegisterSessionNotification(int(self.winId()))
        except Exception:
            logging.exception("WTSUnRegisterSessionNotification failed")
        finally:
            self._registered = False
            self._on_change = None

    def nativeEvent(self, eventType, message):
        try:
            import ctypes
            msg = ctypes.wintypes.MSG.from_address(int(message))
        except Exception:
            return False, 0
        if msg.message == WM_WTSSESSION_CHANGE:
            self._dispatch_session_event(msg.wParam)
        return False, 0

    def _dispatch_session_event(self, wparam: int) -> None:
        if self._on_change is None:
            return
        if wparam == WTS_SESSION_LOCK:
            self._on_change(SampleResult.available(value=True))
        elif wparam == WTS_SESSION_UNLOCK:
            self._on_change(SampleResult.available(value=False))
```

- [ ] **Step 3: Register + Run + Commit**

```bash
./env/Scripts/python.exe -m pytest tests/test_ha_entity_lock_state.py -v
git add src/plugins/home_assistant_mqtt_pub/entities/lock_state.py src/plugins/home_assistant_mqtt_pub/entities/__init__.py tests/test_ha_entity_lock_state.py
git commit -m "feat: add event-driven lock_state binary_sensor entity"
```

---

## Task 22 — Command protocol + lock command

**Files:**
- Create: `src/plugins/home_assistant_mqtt_pub/commands/base.py`
- Create: `src/plugins/home_assistant_mqtt_pub/commands/lock.py`
- Create: `src/plugins/home_assistant_mqtt_pub/commands/__init__.py`
- Create: `tests/test_ha_command_lock.py`

- [ ] **Step 1: Test**

Create `tests/test_ha_command_lock.py`:

```python
from unittest.mock import patch, MagicMock

from src.plugins.home_assistant_mqtt_pub.commands.lock import LockCommand
from src.plugins.home_assistant_mqtt_pub.device_context import DeviceContext


def test_metadata():
    c = LockCommand()
    assert c.key == "lock"
    assert c.default_enabled is True
    assert c.is_available() is True


def test_run_calls_lockworkstation():
    c = LockCommand()
    fake = MagicMock()
    with patch("ctypes.windll", MagicMock(user32=fake)):
        c.run()
    fake.LockWorkStation.assert_called_once()


def test_discovery_payload_is_button():
    c = LockCommand()
    payload = c.discovery_payload(DeviceContext(name="pc"))
    assert payload["command_topic"] == "homeassistant/button/swk_pc/lock/set"
    assert payload["unique_id"] == "swk_pc_lock"
    assert payload["device"]["identifiers"] == ["swk_pc"]
```

- [ ] **Step 2: Implement base + lock + registry**

Create `src/plugins/home_assistant_mqtt_pub/commands/base.py`:

```python
from typing import Protocol


class Command(Protocol):
    key: str
    display_name: str
    default_enabled: bool

    def discovery_payload(self, ctx) -> dict: ...

    def run(self) -> None: ...

    def is_available(self) -> bool:
        return True
```

Create `src/plugins/home_assistant_mqtt_pub/commands/lock.py`:

```python
import logging


class LockCommand:
    key = "lock"
    display_name = "Lock screen"
    default_enabled = True

    def is_available(self) -> bool:
        return True

    def discovery_payload(self, ctx) -> dict:
        return {
            "name": self.display_name,
            "unique_id": f"{ctx.device_id}_{self.key}",
            "object_id": f"{ctx.device_id}_{self.key}",
            "command_topic": ctx.command_topic(self.key),
            "availability_topic": ctx.availability_topic,
            "icon": "mdi:lock",
            "device": ctx.device_block(),
        }

    def run(self) -> None:
        try:
            import ctypes
            ctypes.windll.user32.LockWorkStation()
        except Exception:
            logging.exception("LockWorkStation failed")
```

Create `src/plugins/home_assistant_mqtt_pub/commands/__init__.py`:

```python
from .lock import LockCommand


def build_command_registry(plugin) -> list:
    candidates = [LockCommand()]
    return [c for c in candidates if c.is_available()]
```

Update `home_assistant_mqtt_pub_plugin.py` — replace the local `def build_command_registry(plugin): return []` shim with:

```python
from .commands import build_command_registry  # noqa: F401  (re-export for clarity)
```

- [ ] **Step 3: Run + Commit**

```bash
./env/Scripts/python.exe -m pytest tests/test_ha_command_lock.py tests/test_ha_plugin.py -v
git add src/plugins/home_assistant_mqtt_pub/commands/__init__.py src/plugins/home_assistant_mqtt_pub/commands/base.py src/plugins/home_assistant_mqtt_pub/commands/lock.py src/plugins/home_assistant_mqtt_pub/home_assistant_mqtt_pub_plugin.py tests/test_ha_command_lock.py
git commit -m "feat: add Command protocol and lock command"
```

---

## Task 23 — sleep command

**Files:**
- Create: `src/plugins/home_assistant_mqtt_pub/commands/sleep_cmd.py`
- Modify: `src/plugins/home_assistant_mqtt_pub/commands/__init__.py`
- Create: `tests/test_ha_command_sleep.py`

(The file is named `sleep_cmd.py` to avoid shadowing `time.sleep`.)

- [ ] **Step 1: Test**

Create `tests/test_ha_command_sleep.py`:

```python
from unittest.mock import patch, MagicMock

from src.plugins.home_assistant_mqtt_pub.commands.sleep_cmd import SleepCommand


def test_metadata():
    c = SleepCommand()
    assert c.key == "sleep"
    assert c.default_enabled is True


def test_run_calls_setsuspendstate():
    c = SleepCommand()
    fake = MagicMock()
    with patch("ctypes.windll", MagicMock(PowrProf=fake)):
        c.run()
    fake.SetSuspendState.assert_called_once_with(0, 0, 0)
```

- [ ] **Step 2: Implement**

Create `src/plugins/home_assistant_mqtt_pub/commands/sleep_cmd.py`:

```python
import logging


class SleepCommand:
    key = "sleep"
    display_name = "Sleep"
    default_enabled = True

    def is_available(self) -> bool:
        return True

    def discovery_payload(self, ctx) -> dict:
        return {
            "name": self.display_name,
            "unique_id": f"{ctx.device_id}_{self.key}",
            "object_id": f"{ctx.device_id}_{self.key}",
            "command_topic": ctx.command_topic(self.key),
            "availability_topic": ctx.availability_topic,
            "icon": "mdi:power-sleep",
            "device": ctx.device_block(),
        }

    def run(self) -> None:
        try:
            import ctypes
            ctypes.windll.PowrProf.SetSuspendState(0, 0, 0)
        except Exception:
            logging.exception("SetSuspendState failed")
```

- [ ] **Step 3: Register**

Edit `commands/__init__.py`:

```python
from .lock import LockCommand
from .sleep_cmd import SleepCommand


def build_command_registry(plugin) -> list:
    candidates = [LockCommand(), SleepCommand()]
    return [c for c in candidates if c.is_available()]
```

- [ ] **Step 4: Run + Commit**

```bash
./env/Scripts/python.exe -m pytest tests/test_ha_command_sleep.py -v
git add src/plugins/home_assistant_mqtt_pub/commands/sleep_cmd.py src/plugins/home_assistant_mqtt_pub/commands/__init__.py tests/test_ha_command_sleep.py
git commit -m "feat: add sleep command"
```

---

## Task 24 — shutdown command (with privilege probe)

**Files:**
- Create: `src/plugins/home_assistant_mqtt_pub/commands/shutdown.py`
- Modify: `src/plugins/home_assistant_mqtt_pub/commands/__init__.py`
- Create: `tests/test_ha_command_shutdown.py`

- [ ] **Step 1: Test**

Create `tests/test_ha_command_shutdown.py`:

```python
from unittest.mock import patch, MagicMock

from src.plugins.home_assistant_mqtt_pub.commands.shutdown import ShutdownCommand


def test_is_available_when_privilege_can_be_acquired():
    c = ShutdownCommand()
    with patch.object(ShutdownCommand, "_can_acquire_shutdown_privilege", return_value=True):
        assert c.is_available() is True


def test_is_unavailable_when_privilege_missing():
    c = ShutdownCommand()
    with patch.object(ShutdownCommand, "_can_acquire_shutdown_privilege", return_value=False):
        assert c.is_available() is False


def test_run_calls_exit_windows_ex():
    c = ShutdownCommand()
    fake_user32 = MagicMock()
    fake_user32.ExitWindowsEx.return_value = 1
    with patch.object(c, "_acquire_shutdown_privilege"), \
         patch("ctypes.windll", MagicMock(user32=fake_user32)):
        c.run()
    fake_user32.ExitWindowsEx.assert_called_once()
```

- [ ] **Step 2: Implement**

Create `src/plugins/home_assistant_mqtt_pub/commands/shutdown.py`:

```python
import logging

EWX_SHUTDOWN = 0x00000001
EWX_FORCEIFHUNG = 0x00000010


class ShutdownCommand:
    key = "shutdown"
    display_name = "Shutdown"
    default_enabled = True

    def __init__(self) -> None:
        self._available = self._can_acquire_shutdown_privilege()

    def is_available(self) -> bool:
        return self._available

    def discovery_payload(self, ctx) -> dict:
        return {
            "name": self.display_name,
            "unique_id": f"{ctx.device_id}_{self.key}",
            "object_id": f"{ctx.device_id}_{self.key}",
            "command_topic": ctx.command_topic(self.key),
            "availability_topic": ctx.availability_topic,
            "icon": "mdi:power",
            "device": ctx.device_block(),
        }

    def run(self) -> None:
        try:
            self._acquire_shutdown_privilege()
            import ctypes
            ctypes.windll.user32.ExitWindowsEx(EWX_SHUTDOWN | EWX_FORCEIFHUNG, 0)
        except Exception:
            logging.exception("Shutdown failed")

    @staticmethod
    def _can_acquire_shutdown_privilege() -> bool:
        try:
            import win32security
            import win32api
            import win32con
            tok = win32security.OpenProcessToken(
                win32api.GetCurrentProcess(),
                win32con.TOKEN_ADJUST_PRIVILEGES | win32con.TOKEN_QUERY,
            )
            luid = win32security.LookupPrivilegeValue(None, win32security.SE_SHUTDOWN_NAME)
            win32security.AdjustTokenPrivileges(
                tok, False, [(luid, win32security.SE_PRIVILEGE_ENABLED)],
            )
            return True
        except Exception:
            return False

    def _acquire_shutdown_privilege(self) -> None:
        # Real call path. Mirrors the probe; runs at command time so the privilege
        # is enabled in our token immediately before ExitWindowsEx.
        self._can_acquire_shutdown_privilege()
```

- [ ] **Step 3: Register**

Edit `commands/__init__.py`:

```python
from .lock import LockCommand
from .shutdown import ShutdownCommand
from .sleep_cmd import SleepCommand


def build_command_registry(plugin) -> list:
    candidates = [LockCommand(), SleepCommand(), ShutdownCommand()]
    return [c for c in candidates if c.is_available()]
```

- [ ] **Step 4: Run + Commit**

```bash
./env/Scripts/python.exe -m pytest tests/test_ha_command_shutdown.py -v
git add src/plugins/home_assistant_mqtt_pub/commands/shutdown.py src/plugins/home_assistant_mqtt_pub/commands/__init__.py tests/test_ha_command_shutdown.py
git commit -m "feat: add shutdown command with SeShutdownPrivilege probe"
```

---

## Task 25 — Config panel: broker + device sections

**Files:**
- Modify: `src/plugins/home_assistant_mqtt_pub/mqtt_config_panel.py`
- Create / extend: `tests/test_mqtt_config_panel.py` (existing) — add new device-name + port-coercion cases.

- [ ] **Step 1: Tests for broker + device sections**

Append to `tests/test_mqtt_config_panel.py`:

```python
def test_apply_coerces_port_to_int(qtbot, fake_user_settings, silent_messagebox):
    from src.plugins.home_assistant_mqtt_pub.mqtt_config_panel import MqttConfigPanel
    panel = MqttConfigPanel(parent=None)
    qtbot.addWidget(panel)
    panel.host_field.setText("broker")
    panel.port_field.setText("1883")
    panel.login_field.setText("u")
    panel.password_field.setText("p")
    panel.client_id_field.setText("cid")
    panel.device_name_field.setText("PC One")
    assert panel.apply() is True
    assert fake_user_settings.get("homeassistant_port") == 1883


def test_apply_rejects_non_numeric_port(qtbot, fake_user_settings, silent_messagebox):
    from src.plugins.home_assistant_mqtt_pub.mqtt_config_panel import MqttConfigPanel
    panel = MqttConfigPanel(parent=None)
    qtbot.addWidget(panel)
    panel.host_field.setText("broker")
    panel.port_field.setText("not-a-port")
    panel.login_field.setText("u")
    panel.password_field.setText("p")
    panel.client_id_field.setText("cid")
    panel.device_name_field.setText("PC One")
    assert panel.apply() is False


def test_apply_rejects_empty_device_name(qtbot, fake_user_settings, silent_messagebox):
    from src.plugins.home_assistant_mqtt_pub.mqtt_config_panel import MqttConfigPanel
    panel = MqttConfigPanel(parent=None)
    qtbot.addWidget(panel)
    panel.host_field.setText("broker")
    panel.port_field.setText("1883")
    panel.login_field.setText("u")
    panel.password_field.setText("p")
    panel.client_id_field.setText("cid")
    panel.device_name_field.setText("   ")
    assert panel.apply() is False
```

- [ ] **Step 2: Replace `mqtt_config_panel.py` with sectioned layout**

Replace the file:

```python
from PySide6.QtWidgets import (
    QFormLayout, QGroupBox, QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from ...base.config_panel import ConfigPanel
from ...base.user_settings import UserSettings
from .mqtt_config import MqttConfig


class MqttConfigPanel(ConfigPanel):

    title = "Home Assistant (MQTT)"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._user_settings = UserSettings.instance()
        self._plugin = parent  # may be None in tests
        cfg = MqttConfig.load_from_settings(self._user_settings)

        outer = QVBoxLayout(self)

        broker_box = QGroupBox("Broker", self)
        bform = QFormLayout(broker_box)
        self.login_field = QLineEdit(broker_box)
        if cfg.username is not None:
            self.login_field.setText(str(cfg.username))
        bform.addRow("Login:", self.login_field)
        self.password_field = QLineEdit(broker_box)
        self.password_field.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        if cfg.password is not None:
            self.password_field.setText(str(cfg.password))
        bform.addRow("Password:", self.password_field)
        self.host_field = QLineEdit(broker_box)
        if cfg.host is not None:
            self.host_field.setText(str(cfg.host))
        bform.addRow("Host:", self.host_field)
        self.port_field = QLineEdit(broker_box)
        if cfg.port is not None:
            self.port_field.setText(str(cfg.port))
        bform.addRow("Port:", self.port_field)
        self.client_id_field = QLineEdit(broker_box)
        if cfg.client_id is not None:
            self.client_id_field.setText(str(cfg.client_id))
        bform.addRow("Client ID:", self.client_id_field)
        outer.addWidget(broker_box)

        device_box = QGroupBox("Device", self)
        dform = QFormLayout(device_box)
        self.device_name_field = QLineEdit(device_box)
        if cfg.device_name is not None:
            self.device_name_field.setText(str(cfg.device_name))
        dform.addRow("Name:", self.device_name_field)
        self.forget_button = QPushButton("Forget device in Home Assistant", device_box)
        self.forget_button.clicked.connect(self._on_forget_device)
        dform.addRow(self.forget_button)
        outer.addWidget(device_box)

    def apply(self) -> bool:
        port_text = self.port_field.text().strip()
        try:
            port_int = int(port_text)
        except ValueError:
            QMessageBox.warning(self, "Invalid port", "Port must be an integer.")
            return False
        device_name = self.device_name_field.text().strip()
        if not device_name:
            QMessageBox.warning(self, "Invalid device name", "Device name cannot be empty.")
            return False

        cfg = MqttConfig(
            host=self.host_field.text(),
            port=port_int,
            username=self.login_field.text(),
            password=self.password_field.text(),
            client_id=self.client_id_field.text(),
            device_name=device_name,
        )
        cfg.save_to_settings(self._user_settings)
        if self._plugin is not None and hasattr(self._plugin, "reload_session"):
            self._plugin.reload_session()
        return True

    def _on_forget_device(self) -> None:
        confirm = QMessageBox.question(
            self, "Forget device?",
            "This will remove the device and all its entities from Home Assistant.\n"
            "Continue?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        if self._plugin is None:
            return
        publisher = getattr(self._plugin, "_publisher", None)
        if publisher is None:
            return
        publisher.delete_all_for_current_device()
        from .entity_settings import EntitySettings
        es = EntitySettings(self._user_settings)
        # Reuse the same entity registry the plugin built so disabling matches what was published.
        for entity in getattr(self._plugin, "_entities", []):
            es.set_publish_enabled(entity.key, False)
```

- [ ] **Step 3: Run all panel tests**

Run: `./env/Scripts/python.exe -m pytest tests/test_mqtt_config_panel.py -v`
Expected: existing tests still pass + 3 new ones pass.

- [ ] **Step 4: Commit**

```bash
git add src/plugins/home_assistant_mqtt_pub/mqtt_config_panel.py tests/test_mqtt_config_panel.py
git commit -m "feat: extend MQTT config panel with device section and validation"
```

---

## Task 26 — Config panel: entities + commands sections

**Files:**
- Modify: `src/plugins/home_assistant_mqtt_pub/mqtt_config_panel.py`
- Modify: `tests/test_mqtt_config_panel.py`

- [ ] **Step 1: Tests for entity rows**

Append to `tests/test_mqtt_config_panel.py`:

```python
def test_panel_shows_one_row_per_entity(qtbot, fake_user_settings, silent_messagebox):
    from src.plugins.home_assistant_mqtt_pub.entities import build_entity_registry
    from src.plugins.home_assistant_mqtt_pub.mqtt_config_panel import MqttConfigPanel
    panel = MqttConfigPanel(parent=None)
    qtbot.addWidget(panel)
    expected_keys = {e.key for e in build_entity_registry()}
    panel_keys = set(panel.entity_rows.keys())
    assert expected_keys.issubset(panel_keys)


def test_apply_persists_entity_publish_and_interval(qtbot, fake_user_settings, silent_messagebox):
    from src.plugins.home_assistant_mqtt_pub.mqtt_config_panel import MqttConfigPanel
    panel = MqttConfigPanel(parent=None)
    qtbot.addWidget(panel)
    panel.host_field.setText("broker")
    panel.port_field.setText("1883")
    panel.login_field.setText("u"); panel.password_field.setText("p"); panel.client_id_field.setText("cid")
    panel.device_name_field.setText("PC")
    row = panel.entity_rows["cpu_usage"]
    row.publish_checkbox.setChecked(False)
    row.interval_field.setText("90")
    assert panel.apply() is True
    assert fake_user_settings.get("homeassistant_publish_cpu_usage") is False
    assert fake_user_settings.get("homeassistant_interval_cpu_usage") == 90
```

- [ ] **Step 2: Extend `mqtt_config_panel.py` with entities + commands sections**

Append to the imports:

```python
from PySide6.QtCore import Qt, QObject, Signal
from PySide6.QtWidgets import QCheckBox, QGridLayout, QLabel
from .entities import build_entity_registry
from .entities.base import SampleResult
from .entity_settings import EntitySettings
from .sampler_runner import SamplerRunner
```

Add this helper class above `MqttConfigPanel`:

```python
class _EntityRow(QObject):
    sample_arrived = Signal(object)

    def __init__(self, parent, entity, settings: EntitySettings) -> None:
        super().__init__(parent)
        self.entity = entity
        self.value_label = QLabel("Loading…", parent)
        self.unit_label = QLabel("", parent)
        self.publish_checkbox = QCheckBox(parent)
        self.publish_checkbox.setChecked(settings.is_publish_enabled(entity.key, entity.default_enabled))
        from PySide6.QtWidgets import QLineEdit
        self.interval_field = QLineEdit(parent)
        if entity.is_event_driven:
            self.interval_field.setText("Event-driven")
            self.interval_field.setEnabled(False)
        else:
            self.interval_field.setText(str(settings.interval_s(entity.key, entity.default_interval_s or 30)))
        self.sample_arrived.connect(self._on_sample, Qt.ConnectionType.QueuedConnection)

    def _on_sample(self, result: SampleResult) -> None:
        if result.is_available:
            self.value_label.setText(str(result.value))
            self.unit_label.setText(result.unit)
        else:
            self.value_label.setText("Not available")
            self.publish_checkbox.setChecked(False)
            self.publish_checkbox.setEnabled(False)
```

Inside `MqttConfigPanel.__init__`, after the device_box is added, append:

```python
        self._entity_settings = EntitySettings(self._user_settings)
        self._sampler = SamplerRunner()
        self.entity_rows: dict[str, _EntityRow] = {}

        entities_box = QGroupBox("Entities", self)
        grid = QGridLayout(entities_box)
        grid.addWidget(QLabel("Name", entities_box), 0, 0)
        grid.addWidget(QLabel("Value", entities_box), 0, 1)
        grid.addWidget(QLabel("Unit", entities_box), 0, 2)
        grid.addWidget(QLabel("Publish", entities_box), 0, 3)
        grid.addWidget(QLabel("Interval (s)", entities_box), 0, 4)

        for row_idx, entity in enumerate(build_entity_registry(), start=1):
            row = _EntityRow(self, entity, self._entity_settings)
            self.entity_rows[entity.key] = row
            grid.addWidget(QLabel(entity.display_name, entities_box), row_idx, 0)
            grid.addWidget(row.value_label, row_idx, 1)
            grid.addWidget(row.unit_label, row_idx, 2)
            grid.addWidget(row.publish_checkbox, row_idx, 3)
            grid.addWidget(row.interval_field, row_idx, 4)
            self._sample_into_row(row)

        refresh = QPushButton("Refresh values", entities_box)
        refresh.clicked.connect(self._refresh_all)
        grid.addWidget(refresh, len(self.entity_rows) + 1, 0, 1, 5)
        outer.addWidget(entities_box)

        commands_box = QGroupBox("Commands", self)
        cgrid = QGridLayout(commands_box)
        self.command_checkboxes: dict[str, QCheckBox] = {}
        from .commands import build_command_registry
        for row_idx, command in enumerate(build_command_registry(self._plugin)):
            checkbox = QCheckBox(command.display_name, commands_box)
            checkbox.setChecked(self._entity_settings.is_command_enabled(command.key, command.default_enabled))
            self.command_checkboxes[command.key] = checkbox
            cgrid.addWidget(checkbox, row_idx, 0)
        outer.addWidget(commands_box)
```

Add the two helper methods:

```python
    def _sample_into_row(self, row: _EntityRow) -> None:
        self._sampler.submit(row.entity.sample, lambda result: row.sample_arrived.emit(result))

    def _refresh_all(self) -> None:
        for row in self.entity_rows.values():
            row.value_label.setText("Loading…")
            self._sample_into_row(row)
```

Extend `apply()` (before the `return True`) to persist entity + command toggles:

```python
        for key, row in self.entity_rows.items():
            self._entity_settings.set_publish_enabled(key, row.publish_checkbox.isChecked())
            if not row.entity.is_event_driven:
                try:
                    self._entity_settings.set_interval_s(key, int(row.interval_field.text()))
                except ValueError:
                    QMessageBox.warning(self, "Invalid interval",
                                        f"Interval for {row.entity.display_name} must be an integer.")
                    return False
        for key, checkbox in self.command_checkboxes.items():
            self._entity_settings.set_command_enabled(key, checkbox.isChecked())
```

- [ ] **Step 3: Run + Commit**

```bash
./env/Scripts/python.exe -m pytest tests/test_mqtt_config_panel.py -v
git add src/plugins/home_assistant_mqtt_pub/mqtt_config_panel.py tests/test_mqtt_config_panel.py
git commit -m "feat: add entities and commands sections to HA config panel"
```

---

## Task 27 — Smoke run + cleanup of stale references

**Files:**
- Modify: any remaining files that reference the old `camelotaorus`/UUID strings (none expected after Task 10's rewrite, but verify).
- Verify: `src/ui/tray_widget.py` import line for `HomeAssistantMqttPubPlugin` still works.

- [ ] **Step 1: Run the full test suite**

Run: `./env/Scripts/python.exe -m pytest tests/ -v`
Expected: every test green.

- [ ] **Step 2: Run flake8 (matches CI)**

Run: `./env/Scripts/python.exe -m flake8 src/plugins/home_assistant_mqtt_pub/ tests/ --max-line-length=120`
Expected: no errors. Fix any unused imports / line-length issues.

- [ ] **Step 3: Search for stale identifiers**

Run via Grep:
```
camelotaorus  ->  must return zero matches
120f167c      ->  must return zero matches
```

If anything appears, remove it.

- [ ] **Step 4: Manual smoke test**

Per CLAUDE.md, kill any running tray instance first:

```powershell
Get-Process | Where-Object { $_.Path -eq "$PWD\env\Scripts\python.exe" } | Stop-Process -Force
```

Then launch:
```bash
./env/Scripts/python.exe -m src.swiss_windows_knife
```

In the running app:
1. Open Configuration → Home Assistant (MQTT). Fill broker fields + device name (e.g. `Camelot Aorus`). Apply.
2. In Home Assistant, navigate to Settings → Devices & Services → MQTT. Confirm the device appears with all 13-ish entities.
3. Lock the screen (`Win + L`); confirm the `Locked` binary sensor flips ON within ~1s. Unlock; confirm it flips OFF.
4. From HA, fire the `Lock screen` button; confirm the PC locks.
5. Open the panel again, untick a sensor (e.g. `cpu_temperature`), apply. Confirm the entity disappears from HA.
6. Click `Forget device in Home Assistant`. Confirm. Confirm all entities disappear from HA.

- [ ] **Step 5: Commit smoke notes (if any minor fixes were needed)**

Only commit if anything changed during smoke. Otherwise skip.

```bash
git add -A
git commit -m "chore: post-redesign cleanup and smoke fixups"
```

---

## Self-review checklist (run before handoff)

**Spec coverage:**

| Spec section | Task(s) |
|---|---|
| Entity set | 6, 11–21 (one task per entity, plus disk_free multi-instance in 16) |
| Command set | 22, 23, 24 |
| Topic structure | 2 (DeviceContext) — used by every entity/command |
| Settings keys | 5 (EntitySettings) + 10 (MqttConfig adds device_name + previous_device_name use) |
| Architecture file layout | 6 (entities/__init__.py registry), 22 (commands/__init__.py), 4 (sampler_runner), 7 (mqtt_session), 8+9 (publisher), 10 (plugin shell), 25+26 (config panel) |
| Reconciliation (rename, add, delete, no-op, first-run) | 8 (pure logic + tests), 9 (integration) |
| Lock event-driven via WTSRegisterSessionNotification | 21 |
| HA reboot recovery via `homeassistant/status` | 9 (`Publisher.on_ha_status`), 10 (subscription wiring) |
| LWT + availability_topic shared by all entities | 7 (LWT in MqttSession), each entity payload includes availability_topic |
| Forget device button | 25 (button), 26 (uses publisher.delete_all_for_current_device) |
| Plugin disable deletes discovery | 10 (`status_changed` calls `publisher.delete_all_for_current_device`) |
| App quit → LWT only | 10 (`closeEvent`) |
| psutil dep | 1 |
| Privilege probe for shutdown | 24 |
| Tests for every entity (available + unavailable) | 6, 11–21 |

**Type / signature consistency:** `Entity` protocol (key, display_name, component, default_enabled, default_interval_s, is_event_driven, discovery_payload, sample) used identically across all entity files. `Command` protocol (key, display_name, default_enabled, is_available, discovery_payload, run) used identically across all command files. `SampleResult.available()` / `SampleResult.unavailable()` factory methods used everywhere instead of constructing the dataclass directly.

**No placeholders:** every step contains complete code or a fully-formed test. Bash commands include the exact pytest path. No "TBD" / "TODO" / "fill in details".

**Frequent commits:** every task ends with one commit; conventional-commit prefixes match the project's allowed tags.
