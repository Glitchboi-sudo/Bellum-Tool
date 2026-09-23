# CLAUDE.md — Bellum Tool

Native Linux (Qt6 / PySide6) desktop GUI to manage **PAX PayDroid** POS terminals
(A910 / A920 / A930, D-series…) over ADB. It is a front-end over the external
`pax_adb` binary plus `fastboot` / `paydroidboot`.

## Run / dev

- **Run:** `./run.sh` or `python main.py` (uses `.venv/bin/python` if present).
- **Deps:** Python 3.10+, `PySide6>=6.6` only. Do **not** add runtime dependencies
  (no pyserial, no Pillow, etc.) — use what PySide6/stdlib already provide
  (e.g. `QtSerialPort` for serial, `QImage` + `gzip` for image work).
- **`pax_adb` binary:** located via `$PAX_ADB` → `PATH` → known paths
  (`bellum/core/adb.py:_CANDIDATE_PATHS`). Override with `PAX_ADB=/path ./run.sh`.
- No test suite or linter config is checked in; keep changes runnable by hand.

## Layout

- `bellum/core/` — UI-agnostic services. `adb.py` (`AdbService`, `CommandResult`),
  `fastboot.py`, `inventory.py` (systool device dump), `models.py`. Core code may
  import `PySide6.QtCore` but **never** `QtWidgets` — keep it UI-free; it talks to
  the UI only through injected callbacks.
- `bellum/ui/` — `main_window.py`, `widgets.py` (`AppContext`, `Page`, `TabPage`,
  `Card`, and helpers `hint`/`icon_button`/`flow_row`/`_hrow`), `theme.py`,
  dialogs.
- `bellum/ui/pages/` — one file per tool page. Register a new page by importing it
  in `main_window.py` and adding it to the relevant section list.

## Conventions

- **Language:** all comments, docstrings, and user-facing UI strings are in
  **Spanish**. Match that — do not introduce English strings in the UI.
- Every module starts with `from __future__ import annotations` and a Spanish
  module docstring explaining what the tool does and its scope.
- **Type hints** on function signatures; modern syntax (`str | None`, `list[str]`).

## UI / page pattern

- Pages subclass `Page` (or `TabPage` for grouped sub-pages) and receive an
  `AppContext` (`ctx`) exposing: `ctx.adb`, `ctx.fastboot`, `ctx.palette`,
  `ctx.notify(message, level)`.
- **`ctx.notify` levels:** `"info" | "ok" | "warn" | "error"` — use `warn` for
  "you forgot to pick X", `error` for failures, `ok` for success.
- Build UIs from the `widgets` helpers (`Card`, `hint`, `icon_button`, `flow_row`,
  `_hrow`) so styling stays consistent; colors come from `ctx.palette`, never
  hard-coded hex.
- A page that owns a long-lived resource (QProcess stream, serial port) must
  implement `shutdown()` — `MainWindow.closeEvent` calls it on every page.

## Async command execution (important)

- **Never block the UI thread.** All device I/O goes through `AdbService`, which
  runs `pax_adb` via `QProcess` and delivers results in a callback:
  - `adb.run(args: list[str], on_finished, *, targeted=True, merge_stderr=False)`
  - `adb.shell(command: str, on_finished)` — one shell command string.
- Sequential multi-step flows are chained through callbacks (each step's callback
  launches the next), not loops — see `core/inventory.py` and `pages/dump.py`.
- `CommandResult`: `.ok` (returncode == 0), `.returncode`, `.text` (stdout, or
  stderr if stdout empty), `.stdout`, `.stderr`. Always check `.ok` before
  treating output as success, and handle the empty-output case (locked shells on
  PAX return exit 0 with no data).
- Remote scratch dirs (e.g. `/sdcard/bellum_dump`) are ephemeral: clear before
  writing and only clean up on success so a failed transfer keeps its data.

## Scope boundary (do not cross)

This is a **device-management + authorized security-assessment** tool for
equipment the operator owns or is authorized to test. **Active/write operations
are in scope**, not just read-only: reboot, flashing, package management
(install/uninstall/enable/clear/permissions), file push/pull and APK extraction
(incl. staging via `/data/local/tmp` to get around sync/SELinux limits), `setprop`,
component interaction (`am start`/broadcast) for surface testing, partition dump,
wipe, and the parameterized `systool` commands.

**Still out of scope (the hard line): turnkey payment-security bypass.** Do not
build features whose purpose is to extract, forge, or capture **cardholder data or
payment cryptographic material** — SRED/DUKPT/injected keys, PIN blocks, PAN/track
data — nor to **defeat tamper detection** or the secure-processor boundary. Handling
these partitions/commands as opaque blobs (dump/restore of `pax_authinfo` etc. that
the operator already controls) is fine; parsing/decrypting/forging their contents is not.

Destructive or payment-adjacent operations must stay **parameterized** (the user
types them), never preselected, wrapped in a `DangerCard`, and gated by a Spanish
confirmation dialog. Preserve the existing `_SENSITIVE`/`confirm=` guards when
touching `systool.py`, `dump.py`, `recycle.py`, `flash.py`.
