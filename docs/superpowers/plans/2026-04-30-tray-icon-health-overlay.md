# Tray Icon Health Overlay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Overlay a coloured dot in the top-right corner of the tray icon reflecting aggregate plugin health, refreshing live whenever any plugin's health or toggle state changes.

**Architecture:** Add a `health_changed = Signal()` on `BaseWidget`, emitted by `_set_health` (on real state-or-message change) and by `set_enabled` (on toggle transitions). `TrayWidget` connects each plugin's signal to a slot that aggregates health and rebuilds the tray icon via a new `tray_icon_for_state(HealthState)` helper.

**Tech Stack:** Python 3.12, PySide6 (`Signal`, `QPixmap`, `QPainter`, `QIcon`), pytest-qt.

**Branch:** `feat/plugin-health-status` (already in flight as PR #16; this set of commits adds the icon overlay to the same PR).

**Spec:** `docs/superpowers/specs/2026-04-30-tray-icon-health-overlay-design.md` (committed at e42a6d2).

---

### Task 1: BaseWidget gains `health_changed` Signal and emits on `_set_health` change

**Files:**
- Modify: `src/base/base_widget.py`
- Modify: `tests/test_base_widget.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_base_widget.py`:

```python
def test_health_changed_emits_on_state_change(qtbot, fake_user_settings):
    from src.base.health import HealthState
    widget = BaseWidget(None)
    qtbot.addWidget(widget)

    fired: list[None] = []
    widget.health_changed.connect(lambda: fired.append(None))

    widget._set_health(HealthState.WARNING, "x")
    assert fired == [None]


def test_health_changed_emits_on_message_change(qtbot, fake_user_settings):
    from src.base.health import HealthState
    widget = BaseWidget(None)
    qtbot.addWidget(widget)
    widget._set_health(HealthState.OK, "Auto")

    fired: list[None] = []
    widget.health_changed.connect(lambda: fired.append(None))

    widget._set_health(HealthState.OK, "Manual 60")
    assert fired == [None]


def test_health_changed_does_not_emit_on_noop(qtbot, fake_user_settings):
    from src.base.health import HealthState
    widget = BaseWidget(None)
    qtbot.addWidget(widget)
    widget._set_health(HealthState.OK, "Auto")

    fired: list[None] = []
    widget.health_changed.connect(lambda: fired.append(None))

    widget._set_health(HealthState.OK, "Auto")  # same value
    assert fired == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./env/Scripts/python.exe -m pytest tests/test_base_widget.py -v -k health_changed`
Expected: FAIL — `AttributeError: 'BaseWidget' object has no attribute 'health_changed'`.

- [ ] **Step 3: Write minimal implementation**

Modify `src/base/base_widget.py`. Add the import at the top alongside the existing PySide6 imports:

```python
from PySide6.QtCore import Signal
```

Add the class-level signal declaration just after the `display_name` class attribute (before `__init__`):

```python
class BaseWidget(QWidget):

    display_name: str = ""

    health_changed = Signal()
```

Replace `_set_health` with the change-detecting variant:

```python
    def _set_health(self, state: HealthState, message: str) -> None:
        new_report = HealthReport(state, message)
        if new_report == self._current_health:
            return
        self._current_health = new_report
        self.health_changed.emit()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./env/Scripts/python.exe -m pytest tests/test_base_widget.py -v`
Expected: All tests PASS (existing 13 + 3 new = 16).

- [ ] **Step 5: Commit**

```bash
git add src/base/base_widget.py tests/test_base_widget.py
git commit -m "feat: BaseWidget emits health_changed when state/message changes"
```

---

### Task 2: BaseWidget emits `health_changed` on `set_enabled` transitions

**Files:**
- Modify: `src/base/base_widget.py`
- Modify: `tests/test_base_widget.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_base_widget.py`:

```python
def test_health_changed_emits_on_set_enabled_transition(qtbot, fake_user_settings):
    widget = BaseWidget(None, is_toggleable=True, is_enabled=True)
    qtbot.addWidget(widget)

    fired: list[None] = []
    widget.health_changed.connect(lambda: fired.append(None))

    widget.set_enabled(False)
    assert fired == [None]


def test_health_changed_does_not_emit_on_set_enabled_noop(qtbot, fake_user_settings):
    widget = BaseWidget(None, is_toggleable=True, is_enabled=True)
    qtbot.addWidget(widget)

    fired: list[None] = []
    widget.health_changed.connect(lambda: fired.append(None))

    widget.set_enabled(True)  # already True
    assert fired == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./env/Scripts/python.exe -m pytest tests/test_base_widget.py -v -k set_enabled_transition -k set_enabled_noop`
Expected: 1 FAIL (the transition test sees `fired == []`), 1 PASS (the noop test happens to pass already since no signal fires).

Run the full file to be sure:
Run: `./env/Scripts/python.exe -m pytest tests/test_base_widget.py -v`
Expected: 1 NEW failure (transition).

- [ ] **Step 3: Write minimal implementation**

Modify `src/base/base_widget.py`. Replace `set_enabled`:

```python
    def set_enabled(self, enabled: bool) -> None:
        if self._is_enabled == enabled:
            return
        self._is_enabled = enabled
        UserSettings.instance().set(_settings_key(self.__class__), enabled)
        logging.info(f'Plugin {self.__class__.__name__} is enabled: {enabled}')
        self.status_changed(enabled)
        self.health_changed.emit()
```

(The new line is `self.health_changed.emit()` at the end. The early-return at the top means it only fires on real toggle transitions.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `./env/Scripts/python.exe -m pytest tests/test_base_widget.py -v`
Expected: All tests PASS (16 + 2 new = 18).

- [ ] **Step 5: Commit**

```bash
git add src/base/base_widget.py tests/test_base_widget.py
git commit -m "feat: BaseWidget emits health_changed on toggle transitions"
```

---

### Task 3: `tray_icon_for_state` helper

**Files:**
- Modify: `src/ui/health_icons.py`
- Modify: `tests/test_health_icons.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_health_icons.py`:

```python
def test_tray_icon_for_state_returns_non_null(qtbot):
    # Resources must be loaded so :/icons/coat-of-arms.ico resolves.
    from src import resources  # noqa: F401
    from src.ui.health_icons import tray_icon_for_state

    for state in HealthState:
        icon = tray_icon_for_state(state)
        assert not icon.isNull(), f"tray icon for {state} is null"


def test_tray_icon_for_state_is_cached(qtbot):
    from src import resources  # noqa: F401
    from src.ui.health_icons import tray_icon_for_state

    a = tray_icon_for_state(HealthState.OK)
    b = tray_icon_for_state(HealthState.OK)
    assert a is b
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./env/Scripts/python.exe -m pytest tests/test_health_icons.py -v`
Expected: 2 new tests FAIL — `ImportError: cannot import name 'tray_icon_for_state' from 'src.ui.health_icons'`.

- [ ] **Step 3: Write minimal implementation**

Modify `src/ui/health_icons.py`. Add a constant near `_ICON_SIZE`:

```python
_TRAY_ICON_SIZE = QSize(64, 64)
_TRAY_DOT_RECT = (40, 0, 24, 24)  # x, y, width, height — top-right
```

Append the helper at the bottom of the file:

```python
@cache
def tray_icon_for_state(state: HealthState) -> QIcon:
    """Return the app's tray icon overlaid with a coloured dot for `state`.

    The dot sits in the top-right corner of a 64x64 composed pixmap;
    Windows downsamples for the systray slot. Cached per state.
    """
    base = QIcon(":/icons/coat-of-arms.ico").pixmap(_TRAY_ICON_SIZE)
    composed = QPixmap(_TRAY_ICON_SIZE)
    composed.fill(Qt.GlobalColor.transparent)
    painter = QPainter(composed)
    try:
        painter.drawPixmap(0, 0, base)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setBrush(_COLORS[state])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(*_TRAY_DOT_RECT)
    finally:
        painter.end()
    icon = QIcon()
    icon.addPixmap(composed, QIcon.Mode.Normal)
    icon.addPixmap(composed, QIcon.Mode.Disabled)
    return icon
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./env/Scripts/python.exe -m pytest tests/test_health_icons.py -v`
Expected: 4 tests PASS (2 existing + 2 new).

- [ ] **Step 5: Commit**

```bash
git add src/ui/health_icons.py tests/test_health_icons.py
git commit -m "feat: tray_icon_for_state composes coat-of-arms with health dot"
```

---

### Task 4: `TrayWidget` refreshes its icon on `health_changed`

**Files:**
- Modify: `src/ui/tray_widget.py`
- Modify: `tests/test_tray_widget_health.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_tray_widget_health.py`:

```python
def test_tray_icon_refreshes_on_plugin_health_change(qtbot, fake_user_settings):
    """The tray's icon refresh slot is wired to each plugin's health_changed
    signal and rebuilds the icon via tray_icon_for_state."""
    from unittest.mock import MagicMock

    from PySide6.QtCore import Signal
    from PySide6.QtWidgets import QWidget

    from src import resources  # noqa: F401
    from src.base.health import HealthState
    from src.ui.tray_widget import TrayWidget

    class _SignalingPlugin(QWidget):
        health_changed = Signal()

        def __init__(self, name: str, report: HealthReport):
            super().__init__()
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

        def set_report(self, report: HealthReport) -> None:
            self._report = report
            self.health_changed.emit()

    plugins = [
        _SignalingPlugin("Alpha", HealthReport(HealthState.OK, "ok")),
        _SignalingPlugin("Bravo", HealthReport(HealthState.OK, "ok")),
    ]

    class _TrayForTest(TrayWidget):
        def __init__(self, components):
            QWidget.__init__(self, parent=None)
            self._config_dialog = None
            self.logger_window = None
            self.child_components = components
            self._tray_icon = MagicMock()
            self._wire_health_signals()
            self._refresh_tray_icon()

    tray = _TrayForTest(plugins)
    qtbot.addWidget(tray)

    # Initial refresh in __init__ called setIcon once with the OK icon.
    assert tray._tray_icon.setIcon.call_count == 1

    tray._tray_icon.setIcon.reset_mock()
    plugins[1].set_report(HealthReport(HealthState.WARNING, "broker down"))
    assert tray._tray_icon.setIcon.call_count == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./env/Scripts/python.exe -m pytest tests/test_tray_widget_health.py::test_tray_icon_refreshes_on_plugin_health_change -v`
Expected: FAIL — `AttributeError: 'TrayWidget' object has no attribute '_wire_health_signals'`.

- [ ] **Step 3: Write minimal implementation**

Modify `src/ui/tray_widget.py`. Add the import alongside the existing health-icons import:

```python
from .health_icons import icon_for_state, tray_icon_for_state
```

In `TrayWidget.__init__`, after `self._tray_icon.show()`, add:

```python
        self._wire_health_signals()
        self._refresh_tray_icon()
```

Add the two new methods on the class (place them near `_populate_main_menu`):

```python
    def _wire_health_signals(self) -> None:
        for plugin in self.child_components:
            plugin.health_changed.connect(self._refresh_tray_icon)

    @Slot()
    def _refresh_tray_icon(self) -> None:
        reports: list[HealthReport] = []
        for plugin in self.child_components:
            try:
                reports.append(plugin.health())
            except Exception:
                logging.exception("plugin %s health() raised", plugin.__class__.__name__)
                reports.append(HealthReport(HealthState.WARNING, "health() failed"))
        worst_state, _ = aggregate_health(reports)
        self._tray_icon.setIcon(tray_icon_for_state(worst_state))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./env/Scripts/python.exe -m pytest tests/test_tray_widget_health.py -v`
Expected: All 7 tests PASS (6 existing + 1 new).

Then run the full suite to confirm no regressions:
Run: `./env/Scripts/python.exe -m pytest tests/ -q`
Expected: 230 passed (222 baseline + 3 from Task 1 + 2 from Task 2 + 2 from Task 3 + 1 from Task 4). The suite must be fully green.

- [ ] **Step 5: Commit**

```bash
git add src/ui/tray_widget.py tests/test_tray_widget_health.py
git commit -m "feat: tray icon shows aggregate health overlay"
```

---

### Task 5: Manual smoke + push

- [ ] **Step 1: Run the full test suite**

Run: `./env/Scripts/python.exe -m pytest tests/ -q`
Expected: full green.

- [ ] **Step 2: Run ruff to match CI**

Run: `./env/Scripts/python.exe -m ruff check src tests`
Expected: `All checks passed!`.

- [ ] **Step 3: Manual smoke test**

Stop any running tray Python:

```powershell
Get-Process | Where-Object { $_.Path -like "*\swiss-windows-knife\env\Scripts\python.exe" } | Stop-Process -Force
```

Then launch the dev tray:

```bash
./env/Scripts/python.exe -m src.swiss_windows_knife
```

Verify:
- The tray icon shows a small green dot in its top-right corner.
- Briefly disconnecting from the network: the dot flips to amber when HA reports `Disconnected` and back to green on reconnect.
- Toggling a plugin off in `Configuration → Plugins`: the icon refreshes (the dot stays green because Disabled doesn't contribute, but you can verify the path was exercised by checking the menu's `Health: …` title).
- Forcing a fake VCPError (e.g., temporarily renaming the brightness device, or just verifying via the unit tests in Task 1): if any plugin reports Warning, the dot is amber.

- [ ] **Step 4: Push**

```bash
git push
```

The branch is already tracking `origin/feat/plugin-health-status` (from earlier in this PR), so the new commits land on PR #16 automatically.

---

## Self-review notes

**Spec coverage:**

- Always-show coloured dot reflecting aggregate state — Task 4 (`_refresh_tray_icon` calls `setIcon(tray_icon_for_state(worst_state))`).
- Push model via `health_changed` signal — Task 1 (`_set_health` emit) + Task 2 (`set_enabled` emit).
- DISABLED ignored in aggregate, all-disabled → green — already handled by `aggregate_health` from the parent feature; the new code reuses it unchanged.
- Initial paint at `__init__` so the icon reflects starting state — Task 4 (`self._refresh_tray_icon()` call after `_wire_health_signals`).
- Per-plugin failure isolation — Task 4 (`try/except Exception` around `plugin.health()` in the slot, mirroring `_populate_main_menu`'s pattern).
- 64×64 base, 24-px dot at `(40, 0, 24, 24)` — Task 3 helper.
- `@cache` on the icon helper — Task 3.
- Both Normal and Disabled QIcon modes registered — Task 3.

**Type / signature consistency:**
- `health_changed = Signal()` (no payload) — Task 1, used identically in Tasks 2 and 4.
- `tray_icon_for_state(state: HealthState) -> QIcon` — Task 3, called with the same signature in Task 4.
- `aggregate_health` is an existing helper (parent feature); the new slot calls it with a `list[HealthReport]` (no plugin pairs), matching its existing signature.

**Placeholder scan:** No TBDs, no "implement later", no "similar to Task N" handwaves. Every code step shows the actual code. Test inputs (`"x"`, `"broker down"`, etc.) are concrete strings.
