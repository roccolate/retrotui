from retrotui.apps.charmap import CharacterMapWindow


class Plugin(CharacterMapWindow):
    def __init__(self, title, x, y, w, h, **kwargs):
        CharacterMapWindow.__init__(self, x, y, w, h)
        if title:
            self.title = title
