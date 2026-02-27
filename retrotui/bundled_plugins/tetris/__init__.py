from retrotui.apps.tetris import TetrisWindow


class Plugin(TetrisWindow):
    def __init__(self, title, x, y, w, h, **kwargs):
        TetrisWindow.__init__(self, x, y)
