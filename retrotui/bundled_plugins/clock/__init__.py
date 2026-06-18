from retrotui.apps.clock import ClockCalendarWindow


class Plugin(ClockCalendarWindow):
    def __init__(self, title, x, y, w, h, **kwargs):
        ClockCalendarWindow.__init__(self, x, y, w, h)
        if title:
            self.title = title
