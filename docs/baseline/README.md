# Baseline Evidence Folder

Store reproducible runtime evidence for Fase 0 here.

## Suggested Files

- `baseline_<host>_<terminal>_<date>.log`
- `post_<host>_<terminal>_<date>.log`
- `matrix_<date>.md` (manual TTY test notes)

## Quick Flow

1. Capture baseline log with `RETROTUI_DEBUG=1 RETROTUI_PROFILE=1`.
2. Capture post-change log with same protocol.
3. Extract each run:

```bash
python tools/baseline_extract.py docs/baseline/baseline_host_tty_2026-02-24.log --terminal "linux-tty"
python tools/baseline_extract.py docs/baseline/post_host_tty_2026-02-24.log --terminal "linux-tty"
```

4. Compare:

```bash
python tools/baseline_compare.py \
  docs/baseline/baseline_host_tty_2026-02-24.log \
  docs/baseline/post_host_tty_2026-02-24.log \
  --terminal "linux-tty"
```
