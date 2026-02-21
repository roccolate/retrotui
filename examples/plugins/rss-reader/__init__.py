"""RSS Reader plugin (example)."""
from retrotui.plugins.base import RetroApp
from retrotui.utils import safe_addstr, theme_attr


class Plugin(RetroApp):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # placeholder items — real feed parsing not included in example
        self.items = [
            {'title': 'Welcome to RSS Reader', 'summary': 'This is a demo item.'},
        ]
        self.selected = 0

    def draw_content(self, stdscr, x, y, w, h):
        attr = theme_attr('window_body')
        for i, it in enumerate(self.items[:h]):
            a = attr if i != self.selected else theme_attr('menu_selected')
            safe_addstr(stdscr, y + i, x, it.get('title','')[:w], a)

    def handle_key(self, key):
        if key == ord('j'):
            self.selected = min(self.selected + 1, len(self.items) - 1)
        elif key == ord('k'):
            self.selected = max(self.selected - 1, 0)
        elif key == ord('r'):
            # try to fetch a sample feed (best-effort)
            try:
                import urllib.request, xml.etree.ElementTree as ET
                with urllib.request.urlopen('https://xkcd.com/atom.xml', timeout=5) as resp:
                    data = resp.read()
                root = ET.fromstring(data)
                # Atom feed: entries -> entry/title
                items = []
                for entry in root.findall('.//{http://www.w3.org/2005/Atom}entry'):
                    title = entry.find('{http://www.w3.org/2005/Atom}title')
                    if title is not None:
                        items.append({'title': title.text or ''})
                # Fallback for RSS <item>
                if not items:
                    for item in root.findall('.//item'):
                        t = item.find('title')
                        if t is not None:
                            items.append({'title': t.text or ''})
                if items:
                    self.items = items
                    self.selected = 0
            except Exception:
                # ignore network or parse errors
                pass
