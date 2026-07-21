# RetroTUI — Codex Next Steps

This is the operational handoff for the next active milestone.

## Current state

The pre-v0.9.6 automated stabilization is complete.

Do not reopen the closed P0/P1 contracts unless a regression or real-terminal failure demonstrates that the contract is insufficient. The completion record is in [STABILIZATION_PRE_0.9.6.md](STABILIZATION_PRE_0.9.6.md).

The active milestone is:

**v0.9.6 — cross-terminal certification**

## Prime directive

Validate RetroTUI in real terminal environments and document what is actually supported.

This milestone is not a feature milestone. Prefer small fixes, regression tests and explicit compatibility notes.

## Source of truth

Use these files together:

- `README.md` — public project overview and support policy.
- `ARCHITECTURE.md` — current ownership and runtime contracts.
- `ROADMAP.md` — milestone boundaries.
- `docs/STABILIZATION_PRE_0.9.6.md` — completed hardening record.
- `docs/TTY_TEST_MATRIX.md` — live certification results.
- `tools/TESTING.md` — manual test checklist.
- `docs/RELEASE.md` — release gate.
- `CHANGELOG.md` — release notes.
- `pyproject.toml`, `retrotui/__init__.py`, `retrotui/core/app.py`, `setup.sh` — version sources.

The July audit documents are historical evidence, not current task lists:

- `docs/TECHNICAL_AUDIT_2026-07.md`
- `docs/CORE_AUDIT_2026-07.md`

## Contracts already closed

Do not create parallel mechanisms for these concerns:

- `WindowManager` owns spawn, focus and close.
- `Window.request_close()` owns close authorization.
- `tick()` reports visual changes.
- `wants_periodic_tick` controls cadence.
- `tick_when_hidden` controls hidden service.
- EventBus creation and lifecycle events are deterministic.
- Dialogs use stable workflow IDs and captured source windows.
- Drag-and-drop prefers `accept_dropped_path()` over `open_path()`.
- Logical colors are mapped according to terminal capacity.
- Terminal PTY reads and writes are budgeted.
- Terminal writes use a FIFO pending queue.
- ConPTY receives `cwd` and merged environment where supported.
- Windows PTY close is explicit and verified.
- CI runs repository checks, `unittest` and pytest across six OS/Python combinations.

If a certification bug touches one of these, patch the existing authority and add a focused regression. Do not add a second flag, dispatcher or process owner.

## v0.9.6 scope

Test and document:

- Linux console / TTY.
- Linux GUI terminal emulators.
- SSH sessions.
- tmux.
- GNU screen.
- WSL + Windows Terminal.
- Native Windows with `pywinpty` / ConPTY.

For each environment cover:

- startup and clean shutdown;
- keyboard and global shortcuts;
- mouse routing and capture;
- resize behavior;
- Unicode and wide characters;
- color capacity and theme degradation;
- File Manager;
- Notepad;
- embedded Terminal;
- representative bundled plugins.

## Hard boundaries

Do not start these during v0.9.6 unless required to fix a certification blocker:

- session restore;
- first-run wizard;
- Start Menu redesign;
- new games, themes or bundled apps;
- marketplace/discovery UX;
- broad plugin API redesign;
- networking expansion;
- visual redesign;
- large refactor of the core.

These belong to later roadmap milestones.

## Required workflow per environment

### 1. Record the environment

Capture at least:

- operating system and version;
- Python version;
- terminal emulator or physical TTY;
- `$TERM` or Windows terminal host;
- tmux/screen/SSH layer if present;
- locale and encoding;
- color capability if known;
- mouse backend used.

### 2. Install cleanly

```bash
python -m pip install -e ".[test]"
```

On Windows confirm that `windows-curses` and `pywinpty` are installed by the package markers.

### 3. Run the automated gate

```bash
python tools/qa.py --skip-tests
python -m unittest discover -s tests -v
python -m pytest tests -q
```

A failure here is a release blocker before manual certification continues.

### 4. Launch RetroTUI

```bash
retrotui
```

### 5. Test the base profile

Prioritize:

1. File Manager.
2. Notepad.
3. Terminal.

Then test representative menus, dialogs and plugins.

### 6. Execute the manual checklist

Use `tools/TESTING.md`. Record only actions relevant to that environment, but explain skipped items.

### 7. Update the matrix

Write results directly to `docs/TTY_TEST_MATRIX.md`. Do not create a parallel compatibility document.

### 8. Convert failures into evidence

For every failure:

- record exact environment and reproduction steps;
- classify severity;
- decide whether it is a RetroTUI bug or terminal limitation;
- add an automated regression when simulation is possible;
- document the limitation when it cannot be fixed reliably.

## Embedded terminal certification

Run available commands such as:

```bash
printf '\033[31mred\033[0m normal\n'
printf '\033[?1049hALT SCREEN\033[?1049lNORMAL\n'
less README.md
nano
vim
top
htop
mc
```

Check:

- cursor position after wraps and resize;
- normal/alternate-screen transitions;
- scrollback without duplicated rows;
- copy and selection;
- DEC mouse pass-through when requested;
- RetroTUI mouse ownership when not requested;
- output continues to drain while minimized;
- continuous output does not freeze the desktop;
- large paste/input is delivered in FIFO order;
- child process closes cleanly when the window closes.

### Windows-specific terminal checks

Verify:

- shell starts in the requested `cwd`;
- inherited environment remains available;
- `extra_env` overrides/extends it;
- resize reaches ConPTY;
- interrupt/terminate behavior is observable;
- close does not leave a child process running;
- a failed close is surfaced instead of silently dropping the backend.

## Severity policy

### Critical

- data loss;
- persistent config corruption;
- process left running after a reported successful close;
- app cannot exit cleanly;
- main loop becomes unusable.

### High

- base app unusable in a target environment;
- common terminal input or resize consistently broken;
- dialog result affects the wrong window;
- terminal traffic starves the desktop.

### Medium/Low

- environment-specific visual defects;
- recoverable feature limitations;
- optional plugin issues.

Critical and high issues in environments intended to be marked supported must be fixed or the environment must be downgraded in the matrix.

## Fix policy

1. Reproduce first.
2. Patch the existing authority.
3. Add a focused regression.
4. Run both test runners.
5. Re-run the affected real environment.
6. Update the matrix and changelog.
7. Avoid unrelated cleanup.

## Definition of done for v0.9.6

v0.9.6 is ready when:

- every target environment has a recorded classification or an explicit reason it could not be tested;
- the base profile is documented per environment;
- critical/high certification failures are fixed or clearly excluded from support;
- the permanent six-combination CI matrix is green;
- README claims agree with the TTY matrix;
- `CHANGELOG.md` and release notes describe the certified scope;
- all version sources are synchronized for the release commit.

## Suggested commit sequence

Use small commits:

1. `docs: record <environment> certification`
2. `test: reproduce <specific compatibility bug>`
3. `fix: handle <specific compatibility bug>`
4. `docs: update compatibility status`
5. `release: prepare v0.9.6`

## After v0.9.6

Only after certification is closed, move to v0.9.7:

- session restore;
- first-run experience;
- Start Menu categories;
- plugin/app toggles in Control Panel;
- shortcut documentation;
- plugin crash recovery;
- config migration policy.
