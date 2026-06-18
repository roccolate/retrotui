from retrotui.apps.snake import SnakeWindow


class Plugin(SnakeWindow):
    def __init__(self, title, x, y, w, h, **kwargs):
        SnakeWindow.__init__(self, x, y, w, h)
        if title:
            self.title = title
