"""Mouse backend normalization helpers (SGR/GPM/fallback)."""

import curses
import os


def normalize_mouse_payload(app, event):
    """Normalize raw curses mouse payload and infer missing semantics when possible.

    Returns a dict with normalized fields or None when payload is invalid.
    """
    try:
        _, mx, my, _, bstate = event
    except (TypeError, ValueError):
        return None

    report_flag = getattr(curses, "REPORT_MOUSE_POSITION", 0)
    b1_pressed = getattr(curses, "BUTTON1_PRESSED", 0)
    b1_released = getattr(curses, "BUTTON1_RELEASED", 0)
    b1_clicked = getattr(curses, "BUTTON1_CLICKED", 0)
    b1_double = getattr(curses, "BUTTON1_DOUBLE_CLICKED", 0)
    b3_clicked = getattr(curses, "BUTTON3_CLICKED", 0)
    b3_pressed = getattr(curses, "BUTTON3_PRESSED", 0)
    b3_released = getattr(curses, "BUTTON3_RELEASED", 0)
    b4_pressed = getattr(curses, "BUTTON4_PRESSED", 0)
    b5_pressed = getattr(curses, "BUTTON5_PRESSED", 0)

    # Backend hint: explicit app override wins; Linux console defaults to GPM-like.
    backend = getattr(app, "mouse_backend", None)
    if not backend:
        backend = "gpm" if os.environ.get("TERM") == "linux" else "sgr"

    has_motion = bool(bstate & report_flag)
    last_pos = getattr(app, "_last_mouse_pos", None)
    button1_down = bool((bstate & b1_pressed) or getattr(app, "button1_pressed", False))

    # In some GPM streams motion flag is absent; infer movement from pointer delta while button1 is down.
    inferred_motion = False
    if not has_motion and last_pos is not None and button1_down:
        inferred_motion = (mx, my) != tuple(last_pos)

    # In some GPM setups right-click may come as press/release without CLICKED flag.
    right_click = bool(bstate & b3_clicked)
    inferred_right_click = False
    if not right_click and backend == "gpm" and (bstate & (b3_pressed | b3_released)):
        inferred_right_click = True

    is_click_like = bool(
        bstate
        & getattr(
            app,
            "click_flags",
            b1_clicked | b1_pressed | b1_double,
        )
    )
    is_motion = has_motion or inferred_motion
    is_drag = is_motion and button1_down
    scroll_up = bool(bstate & b4_pressed)
    scroll_down = bool(
        bstate
        & getattr(
            app,
            "scroll_down_mask",
            b5_pressed,
        )
    )
    right_click_effective = right_click or inferred_right_click

    return {
        "mx": mx,
        "my": my,
        "bstate": bstate,
        "backend": backend,
        "has_motion": is_motion,
        "inferred_motion": inferred_motion,
        "right_click": right_click_effective,
        "inferred_right_click": inferred_right_click,
        "button1_pressed": bool(bstate & b1_pressed),
        "button1_released": bool(bstate & b1_released),
        "button1_clicked": bool(bstate & b1_clicked),
        "button1_double": bool(bstate & b1_double),
        "button1_down": button1_down,
        "is_drag": is_drag,
        "is_motion": is_motion,
        "is_click_like": is_click_like,
        "scroll_up": scroll_up,
        "scroll_down": scroll_down,
        "is_passive_noop": is_motion and not (
            button1_down
            or is_click_like
            or right_click_effective
            or scroll_up
            or scroll_down
        ),
    }
