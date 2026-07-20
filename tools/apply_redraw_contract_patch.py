#!/usr/bin/env python3
"""Apply the focused unified-redraw-contract patch."""
from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected one match in {path}, found {count}: {old!r}")
    file_path.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "retrotui/ui/window.py",
    "    needs_redraw = False\n",
    "    # Public runtime scheduling contract.\n"
    "    wants_periodic_tick = False\n"
    "    tick_when_hidden = False\n",
)

replace_once(
    "retrotui/plugins/base.py",
    "    PLUGIN_ID = None  # Set by loader from manifest\n\n"
    "    def __init__(self, title, x, y, w, h, **kwargs):\n",
    "    PLUGIN_ID = None  # Set by loader from manifest\n\n"
    "    @property\n"
    "    def wants_periodic_tick(self):\n"
    "        \"\"\"Return the public periodic scheduling request.\n\n"
    "        Older third-party plugins may still expose ``needs_redraw``.\n"
    "        Keep that compatibility at the plugin boundary; the core loop\n"
    "        only reads ``wants_periodic_tick``.\n"
    "        \"\"\"\n"
    "        explicit = self.__dict__.get(\"_wants_periodic_tick\")\n"
    "        if explicit is not None:\n"
    "            return bool(explicit)\n"
    "        legacy = type(self).__dict__.get(\"needs_redraw\")\n"
    "        if legacy is None:\n"
    "            return False\n"
    "        descriptor = getattr(legacy, \"__get__\", None)\n"
    "        if callable(descriptor):\n"
    "            return bool(descriptor(self, type(self)))\n"
    "        return bool(legacy)\n\n"
    "    @wants_periodic_tick.setter\n"
    "    def wants_periodic_tick(self, value):\n"
    "        self._wants_periodic_tick = bool(value)\n\n"
    "    def tick(self):\n"
    "        \"\"\"Example plugins redraw each scheduled periodic tick.\"\"\"\n"
    "        return bool(self.wants_periodic_tick)\n\n"
    "    def __init__(self, title, x, y, w, h, **kwargs):\n",
)

old_helpers = '''def _has_animated_windows(app):
    """Return True if any visible window requests periodic redraws."""
    for w in app.windows:
        if not getattr(w, "visible", True):
            continue
        if getattr(w, "needs_redraw", False):
            return True
    return False


def _tick_and_probe_windows(app):
    """Run per-window ``tick`` hooks and probe for live/animated windows.

    Combines the three separate ``app.windows`` walks (tick, live,
    animated) into a single iteration. The cost saving is the second
    and third walks, which previously ran every loop iteration even
    when no window had anything to do.
    """
    changed = False
    has_live = False
    has_animated = False
    for w in app.windows:
        visible = getattr(w, "visible", True)
        tick_when_hidden = bool(getattr(w, "tick_when_hidden", False))
        if not visible and not tick_when_hidden:
            continue

        tick = getattr(w, "tick", None)
        if callable(tick):
            try:
                tick_changed = bool(tick())
                # Hidden service ticks advance background state but do not
                # dirty the visual frame until the window becomes visible.
                if visible:
                    changed = tick_changed or changed
            except _INPUT_TIMEOUT_APPLY_ERRORS:
                LOGGER.debug("window tick failed", exc_info=True)

        # A service-ticked hidden terminal still needs the low-latency input
        # timeout so its PTY cannot fill while minimized.
        if not has_live:
            session = getattr(w, "_session", None)
            if session is not None and getattr(session, "running", False):
                has_live = True
        if visible and not has_animated and getattr(w, "_animated", False):
            has_animated = True
    return changed, has_live, has_animated
'''
new_helpers = '''def _has_periodic_windows(app):
    """Return True if any visible window requests periodic scheduling."""
    for window in app.windows:
        if not getattr(window, "visible", True):
            continue
        if bool(getattr(window, "wants_periodic_tick", False)):
            return True
    return False


def _tick_and_probe_windows(app):
    """Run update hooks and collect the public runtime scheduling signals.

    ``tick()`` is the only per-window redraw signal. A True return means
    visible state changed. ``wants_periodic_tick`` only selects a shorter
    polling cadence, while ``tick_when_hidden`` allows service progression.
    """
    changed = False
    has_live = False
    has_periodic = False
    for window in app.windows:
        visible = getattr(window, "visible", True)
        tick_when_hidden = bool(getattr(window, "tick_when_hidden", False))
        if not visible and not tick_when_hidden:
            continue

        tick = getattr(window, "tick", None)
        if callable(tick):
            try:
                tick_changed = bool(tick())
                if visible:
                    changed = tick_changed or changed
            except _INPUT_TIMEOUT_APPLY_ERRORS:
                LOGGER.debug("window tick failed", exc_info=True)

        if not has_live:
            session = getattr(window, "_session", None)
            if session is not None and getattr(session, "running", False):
                has_live = True
        if visible and not has_periodic:
            has_periodic = bool(
                getattr(window, "wants_periodic_tick", False)
            )
    return changed, has_live, has_periodic
'''
replace_once("retrotui/core/event_loop.py", old_helpers, new_helpers)

