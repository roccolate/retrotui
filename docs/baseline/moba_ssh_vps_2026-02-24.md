# RetroTUI Evidence: MobaXterm SSH -> VPS

Date: 2026-02-24
Environment: Windows + MobaXterm `ssh` -> Ubuntu VPS
Host: `instance-20260202-1816`

## Baseline Probe

```text
uname -a
Linux instance-20260202-1816 6.17.0-1007-oracle #7~24.04.1-Ubuntu SMP Tue Feb  3 22:09:11 UTC 2026 aarch64 aarch64 aarch64 GNU/Linux

TERM=xterm
TMUX=
tput colors -> 8
tput -T xterm-256color colors -> 256
infocmp xterm-256color -> terminfo ok
```

Observation:
- VPS has correct `xterm-256color` terminfo.
- Session negotiated `TERM=xterm` (8 colors) from MobaXterm.

## Signal Stress

Command:

```bash
python3 tools/tty_signal_stress.py --iterations 5
```

Result:

```text
Command: /usr/bin/python3 -m retrotui
Signals: SIGINT, SIGTERM, SIGHUP
Iterations per signal: 5
[OK] SIGINT iter=1 rc=0 detail=SIGINT kept process alive; follow-up SIGTERM exited cleanly
[OK] SIGINT iter=2 rc=0 detail=SIGINT kept process alive; follow-up SIGTERM exited cleanly
[OK] SIGINT iter=3 rc=0 detail=SIGINT kept process alive; follow-up SIGTERM exited cleanly
[OK] SIGINT iter=4 rc=0 detail=SIGINT kept process alive; follow-up SIGTERM exited cleanly
[OK] SIGINT iter=5 rc=0 detail=SIGINT kept process alive; follow-up SIGTERM exited cleanly
[OK] SIGTERM iter=1 rc=0 detail=process exited after SIGTERM
[OK] SIGTERM iter=2 rc=0 detail=process exited after SIGTERM
[OK] SIGTERM iter=3 rc=0 detail=process exited after SIGTERM
[OK] SIGTERM iter=4 rc=0 detail=process exited after SIGTERM
[OK] SIGTERM iter=5 rc=0 detail=process exited after SIGTERM
[OK] SIGHUP iter=1 rc=0 detail=process exited after SIGHUP
[OK] SIGHUP iter=2 rc=0 detail=process exited after SIGHUP
[OK] SIGHUP iter=3 rc=0 detail=process exited after SIGHUP
[OK] SIGHUP iter=4 rc=0 detail=process exited after SIGHUP
[OK] SIGHUP iter=5 rc=0 detail=process exited after SIGHUP
Signal stress finished successfully.
```
