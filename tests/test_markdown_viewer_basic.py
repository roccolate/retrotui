import unittest
import tempfile
import os
import curses

from retrotui.apps.markdown_viewer import MarkdownViewerWindow
from retrotui.core.actions import ActionResult, ActionType, AppAction


class MarkdownViewerBasicTests(unittest.TestCase):
    def setUp(self):
        # Create a temporary markdown file with varied content
        self.tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.md', mode='w', encoding='utf-8')
        lines = []
        lines.append('# Title')
        lines.append('\n')
        lines.append('Some paragraph with **bold** text.')
        lines.append('\n')
        lines.append('```')
        for i in range(20):
            lines.append(f'code line {i}')
        lines.append('```')
        lines.append('\n')
        for i in range(40):
            lines.append(f'Line {i}')
        self.tmp.write('\n'.join(lines))
        self.tmp.flush()
        self.tmp.close()

    def tearDown(self):
        try:
            os.unlink(self.tmp.name)
        except Exception:
            pass

    def test_open_path_and_title_and_status(self):
        mv = MarkdownViewerWindow(0, 0, 80, 24)
        res = mv.open_path(self.tmp.name)
        # open_path returns None on success
        self.assertIsNone(res)
        self.assertTrue(mv.filepath.endswith('.md'))
        self.assertTrue(mv.status_message.startswith('Opened'))
        self.assertIn('Markdown Viewer', mv.title)

    def test_handle_key_actions_and_scrolling(self):
        mv = MarkdownViewerWindow(0, 0, 80, 10)
        mv.open_path(self.tmp.name)
        # ensure content loaded
        self.assertGreater(len(mv.raw_content), 0)
        # press down to scroll
        before = mv.scroll_offset
        mv.handle_key(getattr(curses, 'KEY_DOWN', -1))
        self.assertGreaterEqual(mv.scroll_offset, before)
        # page down/up
        mv.handle_key(getattr(curses, 'KEY_NPAGE', -1))
        mv.handle_key(getattr(curses, 'KEY_PPAGE', -1))
        # home/end
        mv.handle_key(getattr(curses, 'KEY_HOME', -1))
        self.assertEqual(mv.scroll_offset, 0)
        mv.handle_key(getattr(curses, 'KEY_END', -1))
        self.assertGreaterEqual(mv.scroll_offset, 0)
        # q -> close
        act = mv.handle_key(ord('q'))
        self.assertIsInstance(act, ActionResult)
        self.assertEqual(act.type, ActionType.EXECUTE)
        self.assertEqual(act.payload, AppAction.CLOSE_WINDOW)
        # o -> request open
        act2 = mv.handle_key(ord('o'))
        self.assertIsInstance(act2, ActionResult)
        self.assertEqual(act2.type, ActionType.REQUEST_OPEN_PATH)

    def test_execute_action_variants(self):
        mv = MarkdownViewerWindow(0, 0, 80, 24)
        # md_open
        res = mv.execute_action('md_open')
        self.assertIsInstance(res, ActionResult)
        self.assertEqual(res.type, ActionType.REQUEST_OPEN_PATH)
        # md_close
        res2 = mv.execute_action('md_close')
        self.assertIsInstance(res2, ActionResult)
        self.assertEqual(res2.type, ActionType.EXECUTE)
        self.assertEqual(res2.payload, AppAction.CLOSE_WINDOW)


if __name__ == '__main__':
    unittest.main()
