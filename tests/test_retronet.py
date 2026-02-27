import unittest
from unittest import mock
import sys
from _support import make_fake_curses

# Use the shared fake curses helper to ensure consistent constants across tests
sys.modules['curses'] = make_fake_curses()


from retrotui.apps.retronet import RetroNetWindow, RichLine, InteractiveSpan
from retrotui.core.actions import ActionType
import curses



class RetroNetTests(unittest.TestCase):
    def setUp(self):
        # Patch theme_attr and curses constants before initializing window
        with mock.patch('retrotui.apps.retronet.theme_attr', return_value=0):
            with mock.patch('retrotui.apps.retronet.threading.Thread'):
                self.win = RetroNetWindow(0, 0, 80, 24)

    def test_sanitize_url(self):
        # Basic HTTP prepend
        self.assertEqual(self.win._sanitize_url("google.com"), "http://google.com")

        # DuckDuckGo Bridge
        self.assertIn("duckduckgo.com/html/?q=test+search", self.win._sanitize_url("google.com/search?q=test search"))

        # Encoding spaces in path
        self.assertEqual(self.win._sanitize_url("http://example.com/path with spaces"), "http://example.com/path%20with%20spaces")

        # Empty URL
        self.assertEqual(self.win._sanitize_url(""), "")

    def test_parse_html_basic(self):
        html_content = "<html><head><title>Test Title</title></head><body><h1>Header 1</h1><p>Paragraph</p></body></html>"
        lines = self.win._parse_html(html_content)

        # Title should be set (shortened)
        self.assertEqual(self.win.title, "RetroNet Ultra - Test Title")


        # H1 should have bold/underline
        h1_line = next(l for l in lines if "Header 1" in l.text)
        self.assertTrue(h1_line.attr & curses.A_BOLD)

        # Paragraph
        self.assertTrue(any("Paragraph" in l.text for l in lines))

    def test_parse_html_links_and_buttons(self):
        html_content = '<a href="http://link.com">Link Label</a> <button>Click Me</button> <input value="Submit">'
        lines = self.win._parse_html(html_content)

        # Find the line with spans
        line = next(l for l in lines if l.spans)
        self.assertEqual(len(line.spans), 3)

        # Link span
        self.assertEqual(line.spans[0].type, 'link')
        self.assertEqual(line.spans[0].payload, 'http://link.com')
        self.assertIn("[Link Label]", line.text)

        # Button/Input spans
        self.assertEqual(line.spans[1].type, 'input')
        self.assertEqual(line.spans[2].type, 'input')

    def test_parse_html_bold_italic(self):
        html_content = '<b>Bold text</b> normal <em>italic text</em>'
        lines = self.win._parse_html(html_content)
        line = next(l for l in lines if "Bold text" in l.text)
        self.assertTrue(line.attr & curses.A_BOLD)
        line_i = next(l for l in lines if "italic text" in l.text)
        self.assertTrue(line_i.attr & curses.A_DIM)

    def test_handle_click_nav_bar(self):
        bx, by, bw, bh = self.win.body_rect()
        # Click on address area (past back/forward buttons)
        sidebar_w = 0  # no sidebar
        content_x = bx + sidebar_w
        res = self.win.handle_click(content_x + 20, by)
        self.assertEqual(res.action_type, ActionType.REQUEST_URL)
        self.assertEqual(res.payload, self.win.url)

    def test_handle_click_link(self):
        self.win.content = [RichLine(" [Link]", 0, [InteractiveSpan(1, 7, 'link', 'http://new.com')])]
        bx, by, bw, bh = self.win.body_rect()

        with mock.patch.object(self.win, '_load_url') as mock_load:
            res = self.win.handle_click(bx + 3, by + 2) # content_y_start is by + 2
            self.assertEqual(res.action_type, ActionType.REFRESH)
            mock_load.assert_called_with('http://new.com')

    def test_handle_key_scroll(self):
        self.win.content = [RichLine(str(i)) for i in range(100)]
        self.win.scroll_y = 0

        # Scroll down
        self.win.handle_key(curses.KEY_DOWN)
        self.assertEqual(self.win.scroll_y, 1)

        # Scroll up
        self.win.handle_key(curses.KEY_UP)
        self.assertEqual(self.win.scroll_y, 0)

    def test_handle_key_page_up_down(self):
        self.win.content = [RichLine(str(i)) for i in range(200)]
        self.win.scroll_y = 0
        _, _, _, bh = self.win.body_rect()
        content_h = max(1, bh - 3)

        # Page Down
        self.win.handle_key(curses.KEY_NPAGE)
        self.assertEqual(self.win.scroll_y, content_h)

        # Page Up
        self.win.handle_key(curses.KEY_PPAGE)
        self.assertEqual(self.win.scroll_y, 0)

    def test_handle_key_home_end(self):
        self.win.content = [RichLine(str(i)) for i in range(200)]
        _, _, _, bh = self.win.body_rect()
        content_h = max(1, bh - 3)

        # End
        self.win.handle_key(curses.KEY_END)
        self.assertEqual(self.win.scroll_y, len(self.win.content) - content_h)

        # Home
        self.win.handle_key(curses.KEY_HOME)
        self.assertEqual(self.win.scroll_y, 0)

    def test_handle_key_sidebar(self):
        self.assertFalse(self.win.show_sidebar)
        self.win.handle_key(ord('h'))
        self.assertTrue(self.win.show_sidebar)
        self.win.handle_key(ord('h'))
        self.assertFalse(self.win.show_sidebar)

    def test_back_forward_navigation(self):
        with mock.patch('retrotui.apps.retronet.threading.Thread'):
            self.win.url = "http://first.com"
            self.win._back_stack = []
            self.win._forward_stack = []

            # Navigate to second page
            self.win._load_url("http://second.com")
            self.assertEqual(self.win.url, "http://second.com")
            self.assertEqual(self.win._back_stack, ["http://first.com"])
            self.assertEqual(self.win._forward_stack, [])

            # Navigate to third
            self.win._load_url("http://third.com")
            self.assertEqual(self.win.url, "http://third.com")
            self.assertEqual(len(self.win._back_stack), 2)

            # Go back
            self.win._go_back()
            self.assertEqual(self.win.url, "http://second.com")
            self.assertEqual(len(self.win._forward_stack), 1)

            # Go forward
            self.win._go_forward()
            self.assertEqual(self.win.url, "http://third.com")
            self.assertEqual(len(self.win._forward_stack), 0)

    def test_back_empty_returns_none(self):
        self.win._back_stack = []
        self.assertIsNone(self.win._go_back())

    def test_forward_empty_returns_none(self):
        self.win._forward_stack = []
        self.assertIsNone(self.win._go_forward())

    def test_history_cap(self):
        with mock.patch('retrotui.apps.retronet.threading.Thread'):
            self.win._back_stack = [f"http://{i}.com" for i in range(250)]
            self.win._load_url("http://new.com")
            self.assertLessEqual(len(self.win._back_stack), 200)

    def test_search_find_matches(self):
        self.win.content = [
            RichLine(" hello world"),
            RichLine(" foo bar"),
            RichLine(" hello again"),
        ]
        matches = self.win._find_matches("hello")
        self.assertEqual(matches, [0, 2])

    def test_search_next_prev(self):
        self.win.content = [
            RichLine(" match here"),
            RichLine(" no match"),
            RichLine(" match again"),
        ]
        self.win._search_query = "match"
        self.win._search_matches = [0, 2]
        self.win._search_idx = -1

        self.win._search_next()
        self.assertEqual(self.win._search_idx, 0)
        self.win._search_next()
        self.assertEqual(self.win._search_idx, 1)
        self.win._search_next()  # wraps
        self.assertEqual(self.win._search_idx, 0)

        self.win._search_prev()  # wraps back
        self.assertEqual(self.win._search_idx, 1)

    def test_execute_search(self):
        self.win.content = [
            RichLine(" apple"),
            RichLine(" banana"),
            RichLine(" apple pie"),
        ]
        res = self.win.execute_search("apple")
        self.assertEqual(res.type, ActionType.REFRESH)
        self.assertEqual(self.win._search_query, "apple")
        self.assertEqual(self.win._search_matches, [0, 2])
        self.assertEqual(self.win._search_idx, 0)

    def test_open_path_search_prefix(self):
        self.win.content = [
            RichLine(" findme here"),
            RichLine(" other"),
        ]
        res = self.win.open_path("search:findme")
        self.assertEqual(res.type, ActionType.REFRESH)
        self.assertEqual(self.win._search_query, "findme")

    def test_open_path_url(self):
        with mock.patch.object(self.win, '_load_url') as mock_load:
            self.win.open_path("http://example.com")
            mock_load.assert_called_with("http://example.com")

    def test_search_mode_escape_clears(self):
        self.win._search_query = "test"
        self.win._search_matches = [0]
        self.win._search_idx = 0
        res = self.win.handle_key(27)  # Escape
        self.assertEqual(res.type, ActionType.REFRESH)
        self.assertEqual(self.win._search_query, "")

    def test_handle_key_slash_triggers_search(self):
        res = self.win.handle_key(ord('/'))
        self.assertEqual(res.type, ActionType.REQUEST_URL)
        self.assertEqual(res.payload, "search:")

    @mock.patch('urllib.request.urlopen')
    def test_fetch_thread_success(self, mock_urlopen):
        # Mock response
        mock_response = mock.MagicMock()
        mock_response.read.return_value = b"<html><body>Fetched</body></html>"
        mock_response.info().get_content_charset.return_value = 'utf-8'
        mock_urlopen.return_value = mock_response

        self.win._fetch_thread("http://test.com")
        self.assertFalse(self.win.is_loading)
        self.assertTrue(any("Fetched" in l.text for l in self.win.content))

    @mock.patch('urllib.request.urlopen')
    def test_fetch_thread_error(self, mock_urlopen):
        mock_urlopen.side_effect = OSError("Net Error")

        self.win._fetch_thread("http://test.com")
        self.assertFalse(self.win.is_loading)
        self.assertTrue(any("Net Error" in l.text for l in self.win.content))

    def test_draw_sidebar(self):
        self.win.show_sidebar = True
        self.win._back_stack = ["http://h1.com", "http://h2.com"]
        stdscr = mock.Mock()
        stdscr.getmaxyx.return_value = (24, 80)
        with mock.patch('retrotui.apps.retronet.safe_addstr'):
            self.win.draw(stdscr)

    def test_draw_search_footer(self):
        self.win.content = [RichLine(" test match")]
        self.win._search_query = "test"
        self.win._search_matches = [0]
        self.win._search_idx = 0
        stdscr = mock.Mock()
        stdscr.getmaxyx.return_value = (24, 80)
        # Just verify draw completes without error when search is active
        with mock.patch('retrotui.apps.retronet.safe_addstr'):
            self.win.draw(stdscr)

    def test_handle_click_back_button(self):
        self.win._back_stack = ["http://prev.com"]
        bx, by, bw, bh = self.win.body_rect()
        with mock.patch.object(self.win, '_go_back', return_value=None) as mock_back:
            self.win.handle_click(bx + 2, by)
            mock_back.assert_called_once()

    def test_sidebar_click_navigates(self):
        self.win.show_sidebar = True
        self.win._back_stack = ["http://old.com"]
        bx, by, bw, bh = self.win.body_rect()
        with mock.patch.object(self.win, '_load_url') as mock_load:
            res = self.win.handle_click(bx + 2, by + 1)
            mock_load.assert_called_with("http://old.com")
            self.assertEqual(res.type, ActionType.REFRESH)


if __name__ == "__main__":
    unittest.main()
