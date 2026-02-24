# RetroTUI TTY Test Matrix

Use this checklist to validate RetroTUI behavior across terminals/backends.

## 1) Test Environments

Mark each environment you ran:

- [ ] Linux Mint `tty` real (`Ctrl+Alt+F3`, `TERM=linux`)
- [ ] Linux Mint `tmux` over real `tty`
- [ ] Linux Mint GUI terminal (GNOME Terminal/Konsole)
- [ ] Linux Mint `ssh` -> VPS
- [x] Windows + MobaXterm `ssh` -> VPS
- [ ] Windows Terminal (PowerShell/OpenSSH) `ssh` -> VPS

## 2) Baseline Info (per environment)

Record before running checks:

```bash
echo "TERM=$TERM"
echo "TMUX=$TMUX"
tput colors
python -V
uname -a
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

## 5) Result Log Template

Copy/paste one block per environment:

```text
Environment:
Host:
Date:
TERM:
TMUX:
Colors (tput):

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

## 6) Pass Criteria

- No terminal corruption after stress runs.
- No accidental exit to host shell from `Ctrl+C` in normal session.
- Mouse behavior consistent enough for daily workflow (click/drag/right-click).
- Selection behavior consistent (outside click clears selection).
