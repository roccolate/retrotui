from retrotui.apps.retronet import RetroNetWindow


class Plugin(RetroNetWindow):
    def __init__(self, title, x, y, w, h, **kwargs):
        RetroNetWindow.__init__(self, x, y, w, h)
        if title:
            self.title = title
