# RetroTUI TTY Signal Stress

This document defines a reproducible manual stress check for runtime signal behavior.

## Goal

Validate that RetroTUI behaves correctly under repeated signals in real TTY sessions:

- `SIGINT`: session remains alive (mapped to in-app Ctrl+C).
- `SIGTERM` / `SIGHUP`: session exits cleanly.
- No terminal corruption after repeated runs.

## Prerequisites

- Linux host (POSIX environment).
- Run from an interactive TTY (`tty1`, `tty2`, etc.) or equivalent console session.
- Repository checked out with dependencies installed.

## Run

```bash
python tools/tty_signal_stress.py --iterations 5
```

Optional:

```bash
python tools/tty_signal_stress.py \
  --iterations 10 \
  --signals SIGINT,SIGTERM,SIGHUP \
  --startup-wait 1.0 \
  --shutdown-timeout 8.0
```

## Expected Output

- Per probe line:
  - `[OK] ...` for each signal/iteration.
- Final line:
  - `Signal stress finished successfully.`

If any line reports `[FAIL]`, capture:

- Terminal type and `$TERM`
- Host distro/version
- Exact command used
- The failing output lines

## Post-check (manual)

After script finishes:

1. Verify shell input still works normally.
2. Run `stty -a` and confirm expected TTY state.
3. Launch RetroTUI once manually (`python -m retrotui`) and confirm startup works.

## Exit Codes

- `0`: all probes passed.
- `1`: one or more probes failed.
- `2`: invalid usage or unsupported environment (non-POSIX / non-TTY).
