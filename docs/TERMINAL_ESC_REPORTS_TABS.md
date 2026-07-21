# Terminal ESC dispatch, reports and tab stops

This cut completes the basic VT format-effectors that sit above the Unicode
physical-cell and DEC scrolling-region layers.

## Single-byte ESC dispatch

The ANSI parser now emits explicit `ESC` events for:

- `IND` (`ESC D`): index one row without changing the column;
- `NEL` (`ESC E`): index one row and return to column zero;
- `RI` (`ESC M`): reverse index, scrolling the active region downward at its top;
- `HTS` (`ESC H`): set a horizontal tab stop at the current physical column;
- `DECSC` / `DECRC` (`ESC 7` / `ESC 8`): save and restore cursor position.

Unknown single-byte ESC commands remain safely consumed.

## Horizontal tabulation

Default stops are installed every eight physical columns. `HT` moves the
cursor to the next stop without writing spaces or changing cells. The terminal
also implements:

- `CHT` (`CSI Ps I`);
- `CBT` (`CSI Ps Z`);
- `TBC` current stop (`CSI g` / `CSI 0 g`);
- `TBC` all stops (`CSI 3 g`).

Tab stops are terminal-wide rather than tied to normal or alternate screen.
They are clipped when the viewport shrinks. New default stops are seeded when
it expands unless the child explicitly cleared all stops.

## Device status reports

- `CSI 5 n` replies with `CSI 0 n`.
- `CSI 6 n` replies with cursor position (`CPR`).
- DEC-private `CSI ? 5 n` and `CSI ? 6 n` receive private-form replies.
- CPR row numbering follows `DECOM`: screen-relative when reset and relative to
  the scrolling region origin when set.

Responses are written directly to the existing PTY child and do not alter
scrollback position or create a new session.

## Deliberate follow-ups

This cut does not implement primary/secondary device attributes, terminal
parameter reports, selective erase, full DECSC rendition restoration, or
256-color/true-color SGR.
