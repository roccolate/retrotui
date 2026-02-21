import unittest
from unittest import mock
import types
import sys
import os

from retrotui.apps.markdown_viewer import MarkdownViewerWindow
from retrotui.core.actions import ActionType

def _install_fake_curses():
    fake = types.ModuleType("curses")
    fake.A_BOLD = 1
    fake.A_UNDERLINE = 2
    fake.A_REVERSE = 4
    fake.color_pair = lambda x: x
    fake.can_change_color = lambda: True
    fake.error = Exception
    return fake

class TestMarkdownViewer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_curses = sys.modules.get("curses")
        sys.modules["curses"] = _install_fake_curses()
        
        # Pop modules to force pick up mocked curses
        for mod in list(sys.modules.keys()):
            if mod.startswith("retrotui."):
                sys.modules.pop(mod, None)
        
        from retrotui.apps.markdown_viewer import MarkdownViewerWindow
        cls.MarkdownViewerWindow = MarkdownViewerWindow

    @classmethod
    def tearDownClass(cls):
        # Pop them again to clean up after ourselves
        for mod in list(sys.modules.keys()):
            if mod.startswith("retrotui."):
                sys.modules.pop(mod, None)
        
        if cls._prev_curses:
            sys.modules["curses"] = cls._prev_curses
        else:
            sys.modules.pop("curses", None)

    def setUp(self):
        # Patch utilities to avoid real curses interaction during draw
        self.safe_patcher = mock.patch("retrotui.apps.markdown_viewer.safe_addstr")
        self.theme_patcher = mock.patch("retrotui.apps.markdown_viewer.theme_attr", return_value=0)
        self.mock_safe = self.safe_patcher.start()
        self.mock_theme = self.theme_patcher.start()

    def tearDown(self):
        self.safe_patcher.stop()
        self.theme_patcher.stop()

    def test_markdown_viewer_init(self):
        win = self.MarkdownViewerWindow(0, 0, 80, 24)
        self.assertEqual(win.title, "Markdown Viewer")
        self.assertEqual(win.raw_content, [])

    @mock.patch("builtins.open", new_callable=mock.mock_open, read_data="# Header\n**bold**")
    @mock.patch("os.path.isfile", return_value=True)
    def test_open_path(self, mock_isfile, mock_open):
        win = self.MarkdownViewerWindow(0, 0, 80, 24)
        win.open_path("test.md")
        self.assertEqual(len(win.raw_content), 2)
        self.assertIn("Header", win.raw_content[0])

    def test_draw_headers_and_bold(self):
        win = self.MarkdownViewerWindow(0, 0, 80, 24)
        win.raw_content = ["# Header 1", "**bold text**"]
        
        stdscr = mock.Mock()
        stdscr.getmaxyx.return_value = (24, 80)
        win.draw(stdscr)
        
        # Verify safe_addstr was called for header and bold
        calls = [call.args for call in self.mock_safe.call_args_list]
        
        # Check for header
        header_call = next((c for c in calls if "Header 1" in c[3]), None)
        self.assertIsNotNone(header_call)
        self.assertTrue(header_call[4] & 1) # A_BOLD
        self.assertTrue(header_call[4] & 2) # A_UNDERLINE

        # Check for bold
        bold_call = next((c for c in calls if "bold text" in c[3]), None)
        self.assertIsNotNone(bold_call)
        self.assertTrue(bold_call[4] & 1) # A_BOLD

if __name__ == "__main__":
    unittest.main()
