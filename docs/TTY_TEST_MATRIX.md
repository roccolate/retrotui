# RetroTUI TTY Test Matrix

This is the living real-environment certification document for RetroTUI v0.9.6.

## Certification summary

**Last updated:** 2026-07-21  
**Published package version:** `0.9.5`  
**Certification baseline:** `main` after the completed pre-v0.9.6 stabilization gate  
**Current state:** certification in progress; no environment is fully certified yet

Automated tests validate internal contracts. They do not by themselves certify a physical TTY, terminal emulator, SSH client, multiplexer, WSL host or Windows ConPTY environment.

### Automated prerequisite

| OS | Python | Repository QA | unittest | pytest |
|---|---:|---:|---:|---:|
| Ubuntu | 3.10 | ✅ | ✅ | ✅ |
| Ubuntu | 3.12 | ✅ | ✅ | ✅ |
| Ubuntu | 3.14 | ✅ | ✅ | ✅ |
| Windows | 3.10 | ✅ | ✅ | ✅ |
| Windows | 3.12 | ✅ | ✅ | ✅ |
| Windows | 3.14 | ✅ | ✅ | ✅ |

### Legend

- ✅ Supported: required checks completed without unresolved critical or high defects.
- ⚠️ Partially supported: usable with documented limitations or incomplete coverage.
- ❌ Not supported: a blocking limitation prevents supported use.
- 🧪 Not tested yet.

### Environment summary

| Environment | Startup | Keyboard | Mouse | Resize | Unicode | Colors | Embedded Terminal | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Linux physical TTY | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | Pending |
| Linux GUI terminal | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | Pending |
| SSH | ⚠️ | 🧪 | 🧪 | 🧪 | 🧪 | ⚠️ | 🧪 | Historical signal-only evidence |
| tmux | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | Pending |
| GNU screen | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | Pending |
| WSL + Windows Terminal | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | Pending |
| Windows native / ConPTY | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | Pending |

## Certification rules

- Record every tested environment in the result log.
- Record the exact RetroTUI commit, Python version, terminal host, locale and nesting layer.
- Do not mark an environment supported until startup, shutdown, keyboard, mouse, resize, Unicode, colors, File Manager, Notepad and Terminal have been checked.
- Test representative bundled plugins before assigning full support.
- Convert reproducible RetroTUI defects into automated regressions when simulation is possible.
- Document terminal limitations that cannot be corrected reliably.
- Keep README, ROADMAP, PROJECT_STATUS and release notes aligned with this matrix.

## Target environments

- [ ] Linux physical TTY.
- [ ] Linux GUI terminal emulator.
- [ ] tmux over a GUI terminal.
- [ ] tmux over a physical TTY.
- [ ] GNU screen.
- [ ] Linux or BSD SSH client to a remote host.
- [x] Windows with MobaXterm SSH to VPS — historical signal-only evidence, not full certification.
- [ ] Windows Terminal with OpenSSH.
- [ ] Windows Terminal with WSL2.
- [ ] Native Windows Python with `windows-curses` and `pywinpty` / ConPTY.

## Information to record

For each run capture:

- operating system and version;
- terminal emulator or physical TTY;
- local, SSH, tmux, screen or WSL nesting;
- RetroTUI version and commit;
- Python version;
- `TERM`, `COLORTERM`, locale and encoding where applicable;
- reported color capacity;
- mouse backend;
- Windows Terminal, PowerShell and ConPTY information when applicable.

## Automated prerequisite per environment

Run the permanent gate from a clean development installation:

```bash
python -m pip install -e ".[test]"
python tools/qa.py --skip-tests
python -m unittest discover -s tests -v
python -m pytest tests -q
```

Mark:

- [ ] Repository QA passed.
- [ ] unittest passed.
- [ ] pytest passed.
- [ ] Correct platform dependencies were installed.

A failure here blocks manual certification for that environment.

## Desktop smoke test

- [ ] Launch and exit RetroTUI cleanly five times.
- [ ] Open and close windows repeatedly.
- [ ] Drag, resize, minimize, restore and maximize windows.
- [ ] Cycle focus with keyboard and mouse.
- [ ] Open and close global, window and context menus.
- [ ] Confirm `Ctrl+Q` closes menu layers before requesting application exit.
- [ ] Confirm `Esc` closes the active menu layer and otherwise reaches the focused app.
- [ ] Test clipboard copy and paste.
- [ ] Resize the host terminal repeatedly, including small dimensions.
- [ ] Confirm terminal modes and the host shell are restored after exit.

