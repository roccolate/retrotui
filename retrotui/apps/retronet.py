"""RetroNet Explorer Ultra: The state-of-the-art text browser."""
import curses
import hashlib
import logging
import os
import tempfile
import urllib.request
import urllib.parse
import re
import html.parser
import threading
import ssl
import socket
import http.client
from dataclasses import dataclass
from typing import List, Tuple

from ..ui.window import Window
from ..utils import safe_addstr, theme_attr, normalize_key_code
from ..core.actions import ActionResult, ActionType, AppAction
from ..constants import _CURSES_ERROR

LOGGER = logging.getLogger(__name__)

# Compiled once: per-line parse would otherwise rebuild the patterns
# for every line on every page fetch (Python's regex cache helps but
# is contention-prone under concurrent fetches).
_LINK_RE = re.compile(r'\[L\](.*?)\|(.*?)\[/L\]')
_BTN_RE = re.compile(r'\[BT\](.*?)\[/BT\]')


class _ResponseTooLargeError(Exception):
    """Raised when a network response exceeds the configured limit."""


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
    ConnectionError,
    _ResponseTooLargeError,
)
_RESPONSE_CLOSE_ERRORS = (
    AttributeError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)

_MAX_HISTORY = 200
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class _RetroNetHTMLParser(html.parser.HTMLParser):
    """Walk HTML and emit the same inline tokens the old regex pipeline emitted.

    Produces a flat text stream plus a title string. Inline tokens ([H1], [H2],
    [B], [I], [L]url|label[/L], [BT]label[/BT]) match what the downstream
    post-processing in ``RetroNetWindow._parse_html`` already understands, so
    swapping the parser is invisible to the renderer.

    Handles nested tags correctly (the old ``re.sub`` pipeline flattened
    ``<b><i>x</i></b>`` and similar into whatever order the global regexes
    happened to fire). ``convert_charrefs=True`` decodes HTML entities in text
    content and ``<title>``, matching the previous ``html.unescape`` call.
    """

    BLOCK_TAGS = frozenset({'p', 'div', 'li', 'tr', 'form'})
    HEADERS = frozenset({'h1', 'h2', 'h3', 'h4', 'h5', 'h6'})
    SKIP_TAGS = frozenset({'script', 'style', 'svg', 'noscript'})

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip_depth = 0
        self.in_title = False
        self.title_parts = []
        self.link_href = None
        self.link_label = []
        self.in_button = False
        self.button_label = []

    def handle_starttag(self, tag, attrs):
        t = tag.lower()
        if t in self.SKIP_TAGS or t == 'head':
            self.skip_depth += 1
            return
        if t == 'title':
            self.in_title = True
            return
        if t == 'br':
            self._emit('\n')
            return
        if t == 'hr':
            self._emit('\n\n')
            return
        if t in self.BLOCK_TAGS:
            self._emit('\n')
            return
        if t in self.HEADERS:
            self._emit('\n\n')
            self._emit('[H1]' if t in ('h1', 'h2', 'h3') else '[H2]')
            return
        if t in ('b', 'strong'):
            self._emit('[B]')
            return
        if t in ('i', 'em'):
            self._emit('[I]')
            return
        if t == 'a':
            href = dict(attrs).get('href', '') or ''
            self.link_href = href
            self.link_label = []
            return
        if t == 'input':
            attrs_d = dict(attrs)
            if attrs_d.get('type', '').lower() == 'hidden':
                return
            label = (attrs_d.get('value') or attrs_d.get('placeholder') or 'Submit').strip()
            self._emit(f' [BT]{label} [/BT] ')
            return
        if t == 'button':
            self.in_button = True
            self.button_label = []
            return

    def handle_endtag(self, tag):
        t = tag.lower()
        if t in self.SKIP_TAGS or t == 'head':
            if self.skip_depth > 0:
                self.skip_depth -= 1
            return
        if t == 'title':
            self.in_title = False
            return
        if t in self.HEADERS:
            self._emit('[/H]')
            return
        if t in ('b', 'strong'):
            self._emit('[/B]')
            return
        if t in ('i', 'em'):
            self._emit('[/I]')
            return
        if t == 'a':
            label = ''.join(self.link_label).strip()
            url = (self.link_href or '#').replace('\n', '').strip()
            if not label:
                label = url[:20]
            self.parts.append(f'[L]{url}|{label}[/L]')
            self.link_href = None
            self.link_label = []
            return
        if t == 'button':
            label = ''.join(self.button_label).strip().replace('\n', ' ') or 'Submit'
            self.parts.append(f' [BT]{label} [/BT] ')
            self.in_button = False
            self.button_label = []
            return

    def handle_data(self, data):
        if self.in_title:
            self.title_parts.append(data)
            return
        if self.skip_depth > 0:
            return
        if self.in_button:
            self.button_label.append(data)
            return
        if self.link_href is not None:
            self.link_label.append(data)
            # Mirror the data into the visible text stream so a
            # malformed page that never emits a matching ``</a>``
            # doesn't silently drop everything from the unclosed
            # anchor onward. The link is still lost (no closing
            # href) but the content is preserved for display.
            self.parts.append(data)
            return
        self.parts.append(data)

    def handle_pi(self, data):
        pass

    def handle_decl(self, decl):
        pass

    def handle_comment(self, data):
        pass

    def _emit(self, text):
        if self.in_button:
            self.button_label.append(text)
        elif self.link_href is not None:
            self.link_label.append(text)
        else:
            self.parts.append(text)

    def get_title(self):
        return ''.join(self.title_parts).strip()

    def get_text(self):
        return ''.join(self.parts)

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


