from retrotui.apps.image_viewer import ImageViewerWindow


class Plugin(ImageViewerWindow):
    def __init__(self, title, x, y, w, h, **kwargs):
        ImageViewerWindow.__init__(self, x, y, w, h)
        if title:
            self.title = title
