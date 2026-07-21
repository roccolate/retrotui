# Terminal Unicode Cell Model

RetroTUI stores terminal output as physical screen columns rather than Python
string indices. This document defines the Unicode rules used by the embedded
terminal after the Unicode-cell hardening slice.

## Cell representation

The public compatibility shape remains a two-item tuple:

```python
(text, curses_attribute)
```

One narrow glyph occupies one tuple. A glyph whose terminal width is two stores
its text in the leading tuple and reserves the next physical column with:

```python
("", same_attribute)
```

The empty string is an internal continuation sentinel. It is never copied to the
clipboard and it is not emitted as output text.

## Width source

RetroTUI uses the Python `wcwidth` package for terminal display width. The
dependency is bounded below by the release used to implement this model and
below the next major version.

The engine distinguishes:

- width `1`: ordinary printable cell;
- width `2`: CJK, wide emoji and other double-column glyphs;
- width `0`: combining marks, variation selectors and joiners;
- width `-1`: control or non-printable codepoints, which are ignored by the
  printable-cell writer.

## Combining and joined sequences

Zero-width codepoints append to the preceding leading cell and do not advance
the cursor. Variation selectors may expand a previously narrow glyph to two
columns; when that happens, the adjacent column is reserved atomically.

A codepoint following a zero-width joiner is merged into the previous stored
sequence. This is intentionally a conservative grapheme-like model rather than
a complete terminal implementation of every Unicode segmentation rule.

## Autowrap

DEC private mode `?7h` enables autowrap and `?7l` disables it.

With autowrap enabled:

- a cursor immediately beyond the right edge wraps before the next printable
  codepoint;
- a width-two glyph at the last column wraps before it is written;
- bottom-edge wrapping scrolls through the normal buffer and its scrollback
  sink.

With autowrap disabled:

- the cursor is clamped to the last physical column;
- later narrow glyphs overwrite that column;
- a width-two glyph with only one column available is represented by the
  replacement character instead of creating a half glyph.

## Invariants

The buffer repairs these invariants after deletion, direct legacy assignment and
resize operations:

- every continuation has exactly one width-two leading cell immediately before
  it;
- a width-two leading cell always has its continuation;
- clearing or deleting one half clears or removes the whole glyph;
- shrinking a row never leaves a half-wide glyph;
- backspace from a continuation lands on the leading column.

## Rendering, cursor and selection

Rendering still batches adjacent cells with the same attribute. Concatenating a
width-two leading string and its empty continuation preserves the correct
physical width, so later runs begin at the proper column.

Selection coordinates remain physical screen columns. Copying slices the cell
list first and only then converts it to text, preventing a wide glyph from
shifting the selected range. A cursor positioned on a continuation column is
drawn over the leading glyph.

## Deliberate limits

This slice does not add:

- 256-color or true-color SGR;
- bidi reordering;
- font fallback;
- configurable ambiguous-width policy;
- complete emoji grapheme conformance across every terminal vendor.

Those remain independent capability decisions and must not be advertised by the
terminfo profile until implemented and tested.
