# Terminal DEC screen controls

This cut adds the first region-aware VT screen operations on top of the Unicode
physical-cell model.

## Implemented

- `DECSTBM` (`CSI top;bottom r`) with independent margins per normal and
  alternate screen buffer.
- `DECOM` origin mode (`CSI ? 6 h` / `CSI ? 6 l`). Cursor addressing becomes
  relative to the top margin while origin mode is enabled.
- CSI cursor save and restore (`CSI s` / `CSI u`).
- Insert character (`ICH`, `CSI Ps @`).
- Delete character (`DCH`, `CSI Ps P`).
- Erase character (`ECH`, `CSI Ps X`).
- Insert line (`IL`, `CSI Ps L`).
- Delete line (`DL`, `CSI Ps M`).
- `?1049` saves the normal-screen cursor, clears and homes the alternate
  screen, then restores the normal cursor on exit.
- Resize preserves valid margins and clamps saved cursor coordinates.

## Unicode safety

Character editing uses physical columns. Operations that intersect the tail of
a double-width glyph expand to the leading cell so no orphan continuation is
left in the row. Resizing sanitizes rows after clipping.

## Scrollback ownership

Only a full-screen upward scroll emits a row into normal-screen scrollback. A
partial DEC scrolling region moves rows inside the visible grid and never
creates history entries.

## Deliberate follow-ups

The following remain separate work:

- `IND`, `RI` and `NEL` ESC dispatch;
- configurable tab stops;
- device-status and cursor-position reports;
- selective erase/protected cells;
- 256-color and true-color SGR.
