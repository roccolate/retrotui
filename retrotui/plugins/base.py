"""Base class for RetroTUI plugins."""
from ..ui.window import Window


class RetroApp(Window):
    """Ergonomic base class for plugin apps.

    Plugins subclass this and implement:
    - draw_content(stdscr, x, y, w, h): Draw app content in body area
    - handle_key(key): Handle keyboard input
    - handle_click(mx, my): Handle mouse clicks

    Metadata comes from plugin.toml manifest.
    """

    PLUGIN_ID = None  # Set by loader from manifest

    @property
    def wants_periodic_tick(self):
        """Return the public periodic scheduling request.

        Older third-party plugins may still expose ``needs_redraw``.
        Keep that compatibility at the plugin boundary; the core loop
        only reads ``wants_periodic_tick``.
        """
        explicit = self.__dict__.get("_wants_periodic_tick")
        if explicit is not None:
            return bool(explicit)
        legacy = type(self).__dict__.get("needs_redraw")
        if legacy is None:
            return False
        descriptor = getattr(legacy, "__get__", None)
        if callable(descriptor):
            return bool(descriptor(self, type(self)))
        return bool(legacy)

    @wants_periodic_tick.setter
    def wants_periodic_tick(self, value):
        self._wants_periodic_tick = bool(value)

    def tick(self):
        """Example plugins redraw each scheduled periodic tick."""
        return bool(self.wants_periodic_tick)

    def __init__(self, title, x, y, w, h, **kwargs):
        super().__init__(title, x, y, w, h, **kwargs)

    def draw_content(self, stdscr, x, y, w, h):
        """Override this to draw your app content."""
        pass

    def draw(self, stdscr):
        """Draw frame + delegate body to draw_content."""
        if not self.visible:
            return
        body_attr = self.draw_frame(stdscr)
        bx, by, bw, bh = self.body_rect()
        self.draw_content(stdscr, bx, by, bw, bh)
        if self.window_menu:
            self.window_menu.draw_dropdown(stdscr, self.x, self.y, self.w)
