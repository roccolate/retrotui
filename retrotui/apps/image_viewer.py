"""Image viewer window using terminal image backends."""

import curses
import os
import re
import shutil
import subprocess

from ..core.actions import ActionResult, ActionType, AppAction
from ..ui.menu import WindowMenu
from ..ui.window import Window
from ..utils import normalize_key_code, safe_addstr, theme_attr, play_ascii_video, VIDEO_EXTENSIONS


_ANSI_CSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_ANSI_OSC_RE = re.compile(r"\x1b\][^\x07]*(?:\x07|\x1b\\)")


def _strip_ansi(text):
    """Remove common ANSI escape sequences."""
    return _ANSI_CSI_RE.sub("", _ANSI_OSC_RE.sub("", text))


class ImageViewerWindow(Window):
    """Viewer for image and video files (ASCII generation)."""

    IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff", ".tif"}
    ZOOM_LEVELS = (50, 75, 100, 125, 150, 200)

    def __init__(self, x, y, w, h, filepath=None):
        super().__init__("Media Viewer", x, y, max(56, w), max(14, h), content=[])
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
                "Media": [
                     ("Play Video     P", "iv_play"),
                ]
            }
        )
        self.filepath = None
        self.is_video = False
        self.backend = None
        self.zoom_index = 2  # 100%
        self.status_message = ""
        self._render_cache = {"key": None, "lines": []}

        if filepath:
            self.open_path(filepath)

    def _update_title(self):
        """Update title to include current media name."""
        if not self.filepath:
            self.title = "Media Viewer"
            return
        type_lbl = "Video" if self.is_video else "Image"
        self.title = f"{type_lbl} Viewer - {os.path.basename(self.filepath)}"

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
        """Open an image or video path."""
        path = os.path.realpath(os.path.expanduser(str(filepath)))
        if not os.path.isfile(path):
            return ActionResult(ActionType.ERROR, f"Not a file: {path}")
        
        ext = os.path.splitext(path)[1].lower()
        if ext in self.IMAGE_EXTENSIONS:
            self.is_video = False
        elif ext in VIDEO_EXTENSIONS:
            self.is_video = True
        else:
            return ActionResult(ActionType.ERROR, f"Not a supported media file: {path}")
            
        self.filepath = path
        self._update_title()
        self._invalidate_cache()
        self.status_message = f"Opened {path}"
        return None

    def _render_image(self, cols, rows):
        """Render current image or video placeholder."""
        if self.is_video:
             return [
                 "",
                 "    [ VIDEO FILE DETECTED ]",
                 "",
                 f"       File: {os.path.basename(self.filepath)}",
                 "    Backend: mpv / mplayer",
                 "",
                 "       Press 'P' or ENTER to Play",
                 ""
             ]

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
            return ["No media opened. Press O to open."]
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
                self.is_video
            )
        except OSError:
            cache_key = (self.filepath, None, None, cols, rows, self.zoom_index, self._detect_backend(), self.is_video)

        if self._render_cache["key"] == cache_key:
            return list(self._render_cache["lines"])

        lines = self._render_image(cols, rows)
        self._render_cache = {"key": cache_key, "lines": list(lines)}
        return lines

    def _set_zoom(self, delta):
        """Adjust zoom index in range."""
        if self.is_video: return
        old = self.zoom_index
        self.zoom_index = max(0, min(len(self.ZOOM_LEVELS) - 1, self.zoom_index + delta))
        if self.zoom_index != old:
            self._invalidate_cache()
    
    def _play_video(self):
        if not self.is_video or not self.filepath:
             return
        # We need a stdscr to play. Passing None might fail if play_ascii_video expects it for refresh.
        # But Window has no access to global stdscr directly? 
        # Actually play_ascii_video(stdscr, ...) 
        # AppAction.ASCII_VIDEO usually runs in ActionRunner which lacks stdscr too.
        # Wait, play_ascii_video calls curses.def_prog_mode() / endwin().
        # It takes stdscr as first arg to refresh it at the end.
        # We can pass curses.stdscr if available? Or import curses.
        # Window doesn't store stdscr. render() gets it.
        # We'll use curses.initscr() - NO, that re-inits.
        # We can pass None to play_ascii_video and handle refresh differently?
        # utils.py: if stdscr: stdscr.refresh()
        # So passing None is safe if we don't crash.
        
        # We will request the app to play it via action? 
        # No, simpler to call it here. Window methods run in EventLoop which has stdscr but doesn't pass it to handle_key.
        # Let's try passing None. The event loop redraws everything next frame anyway.
        success, err = play_ascii_video(None, self.filepath)
        if not success:
             self.status_message = f"Error: {err}"
        else:
             self.status_message = "Playback finished."

    def execute_action(self, action):
        if action == "iv_open":
            return ActionResult(ActionType.REQUEST_OPEN_PATH)
        if action == "iv_reload":
            self._invalidate_cache()
            if self.filepath:
                self.status_message = "Reloaded."
            else:
                self.status_message = "No media opened."
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
        if action == "iv_play":
            self._play_video()
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

        if self.is_video:
             status_keys = "P/Enter Play | O open | Q close"
             tech_info = "Video"
        else:
             status_keys = "+/- zoom | O open | Q close"
             backend = self._detect_backend() or "none"
             zoom = self.ZOOM_LEVELS[self.zoom_index]
             tech_info = f"zoom:{zoom}% backend:{backend}"

        if self.status_message:
            status = self.status_message
            self.status_message = ""
        else:
            status = f"{status_keys} | {tech_info}"
        
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
                    return self.execute_action(action)
        return None

    def handle_key(self, key):
        """Handle keyboard shortcuts."""
        key_code = normalize_key_code(key)

        if self.window_menu and self.window_menu.active:
            action = self.window_menu.handle_key(key_code)
            if action:
                return self.execute_action(action)
            return None

        if key_code in (ord("q"), ord("Q")):
            return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)
        if key_code in (ord("o"), ord("O")):
            return ActionResult(ActionType.REQUEST_OPEN_PATH)
        if key_code in (ord("r"), ord("R")):
            return self.execute_action("iv_reload")
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
        if self.is_video and key_code in (ord("p"), ord("P"), 10, 13): # P or Enter
             self._play_video()
             return None
             
        return None
