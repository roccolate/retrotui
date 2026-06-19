import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock


def _install_fake_curses():
    fake = types.ModuleType("curses")
    fake.A_BOLD = 1
    fake.A_REVERSE = 2
    fake.A_DIM = 4
    fake.COLOR_WHITE = 7
    fake.COLOR_BLUE = 4
    fake.COLOR_BLACK = 0
    fake.COLOR_CYAN = 6
    fake.COLOR_YELLOW = 3
    fake.COLORS = 256
    fake.error = Exception
    fake.color_pair = lambda _: 0
    fake.can_change_color = lambda: False
    fake.start_color = lambda: None
    fake.use_default_colors = lambda: None
    fake.init_color = lambda *_: None
    fake.init_pair = lambda *_: None
    return fake


sys.modules.setdefault("curses", _install_fake_curses())

from retrotui.core.icon_manager import IconPositionManager


class IconManagerTests(unittest.TestCase):
    def test_sort_positions_orders_icons_alphabetically(self):
        app = types.SimpleNamespace(
            icons=[
                {"label": "Zulu"},
                {"label": "alpha"},
                {"label": "Beta"},
            ],
            stdscr=types.SimpleNamespace(getmaxyx=lambda: (24, 120)),
            persist_config=mock.Mock(),
        )
        mgr = IconPositionManager(app)

        positions = mgr.sort_positions()

        self.assertEqual(positions["alpha"], (3, 3))
        self.assertEqual(positions["Beta"], (3, 8))
        self.assertEqual(positions["Zulu"], (3, 13))
        app.persist_config.assert_called_once_with()

    def test_get_screen_pos_uses_default_grid_when_no_persisted_entry(self):
        app = types.SimpleNamespace(
            icons=[{"label": "One"}, {"label": "Two"}],
            stdscr=types.SimpleNamespace(getmaxyx=lambda: (24, 120)),
        )
        mgr = IconPositionManager(app)

        self.assertEqual(mgr.get_screen_pos(0), (3, 3))
        self.assertEqual(mgr.get_screen_pos(1), (3, 8))

    def test_get_screen_pos_supports_position_key_alias(self):
        app = types.SimpleNamespace(
            icons=[{"label": "Desktop", "position_key": "Icons"}],
            stdscr=types.SimpleNamespace(getmaxyx=lambda: (24, 120)),
        )
        mgr = IconPositionManager(app)
        mgr.positions = {"Icons": (33, 11)}

        self.assertEqual(mgr.get_screen_pos(0), (33, 11))

    def test_get_icon_at_supports_symbol_icons(self):
        app = types.SimpleNamespace(
            icons=[{"label": "Files", "symbol": "[D]"}],
            stdscr=types.SimpleNamespace(getmaxyx=lambda: (24, 120)),
        )
        mgr = IconPositionManager(app)
        mgr.positions = {"Files": (10, 6)}

        self.assertEqual(mgr.get_icon_at(10, 6), 0)
        self.assertEqual(mgr.get_icon_at(9, 5), -1)

    def test_save_and_load_quotes_icon_keys(self):
        app = types.SimpleNamespace(
            icons=[],
            stdscr=types.SimpleNamespace(getmaxyx=lambda: (24, 120)),
        )
        mgr = IconPositionManager(app)
        mgr.positions = {'ASCII Vid': (7, 9), 'Quote "App"': (1, 2)}

        with TemporaryDirectory() as tmp:
            path = f"{tmp}/config.toml"
            mgr.save(path)
            text = Path(path).read_text(encoding="utf-8")
            self.assertIn('"ASCII Vid" = "7,9"', text)
            self.assertIn('"Quote \\"App\\"" = "1,2"', text)

            loaded = IconPositionManager(app).load(path)

        self.assertEqual(loaded['ASCII Vid'], (7, 9))
        self.assertEqual(loaded['Quote "App"'], (1, 2))


if __name__ == "__main__":
    unittest.main()