## File Manager

- [ ] Directory navigation.
- [ ] Dual-pane mode and pane focus.
- [ ] Copy, move, rename, new file and new directory.
- [ ] Drag-and-drop copies into File Manager instead of navigating unexpectedly.
- [ ] Permission-denied and missing-path errors are surfaced without crashing.
- [ ] Trash and undo behavior where supported.

## Notepad

- [ ] Open and save UTF-8 files.
- [ ] Edit wide and combining characters.
- [ ] Word wrap remains stable after resize.
- [ ] Dirty close requests confirmation.
- [ ] Dirty Open does not discard content without confirmation.
- [ ] Cancel preserves the window and content.

## Embedded Terminal

Exercise available tools such as `less`, `nano`, `vim`, `top`, `htop` and `mc`.

- [ ] Shell starts and accepts input.
- [ ] Cursor remains accurate after wraps and resize.
- [ ] Alternate-screen applications return to the normal screen.
- [ ] Scrollback does not duplicate or corrupt visible rows.
- [ ] Selection and copy work.
- [ ] `Ctrl+C` copies a selection when one exists.
- [ ] `Ctrl+C` interrupts the child when no selection exists.
- [ ] Large paste/input preserves FIFO byte order.
- [ ] Continuous output does not freeze the desktop.
- [ ] Output continues to drain while Terminal is minimized.
- [ ] DEC mouse pass-through works when requested by the child.
- [ ] RetroTUI retains mouse ownership when the child does not request it.
- [ ] Closing Terminal terminates the child or visibly reports a failed close.

### Windows-native ConPTY

- [ ] Shell starts in the requested working directory.
- [ ] Inherited environment variables remain available.
- [ ] Extra environment values override or extend inherited values.
- [ ] Resize reaches ConPTY.
- [ ] Interrupt and terminate behavior is observable.
- [ ] Closing the window does not leave the child process alive.
- [ ] A failed close is reported instead of silently discarding backend state.

## Unicode, color and layout

- [ ] ASCII and box-drawing characters align.
- [ ] CJK and other wide characters do not split borders or cursor positions.
- [ ] Combining characters do not crash drawing paths.
- [ ] Emoji behavior is acceptable or documented.
- [ ] Eight-color mode remains readable.
- [ ] Higher-color modes map themes correctly.
- [ ] Limited color-pair capacity degrades without invalid pair access.
- [ ] Small host terminal dimensions do not crash rendering.

## Result log template

```text
Environment:
Host OS/version:
Terminal host/emulator:
Connection/nesting:
Date:
RetroTUI version:
RetroTUI commit:
Python:
TERM/COLORTERM:
Locale/encoding:
Color capacity:
Mouse backend:

Repository QA:
unittest:
pytest:
Signal/lifecycle stress:

Startup/shutdown:
Keyboard:
Mouse:
Resize:
Unicode:
Colors:
File Manager:
Notepad:
Embedded Terminal:
Bundled plugins:

Classification: Supported | Partially supported | Not supported | Incomplete

Observed issues:
- 

Limitations/exclusions:
- 

Notes:
- 
```

## Recorded results

### Windows + MobaXterm SSH to VPS — historical partial result

```text
Environment: Windows + MobaXterm SSH to VPS
Host: instance-20260202-1816
Date: 2026-02-24
TERM: xterm
Colors: 8 reported; 256-color terminfo available

Signal/lifecycle stress: PASS for repeated SIGINT, SIGTERM and SIGHUP
Automated QA: not captured
Interactive smoke: not completed
Classification: Incomplete / historical signal-only evidence

Observed issue:
- MobaXterm negotiated TERM=xterm by default, limiting advertised color depth.
```

## Pass criteria for v0.9.6

An environment can be marked supported only when:

- startup and shutdown are reproducible;
- keyboard, mouse and resize are usable;
- Unicode and color behavior are documented;
- File Manager, Notepad and Terminal complete the required checks;
- the embedded terminal is usable for the declared common TUI applications;
- no unresolved critical or high defect contradicts the support claim;
- limitations and skipped checks are explicit.

The milestone closes when every target environment is supported, partially supported, not supported, or explicitly untested with a reason, and all public support claims match those classifications.
