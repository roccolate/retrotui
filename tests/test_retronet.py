import unittest
import os
from unittest import mock
import sys
import ssl
from _support import make_fake_curses

# Use the shared fake curses helper to ensure consistent constants across tests
sys.modules['curses'] = make_fake_curses()


from retrotui.apps.retronet import RetroNetWindow, RichLine, InteractiveSpan, MAX_RESPONSE_BYTES
from retrotui.core.actions import ActionType, AppAction
import curses



class RetroNetTests(unittest.TestCase):
    def setUp(self):
        # Patch theme_attr and curses constants before initializing window
        with mock.patch('retrotui.apps.retronet.theme_attr', return_value=0):
            with mock.patch('retrotui.apps.retronet.threading.Thread'):
                self.win = RetroNetWindow(0, 0, 80, 24)

    def test_constructor_loads_default_tab_once(self):
        with mock.patch('retrotui.apps.retronet.theme_attr', return_value=0), mock.patch.object(
            RetroNetWindow, "_load_url", autospec=True
        ) as load_url:
            RetroNetWindow(0, 0, 80, 24)

        self.assertEqual(load_url.call_count, 1)

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

    def test_parse_html_nested_formatting(self):
        # The old regex pipeline flattened nested tags by global replacement
        # order. A proper HTMLParser walks the tree, so <b><i>x</i></b> applies
        # both attributes to the same line.
        lines = self.win._parse_html('<p><b><i>both</i></b></p>')
        line = next(l for l in lines if "both" in l.text)
        self.assertTrue(line.attr & curses.A_BOLD)
        self.assertTrue(line.attr & curses.A_DIM)
        self.assertNotIn("[B]", line.text)
        self.assertNotIn("[I]", line.text)

    def test_parse_html_malformed_unclosed(self):
        # Unclosed <b> used to leave a stray "[B]" in the rendered text. The
        # parser tolerates it and the post-processor strips the orphan marker.
        lines = self.win._parse_html('<p>hello <b>world</p>')
        rendered = ' '.join(l.text for l in lines)
        self.assertIn("hello", rendered)
        self.assertIn("world", rendered)
        self.assertNotIn("[B]", rendered)
        self.assertNotIn("[/B]", rendered)

    def test_parse_html_malformed_mismatched(self):
        # </i> without <i>; the parser must not crash and must render the text
        # content. An orphan closing marker may survive the post-processor
        # (same as the previous regex pipeline) — the value here is that
        # the parser tolerates the mismatch instead of raising.
        lines = self.win._parse_html('<p>foo <b>bar</i></p>')
        rendered = ' '.join(l.text for l in lines)
        self.assertIn("foo", rendered)
        self.assertIn("bar", rendered)
        self.assertTrue(lines, "parser should still emit lines for malformed input")

    def test_parse_html_script_and_style_skipped(self):
        # Script/style content must not leak into the rendered page, even when
        # the tags are nested or contain HTML-looking content.
        html_content = (
            '<script>var x = "<b>nope</b>";</script>'
            'visible '
            '<style>p { color: red }</style>'
            'also visible'
        )
        lines = self.win._parse_html(html_content)
        rendered = ' '.join(l.text for l in lines)
        self.assertIn("visible", rendered)
        self.assertIn("also visible", rendered)
        self.assertNotIn("nope", rendered)
        self.assertNotIn("color", rendered)

    def test_parse_html_hidden_input_filtered(self):
        # type="hidden" inputs must not produce any [BT] marker.
        lines = self.win._parse_html(
            '<form><input type="hidden" name="csrf" value="abc">'
            '<input value="Submit"></form>'
        )
        rendered = ' '.join(l.text for l in lines)
        self.assertIn("Submit", rendered)
        self.assertNotIn("csrf", rendered)
        self.assertNotIn("abc", rendered)

    def test_parse_html_entities_in_title(self):
        # Entities in <title> must be decoded (same as the old html.unescape).
        self.win._parse_html('<html><head><title>A &amp; B &lt;ok&gt;</title></head><body></body></html>')
        self.assertEqual(self.win.title, "RetroNet Ultra - A & B <ok>")

    def test_parse_html_entities_in_body(self):
        # convert_charrefs=True decodes entities in text content.
        lines = self.win._parse_html('<p>Tom &amp; Jerry &lt;3</p>')
        rendered = ' '.join(l.text for l in lines)
        self.assertIn("Tom & Jerry <3", rendered)

    def test_parse_html_doctype_and_comments_ignored(self):
        # Real-world pages start with <!DOCTYPE ...> and contain <!-- ... -->.
        # Neither must reach the renderer.
        lines = self.win._parse_html(
            '<!DOCTYPE html><html><body><!-- secret -->'
            '<p>public</p></body></html>'
        )
        rendered = ' '.join(l.text for l in lines)
        self.assertIn("public", rendered)
        self.assertNotIn("secret", rendered)
        self.assertNotIn("DOCTYPE", rendered)

    def test_parse_html_void_self_closing(self):
        # XHTML-style self-closing tags must work (handle_startendtag delegates
        # to handle_starttag + handle_endtag by default).
        lines = self.win._parse_html('<p>line one<br/>line two<hr/></p>')
        rendered = ' '.join(l.text for l in lines)
        self.assertIn("line one", rendered)
        self.assertIn("line two", rendered)

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

    def test_handle_key_ctrl_b_opens_bookmarks(self):
        # Ctrl+B (keycode 2) must request the bookmarks window via the new
        # ActionType, not REQUEST_URL.
        res = self.win.handle_key(2)
        self.assertEqual(res.type, ActionType.REQUEST_BOOKMARKS)

    def test_handle_key_ctrl_d_requests_add_bookmark(self):
        res = self.win.handle_key(4)
        self.assertEqual(res.type, ActionType.REQUEST_ADD_BOOKMARK)

    def test_starts_with_single_default_tab(self):
        self.assertEqual(len(self.win.tabs), 1)
        self.assertEqual(self.win.active_tab_idx, 0)

    def test_ctrl_t_creates_new_tab(self):
        before = len(self.win.tabs)
        res = self.win.handle_key(20)  # Ctrl+T
        self.assertEqual(res.type, ActionType.REFRESH)
        self.assertEqual(len(self.win.tabs), before + 1)
        self.assertEqual(self.win.active_tab_idx, before)

    def test_ctrl_w_closes_current_tab(self):
        self.win.handle_key(20)  # Ctrl+T
        second_idx = self.win.active_tab_idx
        before = len(self.win.tabs)
        res = self.win.handle_key(23)  # Ctrl+W
        self.assertEqual(res.type, ActionType.REFRESH)
        self.assertEqual(len(self.win.tabs), before - 1)
        self.assertNotEqual(self.win.active_tab_idx, second_idx)

    def test_ctrl_w_on_last_tab_closes_window(self):
        # Only the initial tab exists.
        self.assertEqual(len(self.win.tabs), 1)
        res = self.win.handle_key(23)
        self.assertEqual(res.type, ActionType.EXECUTE)
        self.assertEqual(res.payload, AppAction.CLOSE_WINDOW)

    def test_ctrl_i_cycles_tabs_forward(self):
        self.win.handle_key(20)  # new tab 1
        self.win.handle_key(20)  # new tab 2
        self.assertEqual(self.win.active_tab_idx, 2)
        self.win.handle_key(9)  # Ctrl+I -> next tab (wraps)
        self.assertEqual(self.win.active_tab_idx, 0)

    def test_shift_tab_cycles_tabs_backward(self):
        self.win.handle_key(20)  # new tab 1
        self.win.handle_key(20)  # new tab 2
        # Now on tab 2. Shift+Tab should go to tab 1.
        self.win.handle_key(curses.KEY_BTAB)
        self.assertEqual(self.win.active_tab_idx, 1)

    def test_each_tab_has_independent_state(self):
        # Open tab 2 and a third, each with different content via _load_url.
        self.win.handle_key(20)
        self.win.content = [RichLine("Tab 2 content")]
        self.win.url = "http://second.com"
        self.win.handle_key(20)
        self.win.content = [RichLine("Tab 3 content")]
        self.win.url = "http://third.com"
        # Switch back to tab 1 — original state must still be there.
        self.win._cycle_tab(-1)
        self.win._cycle_tab(-1)
        self.assertEqual(self.win.url, "http://text.npr.org")
        self.assertEqual(len(self.win.tabs), 3)

    def test_each_tab_has_independent_history(self):
        # Tab 1 navigates somewhere; new tab starts with the default URL.
        with mock.patch('retrotui.apps.retronet.threading.Thread'):
            self.win._load_url("http://a.com", _push_history=False)
        self.assertEqual(len(self.win._back_stack), 0)
        self.win.handle_key(20)  # new tab
        self.assertEqual(self.win.url, "http://text.npr.org")
        self.assertEqual(len(self.win._back_stack), 0)
        self.assertEqual(len(self.win.tabs), 2)

    def test_window_title_reflects_active_tab(self):
        self.win.handle_key(20)  # new tab
        new_tab = self.win._cur()
        new_tab.title = "Second Page"
        self.win._refresh_window_title()
        self.assertIn("Second Page", self.win.title)

    def test_view_source_returns_none_for_empty_tab(self):
        # No fetch has populated raw_html yet.
        self.assertIsNone(self.win._view_source_path())

    def test_view_source_writes_raw_html(self):
        with self.win._lock:
            self.win._cur().raw_html = "<html><body>hi</body></html>"
        path = self.win._view_source_path()
        self.assertIsNotNone(path)
        try:
            with open(path, encoding="utf-8") as f:
                self.assertEqual(f.read(), "<html><body>hi</body></html>")
        finally:
            os.unlink(path)

    def test_view_source_path_is_deterministic_per_url(self):
        with self.win._lock:
            self.win._cur().url = "http://a.com/page"
            self.win._cur().raw_html = "<html>a</html>"
        path1 = self.win._view_source_path()
        with self.win._lock:
            self.win._cur().raw_html = "<html>a-updated</html>"
        path2 = self.win._view_source_path()
        try:
            self.assertEqual(path1, path2)
            with open(path2, encoding="utf-8") as f:
                self.assertEqual(f.read(), "<html>a-updated</html>")
        finally:
            os.unlink(path1)

    def test_ctrl_u_emits_open_file_with_source_path(self):
        with self.win._lock:
            self.win._cur().raw_html = "<p>x</p>"
            self.win._cur().url = "http://example.com/"
        res = self.win.handle_key(21)  # Ctrl+U
        self.assertEqual(res.type, ActionType.OPEN_FILE)
        self.assertTrue(res.payload.endswith(".html"))
        try:
            with open(res.payload, encoding="utf-8") as f:
                self.assertEqual(f.read(), "<p>x</p>")
        finally:
            os.unlink(res.payload)

    def test_ctrl_u_with_no_content_is_noop_refresh(self):
        # raw_html is empty → no file written → REFRESH (so the UI redraws).
        res = self.win.handle_key(21)
        self.assertEqual(res.type, ActionType.REFRESH)

    def test_fetch_thread_persists_raw_html(self):
        with mock.patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = mock.MagicMock()
            mock_response.read.return_value = b"<html><body>Raw</body></html>"
            mock_response.info().get_content_charset.return_value = 'utf-8'
            mock_urlopen.return_value = mock_response
            self.win._fetch_thread("http://raw.com", self.win.active_tab_idx)
        self.assertEqual(self.win._cur().raw_html, "<html><body>Raw</body></html>")

    @mock.patch('urllib.request.urlopen')
    def test_fetch_thread_success(self, mock_urlopen):
        # Mock response
        mock_response = mock.MagicMock()
        mock_response.read.return_value = b"<html><body>Fetched</body></html>"
        mock_response.info().get_content_charset.return_value = 'utf-8'
        mock_urlopen.return_value = mock_response

        self.win._fetch_thread("http://test.com", self.win.active_tab_idx)
        self.assertFalse(self.win.is_loading)
        self.assertTrue(any("Fetched" in l.text for l in self.win.content))

    @mock.patch('urllib.request.urlopen')
    def test_fetch_thread_error(self, mock_urlopen):
        mock_urlopen.side_effect = OSError("Net Error")

        self.win._fetch_thread("http://test.com", self.win.active_tab_idx)
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

    @mock.patch('urllib.request.urlopen')
    def test_fetch_thread_does_not_retry_invalid_tls(self, mock_urlopen):
        mock_urlopen.side_effect = ssl.SSLError("certificate verify failed")
        self.win._fetch_thread("https://invalid.example", self.win.active_tab_idx)
        invalid_calls = [
            call for call in mock_urlopen.call_args_list
            if getattr(call.args[0], "full_url", "") == "https://invalid.example"
        ]
        self.assertEqual(len(invalid_calls), 1)
        self.assertFalse(self.win.is_loading)
        self.assertTrue(any("certificate verify failed" in line.text for line in self.win.content))

    @mock.patch('urllib.request.urlopen')
    def test_fetch_thread_rejects_oversized_response(self, mock_urlopen):
        mock_response = mock.MagicMock()
        mock_response.read.return_value = b"x" * (MAX_RESPONSE_BYTES + 1)
        mock_response.info().get_content_charset.return_value = 'utf-8'
        mock_urlopen.return_value = mock_response
        self.win._fetch_thread("https://large.example", self.win.active_tab_idx)
        mock_response.read.assert_called_once_with(MAX_RESPONSE_BYTES + 1)
        self.assertFalse(self.win.is_loading)
        self.assertTrue(any("exceeds" in line.text for line in self.win.content))


if __name__ == "__main__":
    unittest.main()
