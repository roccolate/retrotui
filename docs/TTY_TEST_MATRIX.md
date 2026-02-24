# RetroTUI TTY Test Matrix

Use this checklist to validate RetroTUI behavior across terminals/backends.

## 1) Test Environments

Mark each environment you ran:

- [ ] Linux Mint `tty` real (`Ctrl+Alt+F3`, `TERM=linux`)
- [ ] Linux Mint `tmux` over real `tty`
- [ ] Linux Mint GUI terminal (GNOME Terminal/Konsole)
- [ ] Linux Mint `ssh` -> VPS
- [ ] Windows + MobaXterm `ssh` -> VPS
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

- [ ] PASS
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

## 6) Pass Criteria

- No terminal corruption after stress runs.
- No accidental exit to host shell from `Ctrl+C` in normal session.
- Mouse behavior consistent enough for daily workflow (click/drag/right-click).
- Selection behavior consistent (outside click clears selection).
