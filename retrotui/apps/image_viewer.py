"""Image viewer window using terminal image backends."""

import curses
import os
import re
import shutil
import subprocess

from ..core.actions import ActionResult, ActionType, AppAction
from ..ui.menu import WindowMenu
from ..ui.window import Window
from ..utils import normalize_key_code, safe_addstr, theme_attr


_ANSI_CSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_ANSI_OSC_RE = re.compile(r"\x1b\][^\x07]*(?:\x07|\x1b\\)")


def _strip_ansi(text):
    """Remove common ANSI escape sequences."""
    return _ANSI_CSI_RE.sub("", _ANSI_OSC_RE.sub("", text))


class ImageViewerWindow(Window):
    """Viewer for image files rendered as terminal text."""

    IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff", ".tif"}
    ZOOM_LEVELS = (50, 75, 100, 125, 150, 200)

    def __init__(self, x, y, w, h, filepath=None):
        super().__init__("Image Viewer", x, y, max(56, w), max(14, h), content=[])
        self.window_menu = WindowMenu(
            {
                "File": [
                    ("Open...        O", "iv_open"),
                    ("Reload         R", "iv_reload"),
                    ("-------------", None),
                    ("Close          Q", "iv_close"),
                ],
                "View": [
                    ("Zoom In        +", "iv_zoom_in"),
                    ("Zoom Out       -", "iv_zoom_out"),
                    ("Reset Zoom     0", "iv_zoom_reset"),
                ],
            }
        )
        self.filepath = None
        self.backend = None
        self.zoom_index = 2  # 100%
        self.status_message = ""
        self._render_cache = {"key": None, "lines": []}

        if filepath:
            self.open_path(filepath)

    def _update_title(self):
        """Update title to include current image name."""
        if not self.filepath:
            self.title = "Image Viewer"
            return
        self.title = f"Image Viewer - {os.path.basename(self.filepath)}"

    def _invalidate_cache(self):
        self._render_cache = {"key": None, "lines": []}

    def _detect_backend(self):
        """Detect preferred backend command."""
        if self.backend is not None:
            return self.backend
        if shutil.which("chafa"):
            self.backend = "chafa"
        elif shutil.which("timg"):
            self.backend = "timg"
        elif shutil.which("catimg"):
            self.backend = "catimg"
        else:
            self.backend = ""
        return self.backend

    def open_path(self, filepath):
        """Open an image path."""
        path = os.path.realpath(os.path.expanduser(str(filepath)))
        if not os.path.isfile(path):
            return ActionResult(ActionType.ERROR, f"Not a file: {path}")
        ext = os.path.splitext(path)[1].lower()
        if ext not in self.IMAGE_EXTENSIONS:
            return ActionResult(ActionType.ERROR, f"Not an image file: {path}")
        self.filepath = path
        self._update_title()
        self._invalidate_cache()
        self.status_message = f"Opened {path}"
        return None

    def _render_image(self, cols, rows):
        """Render current image through backend command."""
        backend = self._detect_backend()
        if not backend:
            return ["[image backend missing: install chafa/timg/catimg]"]

        zoom = self.ZOOM_LEVELS[self.zoom_index] / 100.0
        target_cols = max(8, int(cols * zoom))
        target_rows = max(4, int(rows * zoom))

        if backend == "chafa":
            cmd = [
                "chafa",
                "--format=symbols",
                "--colors=none",
                "--size",
                f"{target_cols}x{target_rows}",
                self.filepath,
            ]
        elif backend == "timg":
            cmd = ["timg", "-g", f"{target_cols}x{target_rows}", self.filepath]
        else:
            cmd = ["catimg", "-w", str(target_cols), self.filepath]

        try:
            completed = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=3.0,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return [f"[image render failed via {backend}]"]

        if completed.returncode != 0:
            return [f"[image render failed via {backend}]"]

        output = completed.stdout or completed.stderr
        lines = _strip_ansi(output).splitlines()
        if not lines:
            return ["[empty image output]"]
        return lines

    def _cached_render_lines(self, cols, rows):
        """Return rendered lines with cache keyed by file/size/zoom/backend."""
        if not self.filepath:
            return ["No image opened. Press O to open."]
        try:
            st = os.stat(self.filepath)
            cache_key = (
                self.filepath,
                int(st.st_size),
                int(st.st_mtime_ns),
                cols,
                rows,
                self.zoom_index,
                self._detect_backend(),
            )
        except OSError:
            cache_key = (self.filepath, None, None, cols, rows, self.zoom_index, self._detect_backend())

        if self._render_cache["key"] == cache_key:
            return list(self._render_cache["lines"])

        lines = self._render_image(cols, rows)
        self._render_cache = {"key": cache_key, "lines": list(lines)}
        return lines

    def _set_zoom(self, delta):
        """Adjust zoom index in range."""
        old = self.zoom_index
        self.zoom_index = max(0, min(len(self.ZOOM_LEVELS) - 1, self.zoom_index + delta))
        if self.zoom_index != old:
            self._invalidate_cache()

    def _execute_menu_action(self, action):
        if action == "iv_open":
            return ActionResult(ActionType.REQUEST_OPEN_PATH)
        if action == "iv_reload":
            self._invalidate_cache()
            if self.filepath:
                self.status_message = "Reloaded."
            else:
                self.status_message = "No image opened."
            return None
        if action == "iv_zoom_in":
            self._set_zoom(1)
            return None
        if action == "iv_zoom_out":
            self._set_zoom(-1)
            return None
        if action == "iv_zoom_reset":
            self.zoom_index = 2
            self._invalidate_cache()
            return None
        if action == "iv_close":
            return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)
        return None

    def draw(self, stdscr):
        """Draw rendered image lines and status bar."""
        if not self.visible:
            return
        body_attr = self.draw_frame(stdscr)
        bx, by, bw, bh = self.body_rect()
        if bw <= 0 or bh <= 0:
            return

        for row in range(bh):
            safe_addstr(stdscr, by + row, bx, " " * bw, body_attr)

        image_rows = max(0, bh - 1)
        if image_rows > 0:
            lines = self._cached_render_lines(bw, image_rows)
            for row, line in enumerate(lines[:image_rows]):
                safe_addstr(stdscr, by + row, bx, line[:bw].ljust(bw), body_attr)

        backend = self._detect_backend() or "none"
        zoom = self.ZOOM_LEVELS[self.zoom_index]
        if self.status_message:
            status = self.status_message
            self.status_message = ""
        else:
            status = f"+/- zoom:{zoom}% | backend:{backend} | O open | R reload | Q close"
        safe_addstr(stdscr, by + bh - 1, bx, status[:bw].ljust(bw), theme_attr("status"))

        if self.window_menu:
            self.window_menu.draw_dropdown(stdscr, self.x, self.y, self.w)

    def handle_click(self, mx, my, bstate=None):
        """Handle menu click actions."""
        _ = bstate
        if self.window_menu:
            if self.window_menu.on_menu_bar(mx, my, self.x, self.y, self.w) or self.window_menu.active:
                action = self.window_menu.handle_click(mx, my, self.x, self.y, self.w)
                if action:
                    return self._execute_menu_action(action)
        return None

    def handle_key(self, key):
        """Handle keyboard shortcuts."""
        key_code = normalize_key_code(key)

        if self.window_menu and self.window_menu.active:
            action = self.window_menu.handle_key(key_code)
            if action:
                return self._execute_menu_action(action)
            return None

        if key_code in (ord("q"), ord("Q")):
            return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)
        if key_code in (ord("o"), ord("O")):
            return ActionResult(ActionType.REQUEST_OPEN_PATH)
        if key_code in (ord("r"), ord("R")):
            return self._execute_menu_action("iv_reload")
        if key_code in (ord("+"), ord("=")):
            self._set_zoom(1)
            return None
        if key_code in (ord("-"), ord("_")):
            self._set_zoom(-1)
            return None
        if key_code == ord("0"):
            self.zoom_index = 2
            self._invalidate_cache()
            return None
        if key_code == getattr(curses, "KEY_PPAGE", -1):
            self._set_zoom(1)
            return None
        if key_code == getattr(curses, "KEY_NPAGE", -1):
            self._set_zoom(-1)
            return None
        return None
