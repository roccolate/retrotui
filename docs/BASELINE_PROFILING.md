# RetroTUI Baseline Profiling

This guide defines a repeatable baseline for Fase 0 metrics.

## Scope

Capture at least:

- Startup time (`boot_ms`)
- Full-frame redraw behavior (`redraw_ratio`)
- Partial menu-clock refreshes (`clock_refreshes`)
- Background and window update cost (`background_ms`, `tick_ms`, `max_tick_ms`)
- Render/dispatch worst cases (`max_draw_ms`, `max_dispatch_ms`)
- Redraw causes (`invalidations_notification`, `invalidations_tick`, `invalidations_input`)
- Approximate idle wait time (`input_wait_ms`)
- CPU and RAM from host process monitor

## Enable Instrumentation

Set env vars before launch:

```bash
export RETROTUI_DEBUG=1
export RETROTUI_PROFILE=1
export RETROTUI_PROFILE_INTERVAL=5
```

PowerShell:

```powershell
$env:RETROTUI_DEBUG='1'
$env:RETROTUI_PROFILE='1'
$env:RETROTUI_PROFILE_INTERVAL='5'
```

## What to Collect

Look for log lines:

- `startup boot_ms=...`
- `profile ... redraw_ratio=...`
- `profile_final ... redraw_ratio=... clock_refreshes=... tick_ms=...`

`redraws` and `redraw_ratio` count only complete frames. The menu clock uses a
partial curses refresh and is reported separately as `clock_refreshes`. This
keeps before/after redraw comparisons stable when the clock is visible.

Optional extractor (from saved log file):

```bash
python tools/baseline_extract.py docs/baseline/run.log --terminal "linux-tty"
```

Compare baseline vs post-change:

```bash
python tools/baseline_compare.py docs/baseline/before.log docs/baseline/after.log --terminal "linux-tty"
```

And record host stats manually:

- CPU `%` in idle (no interaction for 60s)
- RAM footprint in idle

## Baseline Table (Template)

| Date | Host | Terminal | Boot ms | Redraw ratio | CPU idle % | RAM idle MB | Notes |
|---|---|---|---:|---:|---:|---:|---|
| YYYY-MM-DD | machine-name | linux tty / tmux / ssh |  |  |  |  |  |
| YYYY-MM-DD | machine-name | linux tty / tmux / ssh |  |  |  |  |  |

## Recommended Run Protocol

1. Cold start RetroTUI and wait 10s.
2. Leave idle 60s.
3. Perform a fixed interaction script (open file manager, open notepad, move window).
4. Exit and save logs.

## Storage

Store captured logs and filled tables under:

- `docs/baseline/`

Use one file per environment and date.
