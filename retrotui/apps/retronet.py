"""RetroNet Explorer Ultra: The state-of-the-art text browser."""
import curses
import urllib.request
import urllib.parse
import re
import html
import threading
import ssl
from dataclasses import dataclass
from typing import List, Tuple

from ..ui.window import Window
from ..utils import safe_addstr, theme_attr, normalize_key_code
from ..core.actions import ActionResult, ActionType

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
        self.history = []
        self.scroll_y = 0
        self.is_loading = False
        self.show_sidebar = False
        self.loading_frame = 0
        self.loading_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
        
        # Pre-resolve attributes for thread safety
        self.attr_title = theme_attr('window_title')
        self.attr_error = theme_attr('error')
        self.attr_dim = curses.A_DIM
        self.attr_bold = curses.A_BOLD
        self.attr_inactive = theme_attr('window_inactive')
        self.attr_body = theme_attr('window_body')
        
        self._load_url(self.url)

    def _sanitize_url(self, url):
        """Encode spaces and special characters for network, but keep it readable."""
        if not url: return ""
        
        # DuckDuckGo Bridge: Clean and simple
        if "google.com/search?q=" in url or "duckduckgo.com/?q=" in url:
            query = ""
            if "?q=" in url:
                query = url.split("?q=", 1)[1]
            # Use quote_plus for '+' spaces which is cleaner
            return f"https://duckduckgo.com/html/?q={urllib.parse.quote_plus(urllib.parse.unquote(query))}"
        
        try:
            parts = list(urllib.parse.urlsplit(url))
            if not parts[0]:
                 return self._sanitize_url('http://' + url)
            parts[2] = urllib.parse.quote(parts[2])
            parts[3] = urllib.parse.quote(parts[3], safe='=&')
            return urllib.parse.urlunsplit(parts)
        except Exception:
            return url

    def _load_url(self, url):
        if not url: return
        
        # Keep clean URL for display/history, used sanitized for fetch
        clean_url = url
        sanitized_url = self._sanitize_url(url)
        
        if self.url and self.url not in self.history:
            self.history.append(self.url)
            
        self.url = clean_url
        self.content = [RichLine("Loading...", self.attr_title)]
        self.is_loading = True
        self.scroll_y = 0

        thread = threading.Thread(target=self._fetch_thread, args=(sanitized_url,), daemon=True)
        thread.start()

    def _fetch_thread(self, url):
        try:
            # Modern "Stealth" Headers
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            context = ssl._create_unverified_context()
            
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10, context=context) as response:
                charset = response.info().get_content_charset() or 'utf-8'
                raw_html = response.read().decode(charset, errors='ignore')
                self.content = self._parse_html(raw_html)
        except BaseException as e:
            # Use pre-resolved attributes ONLY here
            msg = str(e) if str(e) else "Unknown network error or crash."
            self.content = [
                RichLine(f"Error loading {url}:", self.attr_error),
                RichLine(msg, self.attr_dim)
            ]
        finally:
            self.is_loading = False

    def _parse_html(self, raw_html):
        """Ultra parser with style and structure support."""
        # Clean scripts, styles, and SVG/Head/Nav (optional but helps)
        text = re.sub(r'<(script|style|svg|head|noscript).*?>.*?</\1>', '', raw_html, flags=re.DOTALL | re.IGNORECASE)
        
        # Title
        title_match = re.search(r'<title>(.*?)</title>', text, re.IGNORECASE | re.DOTALL)
        if title_match:
            self.title = f"RetroNet Ultra - {html.unescape(title_match.group(1)).strip()[:30]}"

        # 1. Headers
        text = re.sub(r'<h[1-3].*?>(.*?)</h[1-3]>', r'\n\n[H1]\1[/H]\n', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<h[4-6].*?>(.*?)</h[4-6]>', r'\n\n[H2]\1[/H]\n', text, flags=re.DOTALL | re.IGNORECASE)
        
        # 2. Bold/Strong
        text = re.sub(r'<(b|strong).*?>(.*?)</\1>', r'[B]\2[/B]', text, flags=re.DOTALL | re.IGNORECASE)
        
        # 3. Inputs/Buttons (Flatten them)
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

        # 4. Links: Flatten them!
        def render_link(match):
            href_m = re.search(r'href=["\'](.*?)["\']', match.group(0), re.I)
            url = href_m.group(1) if href_m else "#"
            label = match.group(1)
            # Remove newlines to keep token on a single line
            url = url.replace('\n', '').strip()
            label = label.replace('\n', ' ').strip()
            if not label: label = url[:20]
            return f"[L]{url}|{label}[/L]"
        
        text = re.sub(r'<a\s+.*?>(.*?)</a>', render_link, text, flags=re.DOTALL | re.IGNORECASE)
        
        # 5. Block elements & cleanup
        text = re.sub(r'<(p|div|li|br|form|tr|hr).*?>', r'\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<.*?>', '', text) # Strip remaining tags
        text = html.unescape(text)

        # 6. Post-process tokens into RichLine objects
        final_lines = []
        for line_raw in text.splitlines():
            line_raw = line_raw.strip()
            if not line_raw:
                if final_lines and final_lines[-1].text != "":
                    final_lines.append(RichLine(""))
                continue
            
            # Complex token parser
            attr = 0
            spans = []
            
            # Line attributes
            if "[H1]" in line_raw:
                attr = curses.A_BOLD | curses.A_UNDERLINE
                line_raw = line_raw.replace("[H1]", "").replace("[/H]", "")
            elif "[H2]" in line_raw:
                attr = curses.A_BOLD
                line_raw = line_raw.replace("[H2]", "").replace("[/H]", "")
            
            clean_text = " " # Modern indent
            if attr & curses.A_BOLD: clean_text = "» "
            
            working = line_raw
            while True:
                # Use non-greedy match for everything
                m_link = re.search(r'\[L\](.*?)\|(.*?)\[/L\]', working)
                m_btn = re.search(r'\[BT\](.*?)\[/BT\]', working)
                
                indices = [i for i in [m_link, m_btn] if i]
                if not indices: break
                m = min(indices, key=lambda x: x.start())
                
                # Pre-match text
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

    def draw(self, stdscr):
        if not self.visible: return
        body_attr = self.draw_frame(stdscr)
        bx, by, bw, bh = self.body_rect()
        
        # Full clear
        for i in range(bh):
            safe_addstr(stdscr, by + i, bx, ' ' * bw, body_attr)

        content_x = bx
        content_w = bw
        
        # Sidebar logic (History)
        if self.show_sidebar:
            sidebar_w = 20
            content_x += sidebar_w
            content_w -= sidebar_w
            # Draw Sidebar separator and content
            for i in range(bh):
                safe_addstr(stdscr, by + i, bx + sidebar_w - 1, "│", self.attr_inactive)
            safe_addstr(stdscr, by, bx + 1, "HISTORY", self.attr_title)
            for i, h_url in enumerate(self.history[-bh+2:]):
                safe_addstr(stdscr, by + 1 + i, bx + 1, h_url[:sidebar_w-3], self.attr_dim)

        # Header: Address Bar with Modern Icon
        lock_icon = "🔒" if self.url.startswith('https') else "🔓"
        safe_addstr(stdscr, by, content_x + 1, f" {lock_icon} Address: ", body_attr | self.attr_bold)
        addr_width = content_w - 18
        
        # Display unquoted, human-friendly URL
        display_url = urllib.parse.unquote(self.url)
        safe_addstr(stdscr, by, content_x + 15, display_url.ljust(addr_width)[:addr_width], self.attr_inactive)
        
        # Loading Animation
        if self.is_loading:
            spinner = self.loading_chars[self.loading_frame % len(self.loading_chars)]
            self.loading_frame += 1
            safe_addstr(stdscr, by, bx + bw - 4, f" {spinner} ", self.attr_title | self.attr_bold)

        # Content Area
        content_y_start = by + 2
        content_h = bh - 3
        visible_lines = self.content[self.scroll_y : self.scroll_y + content_h]
        
        for i, rline in enumerate(visible_lines):
            line_attr = rline.attr if rline.attr else body_attr
            text = rline.text[:content_w - 2]
            safe_addstr(stdscr, content_y_start + i, content_x + 1, text, line_attr)

        # Modern Scrollbar
        if len(self.content) > content_h:
            scroll_h = max(1, int(content_h * content_h / len(self.content)))
            scroll_pos = int(self.scroll_y * content_h / len(self.content))
            for i in range(content_h):
                char = "┃" if scroll_pos <= i < scroll_pos + scroll_h else "│"
                safe_addstr(stdscr, content_y_start + i, bx + bw - 1, char, self.attr_inactive)

        # Footer Help
        help_y = by + bh - 1
        help_txt = " [G] Go  [H] Hist [UP/DN] Scroll "
        safe_addstr(stdscr, help_y, bx + 1, help_txt, self.attr_title)

    def handle_click(self, mx, my):
        bx, by, bw, bh = self.body_rect()
        # Address bar click
        if by <= my <= by + 1 and bx <= mx <= bx + bw:
            return ActionResult(ActionType.REQUEST_URL, self.url)
        
        # Content Area clicks
        content_y_start = by + 2
        content_h = bh - 3
        if content_y_start <= my < content_y_start + content_h:
            line_idx = self.scroll_y + (my - content_y_start)
            if line_idx < len(self.content):
                rline = self.content[line_idx]
                # Sidebar offset check
                content_x = bx + (20 if self.show_sidebar else 0)
                relative_mx = mx - content_x
                
                for span in rline.spans:
                    if span.start_x <= relative_mx < span.end_x:
                        if span.type == 'link':
                            # Open link
                            target_url = span.payload
                            if not target_url.startswith('http'):
                                # Handle relative? Simple version for now: concat
                                from urllib.parse import urljoin
                                target_url = urljoin(self.url, target_url)
                            self._load_url(target_url)
                            return ActionResult(ActionType.REFRESH)
                        elif span.type == 'input':
                            # Trigger input dialog for "searching"
                            # In Ultra, we simulate interactive forms. 
                            # Since we don't have full POST support, we redirect to a search if it looks like one.
                            if "google" in self.url:
                                return ActionResult(ActionType.REQUEST_URL, "google.com/search?q=")
                            return ActionResult(ActionType.REQUEST_URL, span.payload)
        
        return super().handle_click(mx, my)

    def handle_key(self, key):
        code = normalize_key_code(key)
        if code == curses.KEY_DOWN:
            if self.scroll_y < len(self.content) - (self.h - 6):
                self.scroll_y += 1
        elif code == curses.KEY_UP:
            if self.scroll_y > 0:
                self.scroll_y -= 1
        elif code == ord('h') or code == ord('H'):
            self.show_sidebar = not self.show_sidebar
        elif code in (ord('g'), ord('G')):
            return ActionResult(ActionType.REQUEST_URL, self.url)
        return super().handle_key(key)

    def open_path(self, path):
        self._load_url(path)
        return None
