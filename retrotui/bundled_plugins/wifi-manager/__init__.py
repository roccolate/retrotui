from retrotui.apps.wifi_manager import WifiManagerWindow


class Plugin(WifiManagerWindow):
    def __init__(self, title, x, y, w, h, **kwargs):
        WifiManagerWindow.__init__(self, x, y, w, h)
