"""Interactive mouse debugger for TTY/terminal sessions.

Shows both raw curses mouse masks and normalized RetroTUI semantics so
cross-backend issues (SGR/GPM/fallback) are easier to diagnose.
"""

import curses
import os
import types

from retrotui.core.platform.mouse_backend import normalize_mouse_payload


def _build_flag_catalog():
    """Return sorted mouse flag names/values exported by curses."""
    names = []
    for attr in dir(curses):
        if not (attr.startswith("BUTTON") or attr == "REPORT_MOUSE_POSITION"):
            continue
        value = getattr(curses, attr, 0)
        if isinstance(value, int) and value:
            names.append((attr, value))
    names.sort(key=lambda item: item[1])
    return names


def _decode_flags(bstate, flag_catalog):
    """Return all symbolic flag names present in *bstate*."""
    matched = []
    for name, value in flag_catalog:
        if bstate & value:
            matched.append(name)
    return matched


def _update_button_state(app_state, norm):
    """Mirror the same button-state tracking used by mouse_router."""
    if norm.get("button1_pressed"):
        app_state.button1_pressed = True
    elif norm.get("button1_released"):
        app_state.button1_pressed = False
    elif (norm.get("button1_clicked") or norm.get("button1_double")) and not norm.get("is_motion"):
        app_state.button1_pressed = False


def _norm_summary(norm):
    """Compact human-readable normalized semantics."""
    return (
        f"backend={norm.get('backend')} "
        f"motion={int(bool(norm.get('is_motion')))} "
        f"drag={int(bool(norm.get('is_drag')))} "
        f"right={int(bool(norm.get('right_click')))} "
        f"scroll_up={int(bool(norm.get('scroll_up')))} "
        f"scroll_down={int(bool(norm.get('scroll_down')))} "
        f"inferred_motion={int(bool(norm.get('inferred_motion')))} "
        f"inferred_right={int(bool(norm.get('inferred_right_click')))} "
        f"button1_down={int(bool(norm.get('button1_down')))}"
    )


def main(stdscr):
    curses.curs_set(0)
    curses.noecho()
    curses.cbreak()
    stdscr.keypad(True)

    requested_mask = curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION
    new_mask, _old_mask = curses.mousemask(requested_mask)

    # Match RetroTUI setup for SGR terminals.
    print("\033[?1002h", end="", flush=True)
    print("\033[?1006h", end="", flush=True)

    app_state = types.SimpleNamespace(
        mouse_backend=str(os.environ.get("RETROTUI_MOUSE_BACKEND", "")).strip().lower(),
        _last_mouse_pos=None,
        button1_pressed=False,
        click_flags=(
            getattr(curses, "BUTTON1_CLICKED", 0)
            | getattr(curses, "BUTTON1_PRESSED", 0)
            | getattr(curses, "BUTTON1_DOUBLE_CLICKED", 0)
        ),
        scroll_down_mask=(
            getattr(curses, "BUTTON5_PRESSED", 0)
            | getattr(curses, "BUTTON5_CLICKED", 0)
            or 0x200000
        ),
    )

    flag_catalog = _build_flag_catalog()

    stdscr.clear()
    stdscr.addstr(0, 0, "RetroTUI Mouse Debugger (Ctrl+C to exit)")
    stdscr.addstr(1, 0, f"Mouse Mask: {new_mask:x} (Requested: {requested_mask:x})")
    stdscr.addstr(2, 0, "Events: raw flags + normalized semantics")
    stdscr.refresh()

    row = 3
    max_rows = max(4, curses.LINES - 1)

    while True:
        try:
            key = stdscr.getch()
            if key != curses.KEY_MOUSE:
                if key == 3:
                    break
                continue

            try:
                raw_event = curses.getmouse()
                norm = normalize_mouse_payload(app_state, raw_event)
            except curses.error:
                continue

            if norm is None:
                continue

            _update_button_state(app_state, norm)
            app_state._last_mouse_pos = (norm.get("mx"), norm.get("my"))

            bstate = int(norm.get("bstate") or 0)
            raw_flags = _decode_flags(bstate, flag_catalog)
            raw_desc = "|".join(raw_flags) if raw_flags else "-"

            msg = (
                f"x={norm.get('mx')}, y={norm.get('my')}, "
                f"bstate=0x{bstate:x} ({raw_desc}) | {_norm_summary(norm)}"
            )

            rows, cols = stdscr.getmaxyx()
            if row >= max_rows or row >= rows:
                row = 3
            stdscr.move(row, 0)
            stdscr.clrtoeol()
            stdscr.addstr(row, 0, msg[: max(1, cols - 1)])
            stdscr.refresh()
            row += 1
        except KeyboardInterrupt:
            break


if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass
