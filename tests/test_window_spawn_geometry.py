import unittest
from types import SimpleNamespace

from retrotui.constants import WIN_MIN_HEIGHT, WIN_MIN_WIDTH
from retrotui.core.window_manager import WindowManager, WindowSpawnSpec


class WindowSpawnGeometryTests(unittest.TestCase):
    def test_unsupported_tiny_terminal_preserves_window_minimums(self):
        app = SimpleNamespace(stdscr=SimpleNamespace(getmaxyx=lambda: (5, 10)))
        manager = WindowManager(app)

        _x, _y, width, height = manager.resolve_spawn_geometry(
            WindowSpawnSpec(70, 24, 8, 3)
        )

        self.assertEqual(width, WIN_MIN_WIDTH)
        self.assertEqual(height, WIN_MIN_HEIGHT)


if __name__ == "__main__":
    unittest.main()