@dataclass
class _TabState:
    """Per-tab browser state. Mutated under ``RetroNetWindow._lock``."""

    url: str = ""
    title: str = ""
    content: List[RichLine] = None
    back_stack: list = None
    forward_stack: list = None
    scroll_y: int = 0
    is_loading: bool = False
    search_query: str = ""
    search_matches: list = None
    search_idx: int = -1
    loading_frame: int = 0
    raw_html: str = ""
    tab_id: int = 0
    load_generation: int = 0

    def __post_init__(self):
        if self.content is None:
            self.content = []
        if self.back_stack is None:
            self.back_stack = []
        if self.forward_stack is None:
            self.forward_stack = []
        if self.search_matches is None:
            self.search_matches = []


_DEFAULT_TAB_URL = "http://text.npr.org"


class RetroNetWindow(Window):
    """Nostalgic yet ultra-modern text browser."""


def _cleanup_stale_viewsource_files(max_age_seconds: int = 7 * 24 * 3600):
    """Remove stale ``retrotui_retronet_viewsource_*.html`` temp files.

    One file per URL is written when the user opens the page source.
    The path is derived from a hash of the URL so two windows on the
    same page share the file, but a long-running session otherwise
    accumulates files. Sweep anything older than ``max_age_seconds``
    at startup.
    """
    try:
        import glob
        import os
        import time

        tmp_dir = tempfile.gettempdir()
        now = time.time()
        for path in glob.glob(
            os.path.join(tmp_dir, "retrotui_retronet_viewsource_*.html")
        ):
            try:
                mtime = os.path.getmtime(path)
            except OSError:
                continue
            if now - mtime > max_age_seconds:
                try:
                    os.unlink(path)
                except OSError:
                    pass
    except Exception:
        # Cleanup is best-effort; never let a sweep failure break
        # the rest of the app's startup.
        LOGGER.debug("viewsource cleanup failed", exc_info=True)


