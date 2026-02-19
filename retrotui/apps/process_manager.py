"""Process Manager window backed by /proc live data."""

import curses
import os
import signal
import time
from dataclasses import dataclass

from ..core.actions import ActionResult, ActionType, AppAction
from ..ui.menu import WindowMenu
from ..ui.window import Window
from ..utils import normalize_key_code, safe_addstr, theme_attr


@dataclass
class ProcessRow:
    """One process table row."""

    pid: int
    cpu_percent: float
    mem_percent: float
    command: str
    total_ticks: int


class ProcessManagerWindow(Window):
    """Live process list with sorting and kill confirmation request."""

    REFRESH_INTERVAL_SECONDS = 1.0
    KEY_F5 = getattr(curses, "KEY_F5", -1)

    def __init__(self, x, y, w, h):
        super().__init__("Process Manager", x, y, max(58, w), max(14, h), content=[])
        self.rows = []
        self.selected_index = 0
        self.sort_key = "cpu"  # cpu | mem | pid
        self.sort_reverse = True
        self._last_refresh = 0.0
        self._error_message = None

        self._cpu_count = max(1, int(os.cpu_count() or 1))
        try:
            page_size = int(os.sysconf("SC_PAGE_SIZE"))
        except (AttributeError, OSError, ValueError):
            page_size = 4096
        self._page_kb = max(1, page_size // 1024)
        self._prev_total_jiffies = None
        self._prev_proc_ticks = {}

        self.summary_uptime = "-"
        self.summary_load = "-"
        self.summary_mem = "-"

        self.window_menu = WindowMenu(
            {
                "Process": [
                    ("Sort CPU       C", "pm_sort_cpu"),
                    ("Sort MEM       M", "pm_sort_mem"),
                    ("Sort PID       P", "pm_sort_pid"),
                    ("Kill Process   K", "pm_kill"),
                    ("Refresh       F5", "pm_refresh"),
                    ("-------------", None),
                    ("Close          Q", "pm_close"),
                ]
            }
        )
        self.refresh_processes(force=True)

    @staticmethod
    def _read_first_line(path):
        with open(path, "r", encoding="utf-8", errors="replace") as stream:
            return stream.readline().strip()

    @staticmethod
    def _read_mem_total_kb():
        try:
            with open("/proc/meminfo", "r", encoding="utf-8", errors="replace") as stream:
                for line in stream:
                    if line.startswith("MemTotal:"):
                        return int(line.split()[1])
        except (OSError, ValueError, IndexError):
            return 1
        return 1

    @staticmethod
    def _read_mem_available_kb():
        mem_free = 0
        try:
            with open("/proc/meminfo", "r", encoding="utf-8", errors="replace") as stream:
                for line in stream:
                    if line.startswith("MemAvailable:"):
                        return int(line.split()[1])
                    if line.startswith("MemFree:"):
                        mem_free = int(line.split()[1])
        except (OSError, ValueError, IndexError):
            return 0
        return mem_free

    @staticmethod
    def _read_total_jiffies():
        try:
            line = ProcessManagerWindow._read_first_line("/proc/stat")
        except OSError:
            return 0
        if not line.startswith("cpu "):
            return 0
        parts = line.split()[1:]
        total = 0
        for item in parts:
            try:
                total += int(item)
            except ValueError:
                continue
        return total

    @staticmethod
    def _read_uptime_seconds():
        try:
            raw = ProcessManagerWindow._read_first_line("/proc/uptime")
            return float(raw.split()[0])
        except (OSError, ValueError, IndexError):
            return 0.0

    @staticmethod
    def _format_uptime(seconds):
        total = max(0, int(seconds))
        days, rem = divmod(total, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, _ = divmod(rem, 60)
        if days:
            return f"{days}d {hours:02d}h {minutes:02d}m"
        return f"{hours:02d}h {minutes:02d}m"

    @staticmethod
    def _read_load_average():
        try:
            raw = ProcessManagerWindow._read_first_line("/proc/loadavg").split()
            return f"{float(raw[0]):.2f} {float(raw[1]):.2f} {float(raw[2]):.2f}"
        except (OSError, ValueError, IndexError):
            return "- - -"

    @staticmethod
    def _read_command(pid):
        cmdline_path = f"/proc/{pid}/cmdline"
        comm_path = f"/proc/{pid}/comm"
        try:
            with open(cmdline_path, "rb") as stream:
                raw = stream.read().replace(b"\x00", b" ").strip()
            if raw:
                return raw.decode("utf-8", errors="replace")
        except OSError:
            pass
        try:
            return ProcessManagerWindow._read_first_line(comm_path)
        except OSError:
            return f"[{pid}]"

    def _read_process_row(self, pid, total_delta, mem_total_kb):
        stat_path = f"/proc/{pid}/stat"
        statm_path = f"/proc/{pid}/statm"

        try:
            stat_line = self._read_first_line(stat_path)
        except OSError:
            return None

        close = stat_line.rfind(")")
        if close < 0:
            return None
        tail = stat_line[close + 2 :].split()
        if len(tail) < 13:
            return None
        try:
            utime = int(tail[11])
            stime = int(tail[12])
            total_ticks = utime + stime
        except (ValueError, IndexError):
            return None

        try:
            statm_line = self._read_first_line(statm_path).split()
            rss_pages = int(statm_line[1])
        except (OSError, ValueError, IndexError):
            rss_pages = 0
        rss_kb = rss_pages * self._page_kb
        mem_percent = (rss_kb / max(1, mem_total_kb)) * 100.0

        prev_ticks = self._prev_proc_ticks.get(pid)
        if prev_ticks is None or total_delta <= 0:
            cpu_percent = 0.0
        else:
            proc_delta = max(0, total_ticks - prev_ticks)
            cpu_percent = (proc_delta / max(1, total_delta)) * 100.0 * self._cpu_count

        command = self._read_command(pid)
        return ProcessRow(
            pid=pid,
            cpu_percent=cpu_percent,
            mem_percent=mem_percent,
            command=command,
            total_ticks=total_ticks,
        )

    def _sort_rows(self):
        if self.sort_key == "pid":
            self.rows.sort(key=lambda row: row.pid, reverse=self.sort_reverse)
            return
        if self.sort_key == "mem":
            self.rows.sort(key=lambda row: row.mem_percent, reverse=self.sort_reverse)
            return
        self.rows.sort(key=lambda row: row.cpu_percent, reverse=self.sort_reverse)

    def _visible_rows(self):
        _, _, _, bh = self.body_rect()
        return max(1, bh - 3)  # Header + summary + status rows.

    def _max_scroll(self):
        return max(0, len(self.rows) - self._visible_rows())

    def _ensure_selection_visible(self):
        if self.selected_index < self.scroll_offset:
            self.scroll_offset = self.selected_index
            return
        view = self._visible_rows()
        if self.selected_index >= self.scroll_offset + view:
            self.scroll_offset = max(0, self.selected_index - view + 1)

    def refresh_processes(self, force=False):
        """Refresh table data from /proc."""
        now = time.monotonic()
        if not force and (now - self._last_refresh) < self.REFRESH_INTERVAL_SECONDS:
            return
        self._last_refresh = now

        mem_total_kb = self._read_mem_total_kb()
        mem_avail_kb = self._read_mem_available_kb()
        total_jiffies = self._read_total_jiffies()
        total_delta = 0
        if self._prev_total_jiffies is not None:
            total_delta = max(0, total_jiffies - self._prev_total_jiffies)

        rows = []
        new_ticks = {}
        self._error_message = None
        try:
            proc_dirs = [name for name in os.listdir("/proc") if name.isdigit()]
        except OSError as exc:
            self._error_message = str(exc)
            proc_dirs = []

        for name in proc_dirs:
            pid = int(name)
            row = self._read_process_row(pid, total_delta, mem_total_kb)
            if row is None:
                continue
            rows.append(row)
            new_ticks[pid] = row.total_ticks

        self.rows = rows
        self._sort_rows()
        self._prev_total_jiffies = total_jiffies
        self._prev_proc_ticks = new_ticks

        if self.rows:
            self.selected_index = max(0, min(self.selected_index, len(self.rows) - 1))
        else:
            self.selected_index = 0
        self.scroll_offset = max(0, min(self.scroll_offset, self._max_scroll()))
        self._ensure_selection_visible()

        used_kb = max(0, mem_total_kb - mem_avail_kb)
        self.summary_uptime = self._format_uptime(self._read_uptime_seconds())
        self.summary_load = self._read_load_average()
        self.summary_mem = f"{used_kb // 1024}MB/{mem_total_kb // 1024}MB"

    def _selected_row(self):
        if not self.rows:
            return None
        if not (0 <= self.selected_index < len(self.rows)):
            return None
        return self.rows[self.selected_index]

    def request_kill_selected(self):
        """Return a kill-confirmation request for currently selected process."""
        row = self._selected_row()
        if row is None:
            return ActionResult(ActionType.ERROR, "No process selected.")
        payload = {"pid": row.pid, "command": row.command, "signal": signal.SIGTERM}
        return ActionResult(ActionType.REQUEST_KILL_CONFIRM, payload)

    def kill_process(self, payload):
        """Send requested signal to one process."""
        data = payload or {}
        pid = int(data.get("pid", 0))
        sig = int(data.get("signal", signal.SIGTERM))
        if pid <= 0:
            return ActionResult(ActionType.ERROR, "Invalid PID.")
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            # Process already exited.
            self.refresh_processes(force=True)
            return None
        except PermissionError:
            return ActionResult(ActionType.ERROR, f"Permission denied for PID {pid}.")
        except OSError as exc:
            return ActionResult(ActionType.ERROR, str(exc))
        self.refresh_processes(force=True)
        return None

    def _set_sort(self, key):
        if self.sort_key == key:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_key = key
            self.sort_reverse = key != "pid"
        self.refresh_processes(force=True)

    def execute_action(self, action):
        if action == "pm_sort_cpu":
            self._set_sort("cpu")
            return None
        if action == "pm_sort_mem":
            self._set_sort("mem")
            return None
        if action == "pm_sort_pid":
            self._set_sort("pid")
            return None
        if action == "pm_refresh":
            self.refresh_processes(force=True)
            return None
        if action == "pm_kill":
            return self.request_kill_selected()
        if action == "pm_close":
            return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)
        return None

    def draw(self, stdscr):
        """Draw process table and summary bar."""
        if not self.visible:
            return

        self.refresh_processes(force=False)
        body_attr = self.draw_frame(stdscr)
        bx, by, bw, bh = self.body_rect()
        if bh <= 0 or bw <= 0:
            return

        for row in range(bh):
            safe_addstr(stdscr, by + row, bx, " " * bw, body_attr)

        arrow = '▼' if self.sort_reverse else '▲'
        pid_h = f"{'PID':>6}"
        cpu_h = f"{'CPU%':>6}"
        mem_h = f"{'MEM%':>6}"
        cmd_h = 'COMMAND'
        if self.sort_key == 'pid':
            pid_h = f"{'PID':>5}{arrow}"
        elif self.sort_key == 'cpu':
            cpu_h = f"{'CPU%':>5}{arrow}"
        elif self.sort_key == 'mem':
            mem_h = f"{'MEM%':>5}{arrow}"
        elif self.sort_key == 'cmd':
            cmd_h = f'COMMAND{arrow}'
        header = f"{pid_h} {cpu_h} {mem_h} {cmd_h}"
        safe_addstr(stdscr, by, bx, header[:bw].ljust(bw), theme_attr("menubar"))

        view_rows = self._visible_rows()
        start = max(0, min(self.scroll_offset, self._max_scroll()))
        self.scroll_offset = start
        for idx in range(view_rows):
            row_index = start + idx
            if row_index >= len(self.rows):
                break
            row = self.rows[row_index]
            line = f"{row.pid:>6} {row.cpu_percent:>6.1f} {row.mem_percent:>6.1f} {row.command}"
            attr = body_attr
            if row_index == self.selected_index:
                attr = theme_attr("file_selected") | curses.A_BOLD
            safe_addstr(stdscr, by + 1 + idx, bx, line[:bw].ljust(bw), attr)

        summary = (
            f"Uptime {self.summary_uptime} | Load {self.summary_load} | "
            f"Mem {self.summary_mem}"
        )
        safe_addstr(stdscr, by + bh - 2, bx, summary[:bw].ljust(bw), theme_attr("status"))

        error_info = f" | {self._error_message}" if self._error_message else ""
        status = (
            f"Sort:{self.sort_key.upper()} C/M/P  K kill  F5 refresh  "
            f"Arrows/PgUp/PgDn nav{error_info}"
        )
        safe_addstr(stdscr, by + bh - 1, bx, status[:bw].ljust(bw), theme_attr("status"))

        if self.window_menu:
            self.window_menu.draw_dropdown(stdscr, self.x, self.y, self.w)

    def handle_click(self, mx, my, bstate=None):
        """Select rows and dispatch window menu clicks."""
        if self.window_menu:
            if self.window_menu.on_menu_bar(mx, my, self.x, self.y, self.w) or self.window_menu.active:
                action = self.window_menu.handle_click(mx, my, self.x, self.y, self.w)
                if action:
                    return self.execute_action(action)
                return None

        bx, by, bw, bh = self.body_rect()

        # Header row click — sort by column
        if my == by and bx <= mx < bx + bw:
            col = mx - bx
            if col < 7:
                self._set_sort('pid')
            elif col < 14:
                self._set_sort('cpu')
            elif col < 21:
                self._set_sort('mem')
            else:
                self._set_sort('cmd')
            return None

        if not (bx <= mx < bx + bw and by + 1 <= my < by + bh - 2):
            return None


            return None

        row_index = self.scroll_offset + (my - (by + 1))
        if 0 <= row_index < len(self.rows):
            self.selected_index = row_index
            self._ensure_selection_visible()
            if bstate and (bstate & getattr(curses, "BUTTON1_DOUBLE_CLICKED", 0)):
                return self.request_kill_selected()
        return None

    def handle_key(self, key):
        """Handle keyboard navigation, sorting and kill action."""
        key_code = normalize_key_code(key)

        if self.window_menu and self.window_menu.active:
            action = self.window_menu.handle_key(key_code)
            if action:
                return self.execute_action(action)
            return None

        if key_code == curses.KEY_UP:
            self.selected_index = max(0, self.selected_index - 1)
            self._ensure_selection_visible()
        elif key_code == curses.KEY_DOWN:
            self.selected_index = min(max(0, len(self.rows) - 1), self.selected_index + 1)
            self._ensure_selection_visible()
        elif key_code == curses.KEY_PPAGE:
            self.selected_index = max(0, self.selected_index - self._visible_rows())
            self._ensure_selection_visible()
        elif key_code == curses.KEY_NPAGE:
            self.selected_index = min(
                max(0, len(self.rows) - 1),
                self.selected_index + self._visible_rows(),
            )
            self._ensure_selection_visible()
        elif key_code == curses.KEY_HOME:
            self.selected_index = 0
            self._ensure_selection_visible()
        elif key_code == curses.KEY_END:
            self.selected_index = max(0, len(self.rows) - 1)
            self._ensure_selection_visible()
        elif key_code in (ord("c"), ord("C")):
            self._set_sort("cpu")
        elif key_code in (ord("m"), ord("M")):
            self._set_sort("mem")
        elif key_code in (ord("p"), ord("P")):
            self._set_sort("pid")
        elif key_code in (ord("k"), ord("K"), curses.KEY_DC):
            return self.request_kill_selected()
        elif key_code in (self.KEY_F5, ord("r"), ord("R")):
            self.refresh_processes(force=True)
        elif key_code in (ord("q"), ord("Q")):
            return ActionResult(ActionType.EXECUTE, AppAction.CLOSE_WINDOW)

        return None
