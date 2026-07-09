# RetroTUI TTY Test Matrix

Use this checklist to validate RetroTUI behavior across terminals/backends.

## v0.9.6 Certification Summary

Last updated: 2026-07-09
RetroTUI version tested: 0.9.5 / 0.9.6-dev

### Legend

- ✅ Supported
- ⚠️ Partially supported
- ❌ Not supported
- 🧪 Not tested yet

### Summary

| Environment | Startup | Keyboard | Mouse | Resize | Unicode | Colors | Embedded Terminal | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Linux TTY | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | Pending |
| Linux GUI terminal | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | Pending |
| SSH | ⚠️ | 🧪 | 🧪 | 🧪 | 🧪 | ⚠️ | 🧪 | Partial: MobaXterm SSH signal stress recorded only |
| tmux | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | Pending |
| screen | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | Pending |
| WSL + Windows Terminal | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | Pending |
| Windows native | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | 🧪 | Pending |

### v0.9.6 rules

- Record every environment in the result log below.
- Do not mark an environment ✅ unless startup, keyboard, mouse, resize, Unicode, colors, and embedded terminal behavior have all been checked.
- If a terminal cannot support a behavior reliably, mark it ⚠️ or ❌ and document the limitation.
- Keep README and ROADMAP aligned with the support level shown here.

## 1) Test Environments

Mark each environment you ran:

- [ ] Linux Mint `tty` real (`Ctrl+Alt+F3`, `TERM=linux`)
- [ ] Linux Mint `tmux` over real `tty`
- [ ] Linux Mint GUI terminal (GNOME Terminal/Konsole)
- [ ] Linux Mint `ssh` -> VPS
- [x] Windows + MobaXterm `ssh` -> VPS
- [ ] Windows Terminal (PowerShell/OpenSSH) `ssh` -> VPS
- [ ] Windows Terminal + WSL2
- [ ] Windows native Python + `pywinpty` / ConPTY
- [ ] `screen`

## 2) Baseline Info (per environment)

Record before running checks:

```bash
echo "TERM=$TERM"
echo "TMUX=$TMUX"
echo "STY=$STY"
tput colors
python -V
uname -a
```

For Windows native, also record:

```powershell
python -V
$PSVersionTable.PSVersion
```

## 3) Automated Stress

### A. Signal stress (required)

```bash
python tools/tty_signal_stress.py --iterations 5
```

Mark:

- [x] PASS (MobaXterm SSH -> VPS, 2026-02-24, `python3 tools/tty_signal_stress.py --iterations 5`)
- [ ] FAIL (attach output)

### B. QA suite (recommended)

```bash
python tools/qa.py
```

Mark:

- [ ] PASS
- [ ] FAIL (attach output)

## 4) Interactive Smoke Stress (required)

Run RetroTUI:

```bash
python -m retrotui
```

Optional mouse diagnostics (recommended when drag/click behavior differs by terminal):

```bash
python tools/debug_mouse.py
```

Perform each test for 2-3 minutes and mark PASS/FAIL:

- [ ] Open/close windows repeatedly (10+ cycles)
- [ ] Drag and resize windows continuously
- [ ] Right click menus (desktop + window body)
- [ ] Text selection + click outside clears selection
- [ ] `Ctrl+C` in Terminal:
  - [ ] With selection: copies selection
  - [ ] Without selection: interrupts foreground process only
- [ ] `Ctrl+Q` policy:
  - [ ] With context/menu layers open: closes layer first, does not exit app
  - [ ] With clean session: opens global exit flow
- [ ] `Esc` policy:
  - [ ] With menu layer open: closes active layer
  - [ ] Without menu layer: reaches focused app (not globally swallowed)
- [ ] Paste paths/text (`Ctrl+V`) in Terminal and Notepad
- [ ] Terminal resize redraw is stable (no corruption)
- [ ] Exit and relaunch RetroTUI cleanly 5 times
- [ ] Mouse debugger reports expected raw flags and normalized semantics during click/drag

## 5) Embedded Terminal Focus Tests

Run these from a RetroTUI Terminal window where the tools are available:

```bash
nano
vim
less README.md
top
htop
mc
printf '\033[31mred\033[0m normal\n'
printf '\033[?1049hALT SCREEN\033[?1049lNORMAL\n'
```

Check:

- [ ] Cursor position is accurate
- [ ] Alt-screen returns to normal screen
- [ ] Scrollback does not corrupt live screen
- [ ] Mouse pass-through works when the child app enables DEC mouse reporting
- [ ] RetroTUI keeps mouse control when the child app does not request mouse reporting
- [ ] Resize updates terminal dimensions without corrupting buffers

## 6) Result Log Template

Copy/paste one block per environment:

```text
Environment:
Host:
Date:
TERM:
TMUX:
STY:
Colors (tput):
Python:
RetroTUI commit/version:

Startup:
Keyboard:
Mouse:
Resize:
Unicode:
Colors:
Embedded Terminal:
Signal stress:
QA:
Smoke:

Observed issues:
- 

Notes:
- 
```

Latest recorded run:

```text
Environment: Windows + MobaXterm ssh -> VPS
Host: instance-20260202-1816
Date: 2026-02-24
TERM: xterm
TMUX:
Colors (tput): 8 (xterm), 256 available via xterm-256color terminfo

Signal stress: PASS (SIGINT/SIGTERM/SIGHUP x5 all OK)
QA: N/A on remote capture
Smoke: Pending

Observed issues:
- Moba session negotiates TERM=xterm by default; limits color depth to 8.

Notes:
- Use `export TERM=xterm-256color` for current session when testing palette behavior.
```

## 7) Pass Criteria

- No terminal corruption after stress runs.
- No accidental exit to host shell from `Ctrl+C` in normal session.
- Mouse behavior consistent enough for daily workflow (click/drag/right-click).
- Selection behavior consistent (outside click clears selection).
- Embedded terminal supports common TUI apps well enough for daily use.
- Support claims in README and ROADMAP match this matrix.