class RetroNetWindow(Window):

    def __init__(self, x, y, w, h):
        super().__init__('RetroNet Explorer Ultra', x, y, w, h)
        self.show_sidebar = False
        self.loading_chars = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

        # Pre-resolve attributes for thread safety
        self.attr_title = theme_attr('window_title')
        self.attr_error = theme_attr('error')
        self.attr_dim = curses.A_DIM
        self.attr_bold = curses.A_BOLD
        self.attr_inactive = theme_attr('window_inactive')
        self.attr_body = theme_attr('window_body')

        # Shared state lock for fetch thread + tab mutations.
        self._lock = threading.Lock()

        self.tabs: List[_TabState] = []
        self.active_tab_idx = 0
        self._next_tab_id = 1
        self._new_tab(_DEFAULT_TAB_URL, activate=True, _push_history=False)
        # Sweep stale ``viewsource`` temp files (one per URL) at startup
        # so a long-running session doesn't slowly fill ``$TMPDIR``.
        _cleanup_stale_viewsource_files()

    # ------------------------------------------------------------------
    # Tab management
    # ------------------------------------------------------------------

    def _cur(self) -> _TabState:
        """Return the active tab, or None if tabs haven't been initialised yet."""
        tabs = getattr(self, 'tabs', None)
        if not tabs:
            return None
        if self.active_tab_idx >= len(tabs):
            self.active_tab_idx = max(0, len(tabs) - 1)
        return tabs[self.active_tab_idx]

    def _tab_index_by_id_locked(self, tab_id):
        for index, tab in enumerate(self.tabs):
            if tab.tab_id == tab_id:
                return index
        return None

    def _tab_request_is_current_locked(self, tab_id, generation):
        index = self._tab_index_by_id_locked(tab_id)
        if index is None:
            return None
        tab = self.tabs[index]
        if tab.load_generation != generation:
            return None
        return index

    def _new_tab(self, url="", *, activate=True, _push_history=True) -> int:
        """Create a new tab. Returns the new tab index."""
        with self._lock:
            tab_id = int(getattr(self, '_next_tab_id', 1))
            self._next_tab_id = tab_id + 1
            tab = _TabState(url=url, tab_id=tab_id)
            self.tabs.append(tab)
            new_idx = len(self.tabs) - 1
            if activate:
                self.active_tab_idx = new_idx
        # The new tab has no prior URL to push to its back stack, so the
        # initial load never pushes history even when the caller asked for it.
        if url and activate:
            self._load_url(url, _push_history=False, _tab_idx=new_idx)
        elif activate:
            self._refresh_window_title()
        return new_idx

    def _close_tab(self, idx: int) -> bool:
        """Close a tab. Returns True if the window should be closed (last tab)."""
        with self._lock:
            if idx < 0 or idx >= len(self.tabs):
                return False
            was_active = idx == self.active_tab_idx
            del self.tabs[idx]
            if not self.tabs:
                return True
            if was_active:
                # Closing the active tab: pick the neighbour at the
                # same index (i.e. the tab that "slides into" the slot),
                # clamped to the new length. Jumping to the last tab
                # when the user closed the middle one was jarring.
                self.active_tab_idx = min(idx, len(self.tabs) - 1)
            elif self.active_tab_idx > idx:
                self.active_tab_idx -= 1
        self._refresh_window_title()
        return False

    def _switch_tab(self, idx: int):
        with self._lock:
            if idx < 0 or idx >= len(self.tabs):
                return
            self.active_tab_idx = idx
        self._refresh_window_title()

    def _cycle_tab(self, delta: int):
        with self._lock:
            if not self.tabs:
                return
            self.active_tab_idx = (self.active_tab_idx + delta) % len(self.tabs)
        self._refresh_window_title()

    def _refresh_window_title(self):
        """Set self.title (window title bar) from the active tab."""
        cur = self._cur()
        if cur is None:
            self.title = "RetroNet Explorer Ultra"
            return
        page_title = (cur.title or "").strip()
        if page_title:
            self.title = f"RetroNet Ultra - {page_title[:30]}"
        elif cur.url:
            self.title = f"RetroNet Ultra - {cur.url[:30]}"
        else:
            self.title = "RetroNet Explorer Ultra"

    # ------------------------------------------------------------------
    # Backward-compatible per-tab properties. External callers (tests,
    # toolbar callbacks) can keep using ``win.url`` and get the active tab.
    # Writes mutate the active tab.
    # ------------------------------------------------------------------

    @property
    def url(self) -> str:
        cur = self._cur()
        return cur.url if cur else ""

    @url.setter
    def url(self, value: str):
        cur = self._cur()
        if cur is not None:
            cur.url = value

    @property
    def content(self) -> list:
        cur = self._cur()
        return cur.content if cur else []

    @content.setter
    def content(self, value: list):
        cur = self._cur()
        if cur is not None and self.tabs:
            cur.content = value

    @property
    def scroll_y(self) -> int:
        cur = self._cur()
        return cur.scroll_y if cur else 0

    @scroll_y.setter
    def scroll_y(self, value: int):
        cur = self._cur()
        if cur is not None:
            cur.scroll_y = value

    @property
    def is_loading(self) -> bool:
        cur = self._cur()
        return cur.is_loading if cur else False

    @is_loading.setter
    def is_loading(self, value: bool):
        cur = self._cur()
        if cur is not None:
            cur.is_loading = value

    @property
    def _back_stack(self) -> list:
        cur = self._cur()
        return cur.back_stack if cur else []

    @_back_stack.setter
    def _back_stack(self, value: list):
        cur = self._cur()
        if cur is not None:
            cur.back_stack = value

    @property
    def _forward_stack(self) -> list:
        cur = self._cur()
        return cur.forward_stack if cur else []

    @_forward_stack.setter
    def _forward_stack(self, value: list):
        cur = self._cur()
        if cur is not None:
            cur.forward_stack = value

    @property
    def _search_query(self) -> str:
        cur = self._cur()
        return cur.search_query if cur else ""

    @_search_query.setter
    def _search_query(self, value: str):
        cur = self._cur()
        if cur is not None:
            cur.search_query = value

    @property
    def _search_matches(self) -> list:
        cur = self._cur()
        return cur.search_matches if cur else []

    @_search_matches.setter
    def _search_matches(self, value: list):
        cur = self._cur()
        if cur is not None:
            cur.search_matches = value

    @property
    def _search_idx(self) -> int:
        cur = self._cur()
        return cur.search_idx if cur else -1

    @_search_idx.setter
    def _search_idx(self, value: int):
        cur = self._cur()
        if cur is not None:
            cur.search_idx = value

    # ------------------------------------------------------------------
    # URL handling
    # ------------------------------------------------------------------

    _ALLOWED_URL_SCHEMES = ("http", "https")

    def _sanitize_url(self, url):
        """Encode spaces and special characters for network, but keep it readable."""
        if not url: return ""

        # Reject non-http(s) schemes — clicking a ``file://`` link would
        # let a remote page read local files through ``urlopen``.
        scheme = urllib.parse.urlsplit(url).scheme.lower()
        if scheme and scheme not in self._ALLOWED_URL_SCHEMES:
            return ""

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

    def _load_url(self, url, *, _push_history=True, _tab_idx=None):
        if not url: return

        clean_url = url
        sanitized_url = self._sanitize_url(url)

        with self._lock:
            tab_idx = _tab_idx if _tab_idx is not None else self.active_tab_idx
            tab = self.tabs[tab_idx]
            if _push_history and tab.url:
                # Deduplicate the previous entry to keep consecutive reloads
                # from polluting the back stack.
                if not tab.back_stack or tab.back_stack[-1] != tab.url:
                    tab.back_stack.append(tab.url)
                    if len(tab.back_stack) > _MAX_HISTORY:
                        tab.back_stack = tab.back_stack[-_MAX_HISTORY:]
                tab.forward_stack.clear()

            tab.url = clean_url
            tab.content = [RichLine("Loading...", self.attr_title)]
            tab.is_loading = True
            tab.scroll_y = 0
            tab.search_query = ""
            tab.search_matches = []
            tab.search_idx = -1
            tab.load_generation += 1
            tab_id = tab.tab_id
            generation = tab.load_generation
        self._refresh_window_title()

        thread = self._start_worker(
            self._fetch_thread,
            sanitized_url,
            tab_id,
            generation,
            name=f'retrotui-fetch-{tab_id}',
        )
        if thread is None:
            with self._lock:
                current_idx = self._tab_request_is_current_locked(tab_id, generation)
                if current_idx is not None:
                    self.tabs[current_idx].is_loading = False

    def _go_back(self):
        with self._lock:
            tab = self._cur()
            if not tab or not tab.back_stack:
                return None
            tab.forward_stack.append(tab.url)
            prev = tab.back_stack.pop()
        self._load_url(prev, _push_history=False)
        return ActionResult(ActionType.REFRESH)

    def _go_forward(self):
        with self._lock:
            tab = self._cur()
            if not tab or not tab.forward_stack:
                return None
            tab.back_stack.append(tab.url)
            nxt = tab.forward_stack.pop()
        self._load_url(nxt, _push_history=False)
        return ActionResult(ActionType.REFRESH)

    # ------------------------------------------------------------------
    # Network
    # ------------------------------------------------------------------

    def _fetch_thread(self, cancel_event, url=None, tab_id=None, generation=None):
        # Legacy direct call: _fetch_thread(url, tab_index). Resolve that
        # index once to the stable request identity used by the runtime path.
        if not callable(getattr(cancel_event, "is_set", None)):
            legacy_url = cancel_event
            legacy_tab_idx = url
            cancel_event = threading.Event()
            url = legacy_url
            with self._lock:
                try:
                    tab = self.tabs[int(legacy_tab_idx)]
                except (IndexError, TypeError, ValueError):
                    return
                tab_id = tab.tab_id
                generation = tab.load_generation
        if cancel_event.is_set():
            return
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
            req = urllib.request.Request(url, headers=headers)
            response = urllib.request.urlopen(req, timeout=10, context=context)
            try:
                charset = response.info().get_content_charset() or 'utf-8'
                raw_bytes = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw_bytes) > MAX_RESPONSE_BYTES:
                    raise _ResponseTooLargeError(
                        f"Response exceeds {MAX_RESPONSE_BYTES // (1024 * 1024)} MiB limit."
                    )
                raw_html = raw_bytes.decode(charset, errors='ignore')
            finally:
                try:
                    response.close()
                except _RESPONSE_CLOSE_ERRORS:
                    pass
            if cancel_event.is_set():
                return
            with self._lock:
                current_idx = self._tab_request_is_current_locked(tab_id, generation)
                if current_idx is None:
                    return
                self.tabs[current_idx].raw_html = raw_html
            parsed = self._parse_html(
                raw_html,
                tab_id=tab_id,
                generation=generation,
            )
            if cancel_event.is_set():
                return
            with self._lock:
                current_idx = self._tab_request_is_current_locked(tab_id, generation)
                if current_idx is None:
                    return
                self.tabs[current_idx].content = parsed
                self.tabs[current_idx].is_loading = False
                if current_idx == self.active_tab_idx:
                    self._refresh_window_title()
        except _RETRONET_FETCH_ERRORS as e:
            msg = str(e) if str(e) else "Unknown network error or crash."
            LOGGER.warning("Failed to load %s: %s", url, msg)
            with self._lock:
                current_idx = self._tab_request_is_current_locked(tab_id, generation)
                if current_idx is not None and not cancel_event.is_set():
                    self.tabs[current_idx].content = [
                        RichLine(f"Error loading {url}:", self.attr_error),
                        RichLine(msg, self.attr_dim)
                    ]
                    self.tabs[current_idx].is_loading = False
        except Exception:
            # Catch-all for the parser / decode path; log so future
            # regressions are diagnosable from the user's terminal log.
            LOGGER.exception("Unhandled exception while loading %s", url)
            with self._lock:
                current_idx = self._tab_request_is_current_locked(tab_id, generation)
                if current_idx is not None and not cancel_event.is_set():
                    self.tabs[current_idx].is_loading = False

    def close(self):
        """Cancel fetch ownership and invalidate every in-flight navigation."""
        result = super().close()
        with self._lock:
            for tab in self.tabs:
                tab.load_generation += 1
                tab.is_loading = False
        return result

    # ------------------------------------------------------------------
    # HTML parsing
    # ------------------------------------------------------------------

    def _parse_html(self, raw_html, tab_idx=None, tab_id=None, generation=None):
        """Ultra parser with style and structure support."""
        parser = _RetroNetHTMLParser()
        try:
            parser.feed(raw_html)
            parser.close()
        except Exception:
            pass

        title = parser.get_title()
        if title:
            with self._lock:
                # The fetch thread may have switched the active tab while
                # the request was in flight; write the title to the tab
                # that initiated the fetch, not whichever tab is active now.
                if tab_id is not None:
                    target_idx = self._tab_request_is_current_locked(tab_id, generation)
                else:
                    target_idx = tab_idx if tab_idx is not None else self.active_tab_idx
                if target_idx is not None and 0 <= target_idx < len(self.tabs):
                    self.tabs[target_idx].title = title
                    if target_idx == self.active_tab_idx:
                        self._refresh_window_title()

        text = parser.get_text()

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
                m_link = _LINK_RE.search(working)
                m_btn = _BTN_RE.search(working)

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
    # View source
    # ------------------------------------------------------------------

    def _view_source_path(self) -> str | None:
        """Write the active tab's raw HTML to a deterministic temp file.

        The path is derived from a hash of the tab URL so two RetroNet
        windows viewing the same page share the file (no accumulation).
        Returns the file path or ``None`` when there's nothing to show.
        """
        with self._lock:
            cur = self._cur()
            if cur is None or not cur.raw_html:
                return None
            url = cur.url or "blank"
            raw = cur.raw_html
        digest = hashlib.sha256(url.encode("utf-8", errors="replace")).hexdigest()[:16]
        tmp_dir = tempfile.gettempdir()
        path = os.path.join(tmp_dir, f"retrotui_retronet_viewsource_{digest}.html")
        try:
            from ..utils import atomic_write_text
            atomic_write_text(path, raw, encoding="utf-8")
        except OSError:
            return None
        return path

    # ------------------------------------------------------------------
    # In-page search
    # ------------------------------------------------------------------

    def _clear_search(self):
        tab = self._cur()
        if tab is None:
            return
        with self._lock:
            tab.search_query = ""
            tab.search_matches = []
            tab.search_idx = -1

    def _find_matches(self, query):
        """Find all line indices containing query (case-insensitive)."""
        if not query:
            return []
        tab = self._cur()
        if tab is None:
            return []
        q = query.lower()
        return [i for i, rl in enumerate(tab.content) if q in rl.text.lower()]

    def _search_next(self):
        """Jump to next search match."""
        tab = self._cur()
        if tab is None or not tab.search_matches:
            return
        tab.search_idx = (tab.search_idx + 1) % len(tab.search_matches)
        tab.scroll_y = max(0, tab.search_matches[tab.search_idx] - 2)

    def _search_prev(self):
        """Jump to previous search match."""
        tab = self._cur()
        if tab is None or not tab.search_matches:
            return
        tab.search_idx = (tab.search_idx - 1) % len(tab.search_matches)
        tab.scroll_y = max(0, tab.search_matches[tab.search_idx] - 2)

    def execute_search(self, query):
        """Called when search input dialog completes."""
        tab = self._cur()
        if tab is None:
            return ActionResult(ActionType.REFRESH)
        with self._lock:
            tab.search_query = query
            tab.search_matches = self._find_matches(query)
            tab.search_idx = -1
        if tab.search_matches:
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

        # Snapshot active tab state under the lock so draw is thread-safe.
        with self._lock:
            cur = self._cur()
            if cur is None:
                return
            current_url = cur.url
            has_back = bool(cur.back_stack)
            has_fwd = bool(cur.forward_stack)
            is_loading = cur.is_loading
            loading_frame = cur.loading_frame
            scroll_y = cur.scroll_y
            content_snapshot = list(cur.content)
            search_query = cur.search_query
            search_matches = list(cur.search_matches)
            search_idx = cur.search_idx
            tabs_snapshot = list(enumerate(self.tabs))
            active_idx = self.active_tab_idx

        # Sidebar (History)
        if self.show_sidebar:
            sidebar_w = self._sidebar_width(bw)
            content_x += sidebar_w
            content_w -= sidebar_w
            for i in range(bh):
                safe_addstr(stdscr, by + i, bx + sidebar_w - 1, "│", self.attr_inactive)
            safe_addstr(stdscr, by, bx + 1, "HISTORY", self.attr_title)
            with self._lock:
                hist = list(cur.back_stack[-max(1, bh - 2):]) if cur else []
            for i, h_url in enumerate(hist):
                display = urllib.parse.unquote(h_url)[:sidebar_w - 3]
                safe_addstr(stdscr, by + 1 + i, bx + 1, display, self.attr_dim)

        # Tab bar (above the nav bar). Only rendered when 2+ tabs are open —
        # single-tab windows keep the pre-tabs layout so click/keyboard
        # coordinates stay identical for the most common case.
        tab_bar_y = by
        if len(tabs_snapshot) > 1 and content_w > 4:
            tab_x = content_x + 1
            for idx, tab in tabs_snapshot:
                if tab_x >= content_x + content_w - 4:
                    break
                label = self._tab_chip_label(tab)
                marker = "▶" if idx == active_idx else " "
                chip = f"{marker}{label}×"
                chip_w = self._tab_chip_width(
                    label, content_x=content_x, tab_x=tab_x, content_w=content_w,
                )
                if chip_w <= 1:
                    break
                attr = (self.attr_bold | curses.A_REVERSE) if idx == active_idx else self.attr_inactive
                safe_addstr(stdscr, tab_bar_y, tab_x, chip[:chip_w - 1].ljust(chip_w - 1), attr)
                tab_x += chip_w - 1
            # New-tab affordance
            if tab_x < content_x + content_w - 2 and len(tabs_snapshot) < 12:
                safe_addstr(stdscr, tab_bar_y, tab_x, " [+]", self.attr_dim)
                tab_x += 4
            # Move the nav bar down by one row to make room for the tab bar.
            by += 1
            bh = max(1, bh - 1)

        # Navigation bar: ◀ ▶ 🔒 [url...]
        nav_y = by
        lock_icon = "🔒" if current_url.startswith('https') else "🔓"
        back_ch = "◀" if has_back else "▷"
        fwd_ch = "▶" if has_fwd else "▷"
        nav_prefix = f" {back_ch} {fwd_ch} {lock_icon} "
        safe_addstr(stdscr, nav_y, content_x + 1, nav_prefix, body_attr | self.attr_bold)

        addr_start = content_x + 1 + len(nav_prefix)
        addr_width = max(1, content_w - len(nav_prefix) - 4)
        display_url = urllib.parse.unquote(current_url)
        safe_addstr(stdscr, nav_y, addr_start, display_url.ljust(addr_width)[:addr_width], self.attr_inactive)

        # Loading animation
        if is_loading:
            spinner = self.loading_chars[loading_frame % len(self.loading_chars)]
            with self._lock:
                if cur is not None:
                    cur.loading_frame = loading_frame + 1
            safe_addstr(stdscr, nav_y, bx + bw - 4, f" {spinner} ", self.attr_title | self.attr_bold)

        # Content area
        content_y_start = by + 2
        content_h = max(1, bh - 3)
        visible_lines = content_snapshot[scroll_y : scroll_y + content_h]

        search_set = set(search_matches) if search_query else set()
        current_match = search_matches[search_idx] if 0 <= search_idx < len(search_matches) else -1
        for i, rline in enumerate(visible_lines):
            line_attr = rline.attr if rline.attr else body_attr
            text = rline.text[:content_w - 2]
            abs_idx = scroll_y + i
            if abs_idx in search_set:
                if abs_idx == current_match:
                    line_attr = curses.A_REVERSE | curses.A_BOLD
                else:
                    line_attr = curses.A_REVERSE
            safe_addstr(stdscr, content_y_start + i, content_x + 1, text, line_attr)

        # Scrollbar
        total = len(content_snapshot)
        if total > content_h and content_h > 0:
            scroll_h = max(1, int(content_h * content_h / total))
            scroll_pos = int(scroll_y * content_h / total)
            for i in range(content_h):
                char = "┃" if scroll_pos <= i < scroll_pos + scroll_h else "│"
                safe_addstr(stdscr, content_y_start + i, bx + bw - 1, char, self.attr_inactive)

        # Footer
        help_y = by + bh - 1
        if search_query:
            idx_display = search_idx + 1 if search_idx >= 0 else 0
            match_info = f" /{search_query}  [{idx_display}/{len(search_matches)}]  [n]Next [N]Prev [Esc]Clear "
            safe_addstr(stdscr, help_y, bx + 1, match_info[:bw - 2], self.attr_title)
        else:
            help_txt = " [◀/▶]Nav [G]Go [H]Hist [/]Find [Ctrl+T]Tab [Ctrl+B]Bkm [Ctrl+U]Src [PgUp/Dn]Scroll "
            safe_addstr(stdscr, help_y, bx + 1, help_txt[:bw - 2], self.attr_title)

    # ------------------------------------------------------------------
    # Mouse
    # ------------------------------------------------------------------

    def handle_click(self, mx, my):
        bx, by, bw, bh = self.body_rect()
        sidebar_w = self._sidebar_width(bw) if self.show_sidebar else 0
        content_x = bx + sidebar_w
        content_w = bw - sidebar_w

        # Tab bar click: switch or close tabs. Only when 2+ tabs are open
        # (the bar isn't drawn for a single tab — see ``draw``).
        if my == by and len(self.tabs) > 1 and content_x <= mx:
            return self._handle_tab_bar_click(
                mx - content_x - 1,
                bw,
                content_x=content_x,
                content_w=content_w,
            ) or ActionResult(ActionType.REFRESH)

        # Sidebar click — navigate to history entry
        if self.show_sidebar and bx <= mx < bx + sidebar_w - 1:
            idx = my - (by + 1)
            with self._lock:
                cur = self._cur()
                hist = list(cur.back_stack[-max(1, bh - 2):]) if cur else []
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
            with self._lock:
                cur = self._cur()
                current_url = cur.url if cur else ""
            return ActionResult(ActionType.REQUEST_URL, current_url)

        # Content area clicks
        content_y_start = by + 2
        content_h = max(1, bh - 3)
        if content_y_start <= my < content_y_start + content_h:
            with self._lock:
                cur = self._cur()
                if cur is None:
                    return None
                line_idx = cur.scroll_y + (my - content_y_start)
                rline = cur.content[line_idx] if line_idx < len(cur.content) else None
                current_url = cur.url
            if rline:
                relative_mx = mx - content_x
                for span in rline.spans:
                    if span.start_x <= relative_mx < span.end_x:
                        if span.type == 'link':
                            target_url = span.payload
                            if not target_url.startswith('http'):
                                target_url = urllib.parse.urljoin(current_url, target_url)
                            self._load_url(target_url)
                            return ActionResult(ActionType.REFRESH)
                        elif span.type == 'input':
                            if "google" in current_url or "duckduckgo" in current_url:
                                return ActionResult(ActionType.REQUEST_URL, "duckduckgo.com/html/?q=")
                            return ActionResult(ActionType.REQUEST_URL, span.payload)

        return super().handle_click(mx, my)

    def _tab_chip_label(self, tab):
        """Return the rendered label for *tab* (matches ``draw``)."""
        label_source = tab.title or tab.url or "New Tab"
        label = label_source.replace('\n', ' ').replace('\t', ' ')
        if len(label) > 14:
            label = label[:13] + "…"
        return label

    def _tab_chip_width(self, label, *, content_x, tab_x, content_w):
        """Width of a tab chip, matching the cap applied by ``draw``."""
        full_w = len(label) + 2  # marker + label + "×" + space
        return min(full_w, content_x + content_w - tab_x)

    def _handle_tab_bar_click(self, rel_x: int, body_w: int, *, content_x: int, content_w: int):
        """Translate a click on the tab bar into a switch/close action."""
        if rel_x < 0:
            return None
        with self._lock:
            tabs_snapshot = list(enumerate(self.tabs))
            active_idx = self.active_tab_idx
        cursor = 0
        tab_x = content_x + 1
        for idx, tab in tabs_snapshot:
            label = self._tab_chip_label(tab)
            chip_w = self._tab_chip_width(
                label, content_x=content_x, tab_x=tab_x, content_w=content_w,
            )
            if chip_w <= 1:
                break
            if rel_x < cursor + chip_w:
                # Last char of the chip is the close marker.
                if rel_x == cursor + chip_w - 1 and len(tabs_snapshot) > 1:
                    if self._close_tab(idx):
                        return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)
                else:
                    self._switch_tab(idx)
                return None
            cursor += chip_w
            tab_x += chip_w - 1
        # Click on the trailing "+" affordance: new tab.
        if 0 <= rel_x - cursor <= 2 and len(tabs_snapshot) < 12:
            self._new_tab(_DEFAULT_TAB_URL, activate=True)
        return None

    # ------------------------------------------------------------------
    # Keyboard
    # ------------------------------------------------------------------

    def handle_key(self, key):
        code = normalize_key_code(key)
        _, _, _, bh = self.body_rect()
        content_h = max(1, bh - 3)

        with self._lock:
            cur = self._cur()
            search_query = cur.search_query if cur else ""

        # Search mode: n/N/Esc override normal keys
        if search_query:
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
                if cur is None:
                    return ActionResult(ActionType.REFRESH)
                max_scroll = max(0, len(cur.content) - content_h)
                if cur.scroll_y < max_scroll:
                    cur.scroll_y += 1
        elif code == curses.KEY_UP:
            with self._lock:
                if cur is not None and cur.scroll_y > 0:
                    cur.scroll_y -= 1
        elif code == curses.KEY_NPAGE:  # Page Down
            with self._lock:
                if cur is None:
                    return ActionResult(ActionType.REFRESH)
                max_scroll = max(0, len(cur.content) - content_h)
                cur.scroll_y = min(max_scroll, cur.scroll_y + content_h)
        elif code == curses.KEY_PPAGE:  # Page Up
            with self._lock:
                if cur is not None:
                    cur.scroll_y = max(0, cur.scroll_y - content_h)
        elif code == curses.KEY_HOME:
            with self._lock:
                if cur is not None:
                    cur.scroll_y = 0
        elif code == curses.KEY_END:
            with self._lock:
                if cur is None:
                    return ActionResult(ActionType.REFRESH)
                max_scroll = max(0, len(cur.content) - content_h)
                cur.scroll_y = max_scroll
        elif code == curses.KEY_LEFT:
            return self._go_back()
        elif code == curses.KEY_RIGHT:
            return self._go_forward()
        elif code in (ord('h'), ord('H')):
            self.show_sidebar = not self.show_sidebar
        elif code in (ord('g'), ord('G')):
            with self._lock:
                current_url = cur.url if cur else ""
            return ActionResult(ActionType.REQUEST_URL, current_url)
        elif code == ord('/'):
            return ActionResult(ActionType.REQUEST_URL, "search:")
        elif code == 2:  # Ctrl+B
            return ActionResult(ActionType.REQUEST_BOOKMARKS)
        elif code == 4:  # Ctrl+D
            return ActionResult(ActionType.REQUEST_ADD_BOOKMARK)
        elif code == 21:  # Ctrl+U — view source of active tab
            path = self._view_source_path()
            if path:
                return ActionResult(ActionType.OPEN_FILE, path)
            return ActionResult(ActionType.REFRESH)
        elif code == 20:  # Ctrl+T — new tab
            self._new_tab(_DEFAULT_TAB_URL, activate=True)
            return ActionResult(ActionType.REFRESH)
        elif code == 23:  # Ctrl+W — close current tab (or window if last)
            if self._close_tab(self.active_tab_idx):
                return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)
            return ActionResult(ActionType.REFRESH)
        elif code == 9:  # Ctrl+I — next tab (Tab already used for cycling by some terminals)
            self._cycle_tab(1)
            return ActionResult(ActionType.REFRESH)
        elif code == curses.KEY_BTAB:  # Shift+Tab — previous tab
            self._cycle_tab(-1)
            return ActionResult(ActionType.REFRESH)
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


