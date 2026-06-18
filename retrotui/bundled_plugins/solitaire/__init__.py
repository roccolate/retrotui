from retrotui.apps.solitaire import SolitaireWindow


class Plugin(SolitaireWindow):
    def __init__(self, title, x, y, w, h, **kwargs):
        SolitaireWindow.__init__(self, x, y, w, h)
        if title:
            self.title = title
