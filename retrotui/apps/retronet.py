"""RetroNet Explorer Ultra: The state-of-the-art text browser."""
import curses
import urllib.request
import urllib.parse
import re
import html
import threading
import ssl
import socket
import http.client
from dataclasses import dataclass
from typing import List, Tuple

from ..ui.window import Window
from ..utils import safe_addstr, theme_attr, normalize_key_code
from ..core.actions import ActionResult, ActionType
from ..constants import _CURSES_ERROR

_URL_SANITIZE_ERRORS = (
    AttributeError,
    LookupError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
    UnicodeError,
)
_RETRONET_FETCH_ERRORS = (
    urllib.error.URLError,
    socket.timeout,
    OSError,
    UnicodeDecodeError,
    ssl.SSLError,
    http.client.HTTPException,
)
_RESPONSE_CLOSE_ERRORS = (
    AttributeError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)

_MAX_HISTORY = 200


@dataclass
class InteractiveSpan:
    start_x: int
    end_x: int
    type: str  # 'link', 'input', 'button'
    payload: str = ""

@dataclass
class RichLine:
    text: str
    attr: int = 0
    spans: List[InteractiveSpan] = None

    def __post_init__(self):
        if self.spans is None:
            self.spans = []

class RetroNetWindow(Window):
    """Nostalgic yet ultra-modern text browser."""

    def __init__(self, x, y, w, h):
        super().__init__('RetroNet Explorer Ultra', x, y, w, h)
        self.url = "http://text.npr.org"
        self.content: List[RichLine] = []
        self._back_stack: list = []
        self._forward_stack: list = []
        self.scroll_y = 0
        self.is_loading = False
        self.show_sidebar = False
        self.loading_frame = 0
        self.loading_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        self._search_query = ""
        self._search_matches: list = []
        self._search_idx = -1

        # Pre-resolve attributes for thread safety
        self.attr_title = theme_attr('window_title')
        self.attr_error = theme_attr('error')
        self.attr_dim = curses.A_DIM
        self.attr_bold = curses.A_BOLD
        self.attr_inactive = theme_attr('window_inactive')
        self.attr_body = theme_attr('window_body')

        self._lock = threading.Lock()
        self._load_url(self.url)

    # ------------------------------------------------------------------
    # URL handling
    # ------------------------------------------------------------------

    def _sanitize_url(self, url):
        """Encode spaces and special characters for network, but keep it readable."""
        if not url: return ""

        # DuckDuckGo Bridge: Clean and simple
        if "google.com/search?q=" in url or "duckduckgo.com/?q=" in url:
            query = ""
            if "?q=" in url:
                query = url.split("?q=", 1)[1]
            return f"https://duckduckgo.com/html/?q={urllib.parse.quote_plus(urllib.parse.unquote(query))}"

        try:
            parts = list(urllib.parse.urlsplit(url))
            if not parts[0]:
                 return self._sanitize_url('http://' + url)
            parts[2] = urllib.parse.quote(parts[2])
            parts[3] = urllib.parse.quote(parts[3], safe='=&')
            return urllib.parse.urlunsplit(parts)
        except _URL_SANITIZE_ERRORS:
            return url

    # ------------------------------------------------------------------
    # Navigation (back / forward)
    # ------------------------------------------------------------------

    def _load_url(self, url, *, _push_history=True):
        if not url: return

        clean_url = url
        sanitized_url = self._sanitize_url(url)

        if _push_history and self.url:
            self._back_stack.append(self.url)
            if len(self._back_stack) > _MAX_HISTORY:
                self._back_stack = self._back_stack[-_MAX_HISTORY:]
            self._forward_stack.clear()

        self.url = clean_url
        self.content = [RichLine("Loading...", self.attr_title)]
        self.is_loading = True
        self.scroll_y = 0
        self._clear_search()

        thread = threading.Thread(target=self._fetch_thread, args=(sanitized_url,), daemon=True)
        thread.start()

    def _go_back(self):
        if not self._back_stack:
            return None
        self._forward_stack.append(self.url)
        prev = self._back_stack.pop()
        self._load_url(prev, _push_history=False)
        return ActionResult(ActionType.REFRESH)

    def _go_forward(self):
        if not self._forward_stack:
            return None
        self._back_stack.append(self.url)
        nxt = self._forward_stack.pop()
        self._load_url(nxt, _push_history=False)
        return ActionResult(ActionType.REFRESH)

    # ------------------------------------------------------------------
    # Network
    # ------------------------------------------------------------------

    def _fetch_thread(self, url):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            context = ssl.create_default_context()
            ssl_warning = False

            req = urllib.request.Request(url, headers=headers)
            # Some test doubles for urllib.request.urlopen don't implement the
            # context manager protocol; use a plain call and close when possible.
            try:
                response = urllib.request.urlopen(req, timeout=10, context=context)
            except ssl.SSLError:
                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                response = urllib.request.urlopen(req, timeout=10, context=context)
                ssl_warning = True
            try:
                charset = response.info().get_content_charset() or 'utf-8'
                raw_html = response.read().decode(charset, errors='ignore')
            finally:
                try:
                    response.close()
                except _RESPONSE_CLOSE_ERRORS:
                    pass
            parsed = self._parse_html(raw_html)
            if ssl_warning:
                parsed.insert(0, RichLine("[SSL: certificate verification failed — showing unverified content]", self.attr_error))
            with self._lock:
                self.content = parsed
        except _RETRONET_FETCH_ERRORS as e:
            msg = str(e) if str(e) else "Unknown network error or crash."
            with self._lock:
                self.content = [
                    RichLine(f"Error loading {url}:", self.attr_error),
                    RichLine(msg, self.attr_dim)
                ]
        finally:
            with self._lock:
                self.is_loading = False

    # ------------------------------------------------------------------
    # HTML parsing
    # ------------------------------------------------------------------

    def _parse_html(self, raw_html):
        """Ultra parser with style and structure support."""
        title_match = re.search(r'<title>(.*?)</title>', raw_html, re.IGNORECASE | re.DOTALL)
        if title_match:
            new_title = f"RetroNet Ultra - {html.unescape(title_match.group(1)).strip()[:30]}"
            with self._lock:
                self.title = new_title

        # Clean scripts, styles, SVG, noscript
        text = re.sub(r'<(script|style|svg|noscript).*?>.*?</\1>', '', raw_html, flags=re.DOTALL | re.IGNORECASE)

        # 1. Headers
        text = re.sub(r'<h[1-3].*?>(.*?)</h[1-3]>', r'\n\n[H1]\1[/H]\n', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<h[4-6].*?>(.*?)</h[4-6]>', r'\n\n[H2]\1[/H]\n', text, flags=re.DOTALL | re.IGNORECASE)

        # 2. Bold/Strong and Italic/Em
        text = re.sub(r'<(b|strong).*?>(.*?)</\1>', r'[B]\2[/B]', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<(i|em).*?>(.*?)</\1>', r'[I]\2[/I]', text, flags=re.DOTALL | re.IGNORECASE)

        # 3. Inputs/Buttons
        def render_input(match):
            tag = match.group(0)
            if 'type="hidden"' in tag.lower(): return ""
            p = re.search(r'placeholder=["\'](.*?)["\']', tag, re.I)
            v = re.search(r'value=["\'](.*?)["\']', tag, re.I)
            lbl = (v or p).group(1) if (v or p) else "Submit"
            lbl = lbl.replace('\n', ' ').strip()
            return f" [BT]{lbl}[/BT] "
        text = re.sub(r'<input.*?>', render_input, text, flags=re.I)

        def render_button(match):
            lbl = match.group(1).replace('\n', ' ').strip()
            return f" [BT]{lbl}[/BT] "
        text = re.sub(r'<button.*?>(.*?)</button>', render_button, text, flags=re.I | re.S)

        # 4. Links
        def render_link(match):
            href_m = re.search(r'href=["\'](.*?)["\']', match.group(0), re.I)
            url = href_m.group(1) if href_m else "#"
            label = match.group(1)
            url = url.replace('\n', '').strip()
            label = label.replace('\n', ' ').strip()
            if not label: label = url[:20]
            return f"[L]{url}|{label}[/L]"

        text = re.sub(r'<a\s+.*?>(.*?)</a>', render_link, text, flags=re.DOTALL | re.IGNORECASE)

        # 5. Block elements & cleanup
        text = re.sub(r'<(p|div|li|br|form|tr|hr).*?>', r'\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<.*?>', '', text)
        text = html.unescape(text)

        # 6. Post-process tokens into RichLine objects
        final_lines = []
        for line_raw in text.splitlines():
            line_raw = line_raw.strip()
            if not line_raw:
                if final_lines and final_lines[-1].text != "":
                    final_lines.append(RichLine(""))
                continue

            attr = 0
            spans = []

            # Line attributes from headers
            if "[H1]" in line_raw:
                underline = getattr(curses, 'A_UNDERLINE', 0)
                attr = curses.A_BOLD | underline
                line_raw = line_raw.replace("[H1]", "").replace("[/H]", "")
            elif "[H2]" in line_raw:
                attr = curses.A_BOLD
                line_raw = line_raw.replace("[H2]", "").replace("[/H]", "")

            # Inline formatting tokens
            if "[B]" in line_raw:
                attr |= curses.A_BOLD
                line_raw = line_raw.replace("[B]", "").replace("[/B]", "")
            if "[I]" in line_raw:
                attr |= curses.A_DIM  # curses has no real italic; dim approximates
                line_raw = line_raw.replace("[I]", "").replace("[/I]", "")

            clean_text = " "
            if attr & curses.A_BOLD: clean_text = "» "

            working = line_raw
            while True:
                m_link = re.search(r'\[L\](.*?)\|(.*?)\[/L\]', working)
                m_btn = re.search(r'\[BT\](.*?)\[/BT\]', working)

                indices = [i for i in [m_link, m_btn] if i]
                if not indices: break
                m = min(indices, key=lambda x: x.start())

                clean_text += working[:m.start()]

                start_x = len(clean_text)
                if m == m_link:
                    url, label = m.group(1), m.group(2)
                    clean_text += f"[{label}]"
                    spans.append(InteractiveSpan(start_x, len(clean_text), 'link', url))
                else:
                    label = m.group(1)
                    clean_text += f"[ {label} ]"
                    spans.append(InteractiveSpan(start_x, len(clean_text), 'input', label))

                working = working[m.end():]

            clean_text += working
            final_lines.append(RichLine(clean_text, attr, spans))

        return final_lines

    # ------------------------------------------------------------------
    # In-page search
    # ------------------------------------------------------------------

    def _clear_search(self):
        self._search_query = ""
        self._search_matches = []
        self._search_idx = -1

    def _find_matches(self, query):
        """Find all line indices containing query (case-insensitive)."""
        if not query:
            return []
        q = query.lower()
        return [i for i, rl in enumerate(self.content) if q in rl.text.lower()]

    def _search_next(self):
        """Jump to next search match."""
        if not self._search_matches:
            return
        self._search_idx = (self._search_idx + 1) % len(self._search_matches)
        self.scroll_y = max(0, self._search_matches[self._search_idx] - 2)

    def _search_prev(self):
        """Jump to previous search match."""
        if not self._search_matches:
            return
        self._search_idx = (self._search_idx - 1) % len(self._search_matches)
        self.scroll_y = max(0, self._search_matches[self._search_idx] - 2)

    def execute_search(self, query):
        """Called when search input dialog completes."""
        self._search_query = query
        self._search_matches = self._find_matches(query)
        self._search_idx = -1
        if self._search_matches:
            self._search_next()
        return ActionResult(ActionType.REFRESH)

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def _sidebar_width(self, bw):
        """Compute sidebar width when visible."""
        return min(24, bw // 3)

    def draw(self, stdscr):
        if not self.visible: return
        body_attr = self.draw_frame(stdscr)
        bx, by, bw, bh = self.body_rect()

        # Full clear
        for i in range(bh):
            safe_addstr(stdscr, by + i, bx, ' ' * bw, body_attr)

        content_x = bx
        content_w = bw

        # Sidebar (History)
        if self.show_sidebar:
            sidebar_w = self._sidebar_width(bw)
            content_x += sidebar_w
            content_w -= sidebar_w
            for i in range(bh):
                safe_addstr(stdscr, by + i, bx + sidebar_w - 1, "│", self.attr_inactive)
            safe_addstr(stdscr, by, bx + 1, "HISTORY", self.attr_title)
            hist = self._back_stack[-max(1, bh - 2):]
            for i, h_url in enumerate(hist):
                display = urllib.parse.unquote(h_url)[:sidebar_w - 3]
                safe_addstr(stdscr, by + 1 + i, bx + 1, display, self.attr_dim)

        # Navigation bar: ◀ ▶ 🔒 [url...]
        nav_y = by
        lock_icon = "🔒" if self.url.startswith('https') else "🔓"
        back_ch = "◀" if self._back_stack else "◁"
        fwd_ch = "▶" if self._forward_stack else "▷"
        nav_prefix = f" {back_ch} {fwd_ch} {lock_icon} "
        safe_addstr(stdscr, nav_y, content_x + 1, nav_prefix, body_attr | self.attr_bold)

        addr_start = content_x + 1 + len(nav_prefix)
        addr_width = max(1, content_w - len(nav_prefix) - 4)
        display_url = urllib.parse.unquote(self.url)
        safe_addstr(stdscr, nav_y, addr_start, display_url.ljust(addr_width)[:addr_width], self.attr_inactive)

        # Loading animation
        if self.is_loading:
            spinner = self.loading_chars[self.loading_frame % len(self.loading_chars)]
            self.loading_frame += 1
            safe_addstr(stdscr, nav_y, bx + bw - 4, f" {spinner} ", self.attr_title | self.attr_bold)

        # Content area
        content_y_start = by + 2
        content_h = max(1, bh - 3)
        with self._lock:
            visible_lines = self.content[self.scroll_y : self.scroll_y + content_h]

        search_set = set(self._search_matches) if self._search_query else set()
        current_match = self._search_matches[self._search_idx] if 0 <= self._search_idx < len(self._search_matches) else -1
        for i, rline in enumerate(visible_lines):
            line_attr = rline.attr if rline.attr else body_attr
            text = rline.text[:content_w - 2]
            abs_idx = self.scroll_y + i
            if abs_idx in search_set:
                if abs_idx == current_match:
                    line_attr = curses.A_REVERSE | curses.A_BOLD
                else:
                    line_attr = curses.A_REVERSE
            safe_addstr(stdscr, content_y_start + i, content_x + 1, text, line_attr)

        # Scrollbar
        with self._lock:
            total = len(self.content)
        if total > content_h and content_h > 0:
            scroll_h = max(1, int(content_h * content_h / total))
            scroll_pos = int(self.scroll_y * content_h / total)
            for i in range(content_h):
                char = "┃" if scroll_pos <= i < scroll_pos + scroll_h else "│"
                safe_addstr(stdscr, content_y_start + i, bx + bw - 1, char, self.attr_inactive)

        # Footer
        help_y = by + bh - 1
        if self._search_query:
            idx_display = self._search_idx + 1 if self._search_idx >= 0 else 0
            match_info = f" /{self._search_query}  [{idx_display}/{len(self._search_matches)}]  [n]Next [N]Prev [Esc]Clear "
            safe_addstr(stdscr, help_y, bx + 1, match_info[:bw - 2], self.attr_title)
        else:
            help_txt = " [◀/▶]Nav [G]Go [H]Hist [/]Find [PgUp/Dn]Scroll "
            safe_addstr(stdscr, help_y, bx + 1, help_txt[:bw - 2], self.attr_title)

    # ------------------------------------------------------------------
    # Mouse
    # ------------------------------------------------------------------

    def handle_click(self, mx, my):
        bx, by, bw, bh = self.body_rect()
        sidebar_w = self._sidebar_width(bw) if self.show_sidebar else 0
        content_x = bx + sidebar_w

        # Sidebar click — navigate to history entry
        if self.show_sidebar and bx <= mx < bx + sidebar_w - 1:
            idx = my - (by + 1)
            hist = self._back_stack[-max(1, bh - 2):]
            if 0 <= idx < len(hist):
                self._load_url(hist[idx])
                return ActionResult(ActionType.REFRESH)

        # Navigation bar click
        if my == by and content_x <= mx:
            rel = mx - (content_x + 1)
            if 0 <= rel <= 3:
                return self._go_back() or ActionResult(ActionType.REFRESH)
            if 4 <= rel <= 7:
                return self._go_forward() or ActionResult(ActionType.REFRESH)
            return ActionResult(ActionType.REQUEST_URL, self.url)

        # Content area clicks
        content_y_start = by + 2
        content_h = max(1, bh - 3)
        if content_y_start <= my < content_y_start + content_h:
            line_idx = self.scroll_y + (my - content_y_start)
            with self._lock:
                rline = self.content[line_idx] if line_idx < len(self.content) else None
            if rline:
                relative_mx = mx - content_x
                for span in rline.spans:
                    if span.start_x <= relative_mx < span.end_x:
                        if span.type == 'link':
                            target_url = span.payload
                            if not target_url.startswith('http'):
                                target_url = urllib.parse.urljoin(self.url, target_url)
                            self._load_url(target_url)
                            return ActionResult(ActionType.REFRESH)
                        elif span.type == 'input':
                            if "google" in self.url or "duckduckgo" in self.url:
                                return ActionResult(ActionType.REQUEST_URL, "duckduckgo.com/html/?q=")
                            return ActionResult(ActionType.REQUEST_URL, span.payload)

        return super().handle_click(mx, my)

    # ------------------------------------------------------------------
    # Keyboard
    # ------------------------------------------------------------------

    def handle_key(self, key):
        code = normalize_key_code(key)
        _, _, _, bh = self.body_rect()
        content_h = max(1, bh - 3)

        # Search mode: n/N/Esc override normal keys
        if self._search_query:
            if code == ord('n'):
                self._search_next()
                return ActionResult(ActionType.REFRESH)
            if code == ord('N'):
                self._search_prev()
                return ActionResult(ActionType.REFRESH)
            if code == 27:  # Escape
                self._clear_search()
                return ActionResult(ActionType.REFRESH)

        if code == curses.KEY_DOWN:
            with self._lock:
                max_scroll = max(0, len(self.content) - content_h)
            if self.scroll_y < max_scroll:
                self.scroll_y += 1
        elif code == curses.KEY_UP:
            if self.scroll_y > 0:
                self.scroll_y -= 1
        elif code == curses.KEY_NPAGE:  # Page Down
            with self._lock:
                max_scroll = max(0, len(self.content) - content_h)
            self.scroll_y = min(max_scroll, self.scroll_y + content_h)
        elif code == curses.KEY_PPAGE:  # Page Up
            self.scroll_y = max(0, self.scroll_y - content_h)
        elif code == curses.KEY_HOME:
            self.scroll_y = 0
        elif code == curses.KEY_END:
            with self._lock:
                max_scroll = max(0, len(self.content) - content_h)
            self.scroll_y = max_scroll
        elif code == curses.KEY_LEFT:
            return self._go_back()
        elif code == curses.KEY_RIGHT:
            return self._go_forward()
        elif code in (ord('h'), ord('H')):
            self.show_sidebar = not self.show_sidebar
        elif code in (ord('g'), ord('G')):
            return ActionResult(ActionType.REQUEST_URL, self.url)
        elif code == ord('/'):
            return ActionResult(ActionType.REQUEST_URL, "search:")
        return super().handle_key(key)

    def open_path(self, path):
        """Navigate to URL, or run in-page search if prefixed with 'search:'."""
        if path and path.startswith("search:"):
            query = path[7:].strip()
            if query:
                return self.execute_search(query)
            return None
        self._load_url(path)
        return None