class BookmarksWindow(Window):
    """Standalone bookmarks list for RetroNet.

    Persists to ``~/.config/retrotui/bookmarks.toml`` via
    ``retrotui.core.bookmarks``. Activating a bookmark navigates the source
    RetroNet window and closes this list.
    """

    def __init__(self, x, y, w, h, source_win=None):
        super().__init__('RetroNet Bookmarks', x, y, w, h)
        self.source_win = source_win
        self.bookmarks: list = []
        self.selected_idx = 0
        self.status_msg = ""
        self.attr_title = theme_attr('window_title')
        self.attr_dim = curses.A_DIM
        self.attr_bold = curses.A_BOLD
        self.attr_inactive = theme_attr('window_inactive')
        self.attr_body = theme_attr('window_body')
        self.attr_error = theme_attr('error')
        self._reload()

    def _reload(self):
        from ..core.bookmarks import load_bookmarks
        self.bookmarks = load_bookmarks()
        if self.selected_idx >= len(self.bookmarks):
            self.selected_idx = max(0, len(self.bookmarks) - 1)
        self.scroll_offset = 0

    def _delete_selected(self):
        if not self.bookmarks:
            return
        from ..core.bookmarks import remove_bookmark
        bm = self.bookmarks[self.selected_idx]
        remove_bookmark(bm.title)
        self.status_msg = f"Deleted '{bm.title}'"
        self._reload()

    def _activate_selected(self):
        if not self.bookmarks:
            return ActionResult(ActionType.REFRESH)
        bm = self.bookmarks[self.selected_idx]
        if self.source_win is not None:
            self.source_win._load_url(bm.url)
            return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)
        self.status_msg = f"No source window for '{bm.title}'"
        return ActionResult(ActionType.REFRESH)

    def handle_key(self, key):
        code = normalize_key_code(key)
        if code == 27:  # Esc
            return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)
        if code in (curses.KEY_UP, ord('k')):
            if self.selected_idx > 0:
                self.selected_idx -= 1
                self._adjust_scroll()
        elif code in (curses.KEY_DOWN, ord('j')):
            if self.selected_idx < len(self.bookmarks) - 1:
                self.selected_idx += 1
                self._adjust_scroll()
        elif code in (curses.KEY_HOME,):
            self.selected_idx = 0
            self._adjust_scroll()
        elif code in (curses.KEY_END,):
            self.selected_idx = max(0, len(self.bookmarks) - 1)
            self._adjust_scroll()
        elif code in (curses.KEY_ENTER, 10, 13):
            return self._activate_selected()
        elif code in (ord('d'), ord('D')):
            self._delete_selected()
        elif code in (ord('r'), ord('R')):
            self._reload()
            self.status_msg = "Reloaded"
        return ActionResult(ActionType.REFRESH)

    def handle_click(self, mx, my):
        if not self.contains(mx, my):
            return None
        bx, by, bw, bh = self.body_rect()
        if by <= my < by + bh:
            row = my - by + self.scroll_offset
            if 0 <= row < len(self.bookmarks):
                self.selected_idx = row
                return self._activate_selected()
        return None

    def _adjust_scroll(self):
        _, _, _, bh = self.body_rect()
        if bh <= 0:
            return
        if self.selected_idx < self.scroll_offset:
            self.scroll_offset = self.selected_idx
        elif self.selected_idx >= self.scroll_offset + bh:
            self.scroll_offset = self.selected_idx - bh + 1

    def draw(self, stdscr):
        if not self.visible:
            return
        body_attr = self.draw_frame(stdscr)
        bx, by, bw, bh = self.body_rect()
        if bh <= 0:
            return

        # Empty state
        if not self.bookmarks:
            msg = " No bookmarks yet. Press Ctrl+D in RetroNet to add one. "
            safe_addstr(stdscr, by + 1, bx + 1, msg[:bw - 2], self.attr_dim)
            hint = " [Esc]Close"
            safe_addstr(stdscr, by + bh - 1, bx + 1, hint[:bw - 2], self.attr_title)
            return

        # List
        for i in range(bh - 1):
            idx = self.scroll_offset + i
            if idx >= len(self.bookmarks):
                break
            bm = self.bookmarks[idx]
            is_sel = (idx == self.selected_idx)
            attr = (self.attr_bold | curses.A_REVERSE) if is_sel else body_attr
            line = f"  {bm.title[:18].ljust(18)}  {bm.url[:bw - 26]}"
            safe_addstr(stdscr, by + i, bx + 1, line.ljust(bw - 2)[:bw - 2], attr)

        # Footer
        footer = f" [Enter]Open  [D]Delete  [R]Reload  [Esc]Close"
        safe_addstr(stdscr, by + bh - 1, bx + 1, footer[:bw - 2], self.attr_title)
        if self.status_msg:
            msg = self.status_msg[:bw - 2]
            safe_addstr(stdscr, by + bh - 2, bx + 1, msg, self.attr_dim)
