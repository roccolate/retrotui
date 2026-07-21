"""Unicode display-cell helpers for the embedded terminal."""

from __future__ import annotations

from collections.abc import Sequence

from wcwidth import wcwidth, wcswidth


CONTINUATION_TEXT = ""


def display_width(text: str) -> int:
    """Return terminal display width for one stored grapheme-like cell."""
    if not text:
        return 0
    width = wcswidth(str(text))
    if width < 0:
        return -1
    return min(width, 2)


def codepoint_width(ch: str) -> int:
    """Return the printable width of one codepoint."""
    if not ch:
        return 0
    return wcwidth(ch[0])


def is_continuation(cell) -> bool:
    """Return whether ``cell`` is the reserved tail of a wide glyph."""
    return bool(cell) and cell[0] == CONTINUATION_TEXT


def leading_cell_index(row: Sequence, col: int) -> int | None:
    """Resolve a physical column to the glyph-leading column."""
    if not 0 <= col < len(row):
        return None
    if not is_continuation(row[col]):
        return col
    index = col - 1
    while index >= 0 and is_continuation(row[index]):
        index -= 1
    return index if index >= 0 else None


def row_text(cells: Sequence) -> str:
    """Convert physical cells to plain text without continuation sentinels."""
    return "".join(cell[0] for cell in cells if cell and not is_continuation(cell))


def sanitize_row(cells: Sequence, default_attr: int = 0) -> list[tuple[str, int]]:
    """Remove orphan tails and half-wide glyphs from a physical row."""
    row = [(str(cell[0]), cell[1]) for cell in cells]
    blank = (" ", default_attr)
    for col, (text, attr) in enumerate(list(row)):
        if text == CONTINUATION_TEXT:
            lead = leading_cell_index(row, col)
            if lead is None or col != lead + 1 or display_width(row[lead][0]) != 2:
                row[col] = blank
            else:
                row[col] = (CONTINUATION_TEXT, row[lead][1])
            continue
        if display_width(text) == 2:
            if col + 1 >= len(row) or not is_continuation(row[col + 1]):
                row[col] = blank
            else:
                row[col + 1] = (CONTINUATION_TEXT, attr)
    return row
