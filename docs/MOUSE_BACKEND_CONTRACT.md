# RetroTUI Mouse Backend Contract

This document defines the normalized mouse contract used by `mouse_backend.normalize_mouse_payload`.

## Backend Resolution

Resolution order:

1. `app.mouse_backend` when set to `gpm` or `sgr` (case-insensitive).
2. `RETROTUI_MOUSE_BACKEND` env var when set to `gpm` or `sgr`.
3. `TERM=linux` -> `gpm`.
4. Any non-empty `TERM` -> `sgr`.
5. Otherwise -> `fallback`.

## Normalized Payload Fields

Required keys:

- `mx`, `my`: pointer coordinates.
- `bstate`: raw curses mask.
- `backend`: resolved backend (`gpm` | `sgr` | `fallback`).
- `is_click_like`: button-1 click-like event.
- `is_motion`: motion event (native or inferred).
- `is_drag`: motion while button-1 is down.
- `right_click`: right click semantic event.
- `scroll_up`, `scroll_down`: wheel events.
- `is_passive_noop`: motion without actionable semantics.

Compatibility flags:

- `inferred_motion`: true when drag motion is inferred by delta + button state.
- `inferred_right_click`: true when right click is inferred (not explicitly clicked).
- `button1_pressed`, `button1_released`, `button1_clicked`, `button1_double`, `button1_down`.

## Cross-Backend Rules

- Drag must work even when backend omits explicit motion flags (`inferred_motion` path).
- Right-click must work with `BUTTON3_CLICKED` and with press/release-only streams.
- Scroll must accept both `BUTTON4/5_PRESSED` and `BUTTON4/5_CLICKED`.
- Passive motion should not trigger redraw-heavy routes (`is_passive_noop=True`).
