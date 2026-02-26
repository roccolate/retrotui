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

    def test_handle_click_address_bar(self):
        # Body rect for 0,0,80,24 is typically (1, 1, 78, 22)
        # Address bar is at by,bx
        bx, by, bw, bh = self.win.body_rect()
        res = self.win.handle_click(bx + 5, by)
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

    def test_handle_key_sidebar(self):
        self.assertFalse(self.win.show_sidebar)
        self.win.handle_key(ord('h'))
        self.assertTrue(self.win.show_sidebar)
        self.win.handle_key(ord('h'))
        self.assertFalse(self.win.show_sidebar)

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
        self.win.history = ["http://h1.com", "http://h2.com"]
        stdscr = mock.Mock()
        stdscr.getmaxyx.return_value = (24, 80)
        # Mock safe_addstr to avoid issues with curses; ensure draw doesn't raise
        with mock.patch('retrotui.apps.retronet.safe_addstr'):
            self.win.draw(stdscr)
        # If draw completed without raising, consider it successful for tests
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
