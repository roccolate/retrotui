import types
from unittest import mock

from retrotui.core.platform import mouse_backend


def test_normalize_mouse_payload_invalid_event_returns_none():
    app = types.SimpleNamespace()
    assert mouse_backend.normalize_mouse_payload(app, None) is None


def test_normalize_mouse_payload_infers_motion_without_report_flag():
    app = types.SimpleNamespace(
        mouse_backend="gpm",
        _last_mouse_pos=(10, 10),
        button1_pressed=True,
    )

    event = (0, 12, 11, 0, 0)
    result = mouse_backend.normalize_mouse_payload(app, event)

    assert result is not None
    assert result["inferred_motion"] is True
    assert result["has_motion"] is True


def test_normalize_mouse_payload_infers_right_click_for_gpm_press_release():
    app = types.SimpleNamespace(
        mouse_backend="gpm",
        _last_mouse_pos=None,
        button1_pressed=False,
    )

    right_pressed = getattr(mouse_backend.curses, "BUTTON3_PRESSED", 0)
    if right_pressed == 0:
        # Skip on platforms exposing no BUTTON3_* constants in curses.
        return

    event = (0, 5, 6, 0, right_pressed)
    result = mouse_backend.normalize_mouse_payload(app, event)

    assert result is not None
    assert result["inferred_right_click"] is True
    assert result["right_click"] is True


def test_normalize_mouse_payload_marks_passive_noop_motion():
    app = types.SimpleNamespace(
        mouse_backend="sgr",
        _last_mouse_pos=None,
        button1_pressed=False,
        click_flags=0xFFFF,
        scroll_down_mask=0,
    )

    report_motion = getattr(mouse_backend.curses, "REPORT_MOUSE_POSITION", 0)
    event = (0, 20, 21, 0, report_motion)
    result = mouse_backend.normalize_mouse_payload(app, event)

    assert result is not None
    assert result["is_motion"] is True
    assert result["is_passive_noop"] is True


def test_normalize_mouse_payload_treats_right_press_as_right_click_for_sgr():
    app = types.SimpleNamespace(
        mouse_backend="sgr",
        _last_mouse_pos=None,
        button1_pressed=False,
    )

    right_pressed = getattr(mouse_backend.curses, "BUTTON3_PRESSED", 0)
    if right_pressed == 0:
        return

    event = (0, 7, 8, 0, right_pressed)
    result = mouse_backend.normalize_mouse_payload(app, event)

    assert result is not None
    assert result["right_click"] is True
    assert result["inferred_right_click"] is False


def test_normalize_mouse_payload_uses_forced_env_backend_when_app_has_none():
    app = types.SimpleNamespace(
        _last_mouse_pos=None,
        button1_pressed=False,
    )
    event = (0, 1, 1, 0, 0)

    with mock.patch.dict(mouse_backend.os.environ, {"RETROTUI_MOUSE_BACKEND": "gpm"}, clear=False):
        result = mouse_backend.normalize_mouse_payload(app, event)

    assert result is not None
    assert result["backend"] == "gpm"


def test_resolve_mouse_backend_prefers_explicit_app_backend():
    app = types.SimpleNamespace(mouse_backend="GPM")
    backend = mouse_backend.resolve_mouse_backend(app, {"TERM": "xterm-256color"})
    assert backend == "gpm"


def test_resolve_mouse_backend_uses_env_override_when_app_backend_invalid():
    app = types.SimpleNamespace(mouse_backend="legacy")
    backend = mouse_backend.resolve_mouse_backend(
        app,
        {"RETROTUI_MOUSE_BACKEND": "sgr", "TERM": "linux"},
    )
    assert backend == "sgr"


def test_resolve_mouse_backend_defaults_to_gpm_on_linux_console():
    app = types.SimpleNamespace()
    backend = mouse_backend.resolve_mouse_backend(app, {"TERM": "linux"})
    assert backend == "gpm"


def test_resolve_mouse_backend_returns_fallback_when_no_hints():
    app = types.SimpleNamespace(mouse_backend="")
    backend = mouse_backend.resolve_mouse_backend(app, {})
    assert backend == "fallback"


def test_normalize_mouse_payload_detects_scroll_up_with_button4_clicked():
    app = types.SimpleNamespace(
        mouse_backend="sgr",
        _last_mouse_pos=None,
        button1_pressed=False,
    )

    b4_clicked = getattr(mouse_backend.curses, "BUTTON4_CLICKED", 0)
    if b4_clicked == 0:
        return

    result = mouse_backend.normalize_mouse_payload(app, (0, 3, 4, 0, b4_clicked))
    assert result is not None
    assert result["scroll_up"] is True


def test_normalize_mouse_payload_detects_scroll_down_with_button5_clicked_default_mask():
    app = types.SimpleNamespace(
        mouse_backend="sgr",
        _last_mouse_pos=None,
        button1_pressed=False,
    )

    b5_clicked = getattr(mouse_backend.curses, "BUTTON5_CLICKED", 0)
    if b5_clicked == 0:
        return

    result = mouse_backend.normalize_mouse_payload(app, (0, 3, 4, 0, b5_clicked))
    assert result is not None
    assert result["scroll_down"] is True
