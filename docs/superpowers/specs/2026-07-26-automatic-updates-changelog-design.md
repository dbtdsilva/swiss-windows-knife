# Automatic updates + multi-version changelog — design

## Problem

The updater (`swiss_windows_knife/components/update_checker.py`) prompts on
every newer release and offers a "Don't ask again for version X" checkbox
whose scope is a single version (`update_skip_version == remote_version`).
Because the scope is per-version, each new release re-prompts — it reads as
if the preference "resets" every update, when in fact it only ever
suppressed one specific version.

Two things are wanted:

1. An **Automatic updates** toggle. When on, updates install silently in the
   background (with only a brief tray notification). When off, keep today's
   prompt-and-skip behaviour.
2. When prompting, **show the release notes** for every version between the
   installed one and the target — if two minor versions separate them, both
   changelogs are shown.

## Goals

- Opt-in silent auto-update, surfaced via a tray balloon only.
- Manual mode shows a readable, scrollable changelog spanning all skipped
  versions, newest first.
- Preserve the existing per-version skip in manual mode.
- No behaviour change for users who do nothing (default off).

## Non-goals

- Deferring/scheduling updates for a "convenient moment".
- Pre-release / draft channel support (stable releases only).
- A global "never update" switch (auto-off + per-version skip already covers
  the intent).

## Decisions (from brainstorming)

- **Toggle UI:** an `Updates` submenu in the tray with `Check for updates…`
  and a checkable `Automatic updates` entry.
- **Default:** `Automatic updates` off. Only governs releases *after* the one
  that ships this feature (the shipping release still arrives via the current
  prompt). Sole-user app, so low stakes; off is least-surprising.
- **Auto UX:** brief tray notification, then silent install + restart.
- **Changelog:** all releases with version > current, up to target,
  concatenated newest-first with version headers.
- **Changelog rendering:** dedicated `QDialog` + `QTextBrowser`
  (`setMarkdown`), not `QMessageBox.setDetailedText`.
- **Prereleases/drafts:** excluded from both target selection and changelog.

## Architecture

### Components / files

- `components/update_checker.py` (modified)
  - `retrieve_menus()` returns a single `Updates` `QMenu` containing
    `Check for updates…` (interactive check) and a checkable
    `Automatic updates` action bound to the `update_automatic` setting.
  - `_CheckThread` fetches `/releases` (list) instead of `/releases/latest`,
    and emits a richer result.
  - `_on_check_finished` branches on `update_automatic`.
  - New signal `notification_requested = Signal(str, str)` (title, message).
- `components/update_prompt_dialog.py` (new)
  - `UpdatePromptDialog(QDialog)`: scrollable `QTextBrowser` rendering the
    concatenated markdown changelog, Yes/No buttons, and a
    "Don't ask again for version X" checkbox. Exposes the accepted result and
    the checkbox state to the caller (the caller owns the settings write, as
    today).
- `ui/tray_widget.py` (modified)
  - Connect `update_checker.notification_requested` to
    `self._tray_icon.showMessage(title, message, icon)`.

### GitHub API

Switch endpoint:

```
https://api.github.com/repos/dbtdsilva/swiss-windows-knife/releases
```

Returns releases newest-first (up to 30/page — far more than the gap will
ever be for a single-user app; if the gap somehow exceeds one page the
older notes are simply omitted, which is acceptable and logged).

Per release used: `tag_name`, `body`, `assets[].name`/`browser_download_url`,
`draft`, `prerelease`.

### Pure helper

```
_releases_above(releases: list[dict], current: str)
    -> tuple[str | None, str | None, list[tuple[str, str]]]
```

Returns `(target_tag, installer_url, changelog_entries)` where:
- drafts and prereleases are filtered out,
- `target_tag` is the highest `_parse_version` among the remainder,
- `installer_url` is the first `.exe` asset on the target release,
- `changelog_entries` are `(tag, body)` for every remaining release with
  `_parse_version(tag) > _parse_version(current)`, sorted newest-first.

If nothing qualifies (all ≤ current, or no installer asset), returns
`(None, None, [])`, which the caller treats as "up to date".

Keeping this pure (no Qt, no network) makes the version math directly
unit-testable; the worker just calls `requests.get(...).json()` and hands the
list to it.

### Worker result shape

`_CheckThread.result_ready` emits either `None` (network/parse failure) or
`(target_tag, installer_url, changelog_entries)`. This replaces the current
`(tag_name, installer_url)` tuple; `_on_check_finished` and the existing
tests are updated accordingly.

## Data flow

1. Timer / startup / menu → `check_updates(interactive)`.
2. `_CheckThread` fetches `/releases`, calls `_releases_above(...)`, emits the
   triple (or `None`).
3. `_on_check_finished(result)`:
   - `None` → warn (interactive) / health WARNING, as today.
   - `target_tag is None` or not newer than `APP_INFO.APP_VERSION` →
     "Up to date" (info if interactive), as today.
   - Newer:
     - health OK `Update available {target}`.
     - **`update_automatic` True:** emit
       `notification_requested("Swiss Windows Knife", "Updating to {target}…")`,
       then download + silent install + restart (existing `_DownloadThread` /
       `_launch_installer`). `update_skip_version` is ignored in this mode.
     - **False:** if `update_skip_version == target`, stop. Otherwise open
       `UpdatePromptDialog` with `changelog_entries`. On accept → download +
       install. On decline with checkbox → store `update_skip_version =
       target` (unchanged semantics; now keyed to the target version).

## Settings

- New: `update_automatic: bool`, default `False`. Seeded on first read via the
  existing `get(..., bool, False)` default pattern (no migration needed).
- Unchanged: `update_skip_version: str`, consulted only in manual mode.

## Error handling

- Network / JSON / HTTP errors → `result_ready.emit(None)` (unchanged path):
  interactive shows a warning box, health goes WARNING; the watchdog still
  guards a wedged worker.
- No installer asset on target → treated as "up to date" (logged), same as the
  current "no installer asset" branch.
- Download failure in auto mode → `_on_download_finished(None)` returns
  quietly (unchanged); health already reflects the attempt. No installer is
  launched.
- Tray notification is best-effort; a missing/late tray icon connection never
  blocks the install.

## Testing

Unit (pure, no Qt):

- `_releases_above`:
  - filters drafts and prereleases,
  - picks highest-version target,
  - returns changelog entries strictly `> current`, newest-first,
  - excludes `== current`,
  - `(None, None, [])` when nothing newer or no `.exe` asset.

Component (`UpdateChecker`, qtbot + `fake_user_settings`):

- Auto mode: `update_automatic=True` + newer target → `_confirm_update` /
  dialog NOT invoked, `notification_requested` fires, download started
  (threads patched), skip-version ignored even when it equals the target.
- Manual mode: newer target → dialog invoked with the changelog entries;
  accept → download; decline+checkbox → `update_skip_version` set to target;
  `update_skip_version == target` → no dialog.
- Existing health tests updated for the new `(target, url, changelog)` result
  shape.

Dialog (`UpdatePromptDialog`, qtbot):

- Renders each `(tag, body)` entry (text present in the browser).
- Reports accept/decline and checkbox state to the caller.

Menu:

- `retrieve_menus()` returns an `Updates` menu with a checkable
  `Automatic updates` action reflecting the setting; toggling it writes
  `update_automatic`.

## Rollout

Ships in the next release like any other change (semantic-release: this is a
`feat:` → minor bump). No data migration; the new setting defaults off.
