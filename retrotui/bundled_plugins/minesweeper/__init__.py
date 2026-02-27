from retrotui.apps.minesweeper import MinesweeperWindow


class Plugin(MinesweeperWindow):
    def __init__(self, title, x, y, w, h, **kwargs):
        MinesweeperWindow.__init__(self, x, y, w, h)
