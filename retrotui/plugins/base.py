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

    def __init__(self, title, x, y, w, h, **kwargs):
        super().__init__(title, x, y, w, h, **kwargs)

    def draw_content(self, stdscr, x, y, w, h):
        """Override this to draw your app content."""
        pass

    def draw(self, stdscr):
        """Draw frame + delegate body to draw_content."""
        body_attr = self.draw_frame(stdscr)
        bx, by, bw, bh = self.body_rect()
        self.draw_content(stdscr, bx, by, bw, bh)