old_timeout = '''def _select_input_timeout_ms(app, *, has_live=None, has_animated=None):
    """Return the target input timeout for the current runtime state.

    ``has_live``/``has_animated`` may be supplied by the caller when it
    has already computed them for the redraw decision; otherwise the
    helpers are invoked on demand. Reusing the cached values avoids two
    extra ``app.windows`` walks per loop iteration.
    """
    idle = int(getattr(app, "input_timeout_idle_ms", TERMINAL_INPUT_TIMEOUT_MS))
    timeout_ms = max(1, idle)

    if has_live is None:
        has_live = _has_live_terminals(app)
    if has_animated is None:
        has_animated = _has_animated_windows(app)

    if has_live:
        live = int(
            getattr(
                app,
                "input_timeout_live_terminal_ms",
                TERMINAL_LIVE_INPUT_TIMEOUT_MS,
            )
        )
        return max(1, live)

    if has_animated:
        anim = int(
            getattr(
                app,
                "input_timeout_animated_ms",
                TERMINAL_ANIMATED_INPUT_TIMEOUT_MS,
            )
        )
        return max(1, min(timeout_ms, anim))
'''
new_timeout = '''def _select_input_timeout_ms(app, *, has_live=None, has_periodic=None):
    """Return the target input timeout for the current runtime state.

    Live services and periodic windows affect polling cadence only. Redraws
    remain controlled by ``tick()`` returns and app-level invalidation.
    """
    idle = int(getattr(app, "input_timeout_idle_ms", TERMINAL_INPUT_TIMEOUT_MS))
    timeout_ms = max(1, idle)

    if has_live is None:
        has_live = _has_live_terminals(app)
    if has_periodic is None:
        has_periodic = _has_periodic_windows(app)

    if has_live:
        live = int(
            getattr(
                app,
                "input_timeout_live_terminal_ms",
                TERMINAL_LIVE_INPUT_TIMEOUT_MS,
            )
        )
        return max(1, live)

    if has_periodic:
        periodic = int(
            getattr(
                app,
                "input_timeout_periodic_ms",
                getattr(
                    app,
                    "input_timeout_animated_ms",
                    TERMINAL_ANIMATED_INPUT_TIMEOUT_MS,
                ),
            )
        )
        return max(1, min(timeout_ms, periodic))
'''
replace_once("retrotui/core/event_loop.py", old_timeout, new_timeout)

old_loop = '''                # Single walk that (1) runs per-window ``tick`` hooks,
                # (2) detects live terminals, (3) detects animated
                # windows. Avoids 3× walks of ``app.windows`` per loop.
                _tick_changed, has_live, has_animated = _tick_and_probe_windows(app)
                if _tick_changed:
                    app._dirty = True
                # PTY output dirties the frame through ``tick_changed``.
                # Merely being alive is a polling concern, not a redraw reason.
                if has_animated:
                    app._dirty = True
                if getattr(app, '_dirty', True):
'''
new_loop = '''                # One walk collects the three independent contracts:
                # change, service liveness and periodic cadence.
                _tick_changed, has_live, has_periodic = _tick_and_probe_windows(app)
                if _tick_changed:
                    app._dirty = True
                if getattr(app, '_dirty', True):
'''
replace_once("retrotui/core/event_loop.py", old_loop, new_loop)
replace_once(
    "retrotui/core/event_loop.py",
    "                _apply_input_timeout(app, _select_input_timeout_ms(app, has_live=has_live, has_animated=has_animated))\n",
    "                _apply_input_timeout(\n"
    "                    app,\n"
    "                    _select_input_timeout_ms(\n"
    "                        app, has_live=has_live, has_periodic=has_periodic\n"
    "                    ),\n"
    "                )\n",
)

replace_once(
    "retrotui/apps/filemanager/window.py",
    "        self._preview_pending = set()\n",
    "        self._preview_pending = set()\n"
    "        self._preview_redraw_pending = False\n",
)
replace_once(
    "retrotui/apps/filemanager/window.py",
    "                    self.needs_redraw = True\n",
    "                    self._preview_redraw_pending = True\n",
)
replace_once(
    "retrotui/apps/filemanager/window.py",
    "    def _invalidate_preview_cache(self):\n"
    "        \"\"\"Clear the preview cache.\"\"\"\n"
    "        with self._preview_lock:\n"
    "            self._preview_cache = {'key': None, 'lines': []}\n",
    "    def _invalidate_preview_cache(self):\n"
    "        \"\"\"Clear the preview cache.\"\"\"\n"
    "        with self._preview_lock:\n"
    "            self._preview_cache = {'key': None, 'lines': []}\n"
    "            self._preview_redraw_pending = False\n\n"
    "    def tick(self):\n"
    "        \"\"\"Consume one completed asynchronous preview update.\"\"\"\n"
    "        with self._preview_lock:\n"
    "            changed = self._preview_redraw_pending\n"
    "            self._preview_redraw_pending = False\n"
    "        return changed\n",
)

# In-tree example plugins now publish only the new public scheduling name.
plugin_paths = (
    "examples/plugins/pomodoro/__init__.py",
    "examples/plugins/starwars-ascii/__init__.py",
    "examples/plugins/matrix-rain/__init__.py",
    "examples/plugins/network-monitor/__init__.py",
    "examples/plugins/game-of-life/__init__.py",
    "examples/plugins/ascii-aquarium/__init__.py",
    "examples/plugins/system-monitor/__init__.py",
)
for plugin_path in plugin_paths:
    path = Path(plugin_path)
    text = path.read_text(encoding="utf-8")
    if "needs_redraw" not in text:
        raise SystemExit(f"expected legacy redraw name in {plugin_path}")
    path.write_text(text.replace("needs_redraw", "wants_periodic_tick"), encoding="utf-8")

replace_once(
    "retrotui/apps/clock.py",
    "class ClockCalendarWindow(Window):\n    \"\"\"Small widget with digital clock and ASCII month calendar.\"\"\"\n",
    "class ClockCalendarWindow(Window):\n"
    "    \"\"\"Small widget with digital clock and ASCII month calendar.\"\"\"\n\n"
    "    wants_periodic_tick = True\n",
)
