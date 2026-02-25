"""
Main RetroTUI Application Class.
"""
import os
import curses
import logging
import signal
import threading
import time

from ..constants import (
    ICONS, ICONS_ASCII, BINARY_DETECT_CHUNK_SIZE,
    TERMINAL_INPUT_TIMEOUT_MS,
    TERMINAL_LIVE_INPUT_TIMEOUT_MS,
    TERMINAL_BACKGROUND_INPUT_TIMEOUT_MS,
    WELCOME_WIN_WIDTH, WELCOME_WIN_HEIGHT,
)
from ..utils import (
    check_unicode_support, init_colors,
    is_video_file, play_ascii_video
)
from ..theme import get_theme
from ..ui.menu import Menu
from ..ui.dialog import Dialog, InputDialog, ProgressDialog
from ..ui.window import Window
from ..apps.notepad import NotepadWindow
from ..apps.logviewer import LogViewerWindow
from ..apps.image_viewer import ImageViewerWindow
from ..apps.hexviewer import HexViewerWindow
from ..apps.markdown_viewer import MarkdownViewerWindow
from .config import AppConfig, load_config, save_config
from .actions import ActionResult, ActionType, AppAction
from .action_runner import execute_app_action
from .drag_drop import DragDropManager
from .file_operations import FileOperationManager
from .icon_manager import IconPositionManager
from .content import build_welcome_content
from .mouse_router import (
    _invoke_mouse_handler,
    handle_drag_resize_mouse,
    handle_global_menu_mouse,
    handle_window_mouse,
    handle_desktop_mouse,
    handle_mouse_event,
)
from .key_router import (
    normalize_app_key,
    handle_menu_hotkeys,
    handle_global_menu_key,
    cycle_focus,
    handle_active_window_key,
    handle_key_event,
)
from .rendering import (
    draw_desktop,
    draw_icons,
    draw_taskbar,
    draw_statusbar,
)
from .event_loop import run_app_loop
from .dialog_dispatch import DialogDispatcher
from .bootstrap import (
    configure_terminal,
    disable_flow_control,
    detect_mouse_backend,
    enable_mouse_support,
    disable_mouse_support,
)

from .window_manager import WindowManager

LOGGER = logging.getLogger(__name__)

APP_VERSION = '0.9.2'
ICON_STYLE_DEFAULT = "default"
ICON_STYLE_MINI = "mini"
ICON_STYLE_BRAILLE = "braille"
ICON_STYLE_CODEX = "codex"
ICON_STYLE_RETRO_01 = "retro_01"  # Legacy alias kept for backwards compatibility.
_CURSES_ERROR = getattr(curses, "error", Exception)
_CONFIG_PERSIST_ERRORS = (OSError, UnicodeError, ValueError, TypeError)
_INPUT_ROUTE_ERRORS = (
    AttributeError,
    LookupError,
    OSError,
    TypeError,
    ValueError,
    _CURSES_ERROR,
)
_PLUGIN_DISCOVERY_IMPORT_ERRORS = (
    ImportError,
    ModuleNotFoundError,
    AttributeError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)
_RUNTIME_ISOLATION_ERRORS = (
    ArithmeticError,
    AssertionError,
    AttributeError,
    ImportError,
    LookupError,
    NameError,
    OSError,
    RuntimeError,
    SyntaxError,
    TypeError,
    ValueError,
    _CURSES_ERROR,
)

class RetroTUI:
    """Main application class."""
    MIN_TERM_WIDTH = 80
    MIN_TERM_HEIGHT = 24
    LONG_FILE_OPERATION_BYTES = 8 * 1024 * 1024
    BACKGROUND_OPERATION_JOIN_TIMEOUT = 5.0

    @property
    def file_ops(self):
        """Return the FileOperationManager, creating it lazily if needed (e.g. in tests using __new__)."""
        if not hasattr(self, '_file_ops'):
            self._file_ops = FileOperationManager(self)
        return self._file_ops

    @file_ops.setter
    def file_ops(self, value):
        self._file_ops = value

    # ------------------------------------------------------------------
    # File operations facade
    # ------------------------------------------------------------------

    def show_save_as_dialog(self, win):
        return self.file_ops.show_save_as_dialog(win)

    def show_open_dialog(self, win):
        return self.file_ops.show_open_dialog(win)

    def show_rename_dialog(self, win):
        return self.file_ops.show_rename_dialog(win)

    def show_delete_confirm_dialog(self, win):
        return self.file_ops.show_delete_confirm_dialog(win)

    def show_copy_dialog(self, win):
        return self.file_ops.show_copy_dialog(win)

    def show_move_dialog(self, win):
        return self.file_ops.show_move_dialog(win)

    def show_new_dir_dialog(self, win):
        return self.file_ops.show_new_dir_dialog(win)

    def show_new_file_dialog(self, win):
        return self.file_ops.show_new_file_dialog(win)

    def show_kill_confirm_dialog(self, win, payload):
        return self.file_ops.show_kill_confirm_dialog(win, payload)

    def _window_selected_entry(self, win):
        return self.file_ops._window_selected_entry(win)

    def _resolve_between_panes_destination(self, win, payload):
        return self.file_ops._resolve_between_panes_destination(win, payload)

    def _is_long_file_operation(self, entry):
        return self.file_ops._is_long_file_operation(entry)

    def _start_background_operation(self, *, title, message, worker, source_win):
        return self.file_ops._start_background_operation(
            title=title,
            message=message,
            worker=worker,
            source_win=source_win,
        )

    def has_background_operation(self):
        return self.file_ops.has_background_operation()

    def poll_background_operation(self):
        return self.file_ops.poll_background_operation()

    def _run_file_operation_with_progress(self, win, *, operation, destination=None):
        return self.file_ops._run_file_operation_with_progress(
            win,
            operation=operation,
            destination=destination,
        )

    def _get_icon_mgr(self):
        """Return the IconPositionManager, creating it lazily if needed (e.g. in tests using __new__)."""
        if not hasattr(self, '_icon_mgr'):
            self._icon_mgr = IconPositionManager(self)
        return self._icon_mgr

    @property
    def icon_positions(self):
        return self._get_icon_mgr().positions

    @icon_positions.setter
    def icon_positions(self, value):
        self._get_icon_mgr().positions = value

    def _get_window_mgr(self):
        """Return the WindowManager, creating it lazily if needed (e.g. in tests using __new__)."""
        if not hasattr(self, 'window_mgr'):
            self.window_mgr = WindowManager(self)
        return self.window_mgr

    @property
    def windows(self):
        return self._get_window_mgr().windows

    @windows.setter
    def windows(self, value):
        self._get_window_mgr().windows = value

    def _get_drag_drop(self):
        """Return the DragDropManager, creating it lazily if needed (e.g. in tests using __new__)."""
        if not hasattr(self, 'drag_drop'):
            self.drag_drop = DragDropManager(self)
        return self.drag_drop

    def _get_dialog_dispatcher(self):
        """Return the dialog dispatcher, creating it lazily if needed."""
        if not hasattr(self, '_dialog_dispatcher'):
            self._dialog_dispatcher = DialogDispatcher(self)
        return self._dialog_dispatcher

    @property
    def drag_payload(self):
        return self._get_drag_drop().payload

    @drag_payload.setter
    def drag_payload(self, value):
        self._get_drag_drop().payload = value

    @property
    def drag_source_window(self):
        return self._get_drag_drop().source_window

    @drag_source_window.setter
    def drag_source_window(self, value):
        self._get_drag_drop().source_window = value

    @property
    def drag_target_window(self):
        return self._get_drag_drop().target_window

    @drag_target_window.setter
    def drag_target_window(self, value):
        self._get_drag_drop().target_window = value

    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.running = True
        self._pending_sigint = False
        self._pending_signal_keys = []
        self._prev_sigint_handler = None
        self._prev_signal_handlers = {}
        self._sigint_handler_installed = False
        self._shutdown_signal = None
        self.window_mgr = WindowManager(self)
        self.use_unicode = check_unicode_support()
        self.config = load_config()
        self.theme_name = self.config.theme
        self._plugins = {}
        self.refresh_icons()
        self._rebuild_global_menu()
        self.context_menu = None
        self.dialog = None
        self.selected_icon = -1
        
        self.theme = get_theme(self.theme_name)
        self.default_show_hidden = bool(self.config.show_hidden)
        self.default_word_wrap = bool(self.config.word_wrap_default)
        self.default_sunday_first = bool(self.config.sunday_first)
        self.show_welcome = bool(self.config.show_welcome)
        self.icon_style = self._normalize_icon_style(getattr(self.config, "icon_style", ICON_STYLE_DEFAULT))
        self._dirty = True  # Render flag: redraw only when True
        self._dragging_win = None   # O(1) drag tracking
        self._resizing_win = None   # O(1) resize tracking
        self._last_icon_click_idx = None
        self._last_icon_click_ts = 0.0
        self.double_click_interval = None
        self._mouse_norm = None
        self._active_window_menu_owner = None
        self.drag_drop = DragDropManager(self)
        # Movable desktop icon positions: mapping icon_key -> (x, y)
        self._icon_mgr = IconPositionManager(self)
        self._background_operation = None
        self._file_ops = FileOperationManager(self)
        self._dialog_dispatcher = DialogDispatcher(self)
        self.input_timeout_idle_ms = TERMINAL_INPUT_TIMEOUT_MS
        self.input_timeout_live_terminal_ms = TERMINAL_LIVE_INPUT_TIMEOUT_MS
        self.input_timeout_background_ms = TERMINAL_BACKGROUND_INPUT_TIMEOUT_MS
        self.mouse_backend = detect_mouse_backend()

        # Plugin discovery and registration (optional; failures should not crash).
        self._load_plugins_runtime()
        # Setup terminal
        configure_terminal(stdscr, timeout_ms=TERMINAL_INPUT_TIMEOUT_MS)
        self._validate_terminal_size()

        disable_flow_control()
        self.click_flags, self.stop_drag_flags, self.scroll_down_mask = enable_mouse_support()
        self.button1_pressed = False  # Track physical button state for TTY drags

        init_colors(self.theme)

        # Create a welcome window if enabled
        if self.show_welcome:
            h, w = stdscr.getmaxyx()
            welcome_content = build_welcome_content(APP_VERSION)
            win = Window('Welcome to RetroTUI', w // 2 - WELCOME_WIN_WIDTH // 2, h // 2 - WELCOME_WIN_HEIGHT // 2, WELCOME_WIN_WIDTH, WELCOME_WIN_HEIGHT,
                          content=welcome_content)
            
            # Custom handler to process "Don't show again"
            def _welcome_handle_key(key):
                if getattr(curses, "KEY_F9", -1) == key or key == "KEY_F9":
                    self.show_welcome = False
                    self.persist_config()
                    self.close_window(win)
                    return ActionResult(ActionType.REFRESH)
                return Window.handle_key(win, key)

            win.handle_key = _welcome_handle_key
            win.active = True
            self.windows.append(win)
        # load persisted icon positions (if any)
        try:
            self._load_icon_positions()
        except _CONFIG_PERSIST_ERRORS:
            # don't fail startup on parse errors
            LOGGER.debug('failed to load icon positions', exc_info=True)

    def _load_plugins_runtime(self):
        """Discover and register plugins (best effort; never crash startup)."""
        self._plugins = {}
        try:
            from ..plugins.loader import discover_plugins, load_plugin
        except _PLUGIN_DISCOVERY_IMPORT_ERRORS:
            LOGGER.debug('plugin discovery unavailable', exc_info=True)
            self.refresh_icons()
            self._rebuild_global_menu()
            return

        for manifest in discover_plugins():
            self._register_plugin_manifest(manifest, load_plugin)
        self.refresh_icons()
        self._rebuild_global_menu()

    def _build_plugin_menu_items(self):
        """Build dynamic plugin entries as menu tuples ``(label, action)``."""
        hidden_menu_items = self._get_hidden_menu_keys()
        entries = []
        for plugin_id, info in (getattr(self, "_plugins", None) or {}).items():
            plugin_info = (info.get("manifest", {}) or {}).get("plugin", {}) or {}
            name = str(plugin_info.get("name") or plugin_id)
            action = f"plugin:{plugin_id}"
            item_key = self._menu_item_visibility_key(name, action)
            if item_key in hidden_menu_items:
                continue
            entries.append((name, action))
        entries.sort(key=lambda item: (item[0].lower(), item[1]))
        return entries

    def _build_global_menu_items(self):
        """Return global menu items with hidden-label filtering and plugin section."""
        hidden_menu_items = self._get_hidden_menu_keys()
        from ..ui.menu import DEFAULT_GLOBAL_ITEMS

        filtered_menu_items = {}
        for category, items in DEFAULT_GLOBAL_ITEMS.items():
            filtered_items = []
            for label, action in items:
                item_key = self._menu_item_visibility_key(label, action)
                if item_key not in hidden_menu_items:
                    filtered_items.append((label, action))
            if filtered_items:
                filtered_menu_items[category] = filtered_items

        plugin_items = self._build_plugin_menu_items()
        if not plugin_items:
            plugin_items = [("(No plugins installed)", None)]
        filtered_menu_items["Plugins"] = plugin_items

        return filtered_menu_items

    def _rebuild_global_menu(self):
        """Rebuild global menu preserving previous selection when possible."""
        from ..ui.menu import Menu

        previous = getattr(self, "menu", None)
        was_active = bool(getattr(previous, "active", False))
        selected_menu = int(getattr(previous, "selected_menu", 0) or 0)
        selected_item = int(getattr(previous, "selected_item", 0) or 0)

        menu = Menu(self._build_global_menu_items())
        menu_names = list(getattr(menu, "menu_names", ()) or ())
        if was_active and menu_names:
            menu.active = True
            menu.selected_menu = max(0, min(selected_menu, len(menu_names) - 1))
            current_items = list(
                (getattr(menu, "items", {}) or {}).get(menu_names[menu.selected_menu], ())
            )
            if current_items:
                menu.selected_item = max(0, min(selected_item, len(current_items) - 1))
            else:
                menu.selected_item = 0

        self.menu = menu

    def _register_plugin_manifest(self, manifest, load_plugin):
        """Register one plugin manifest with defensive isolation."""
        try:
            app_class = load_plugin(manifest)
        except _RUNTIME_ISOLATION_ERRORS:
            LOGGER.debug('failed to load plugin manifest', exc_info=True)
            return
        if not app_class:
            return
        plugin_info = manifest.get('plugin', {})
        pid = plugin_info.get('id')
        if not pid:
            return
        self._plugins[pid] = {
            'class': app_class,
            'manifest': manifest,
        }

    def _close_window_safely(self, win):
        """Run window close hook without allowing cleanup-time crashes."""
        closer = getattr(win, 'close', None)
        if not callable(closer):
            return
        try:
            closer()
        except _RUNTIME_ISOLATION_ERRORS:  # pragma: no cover - defensive cleanup path
            LOGGER.debug('Window cleanup failed for %r', win, exc_info=True)

    def _invoke_callable_action(self, action):
        """Execute callable actions with failure isolation."""
        try:
            return action()
        except _RUNTIME_ISOLATION_ERRORS:
            LOGGER.debug('callable action failed', exc_info=True)
            return None

    def _build_plugin_window(self, info, plugin_id):
        """Instantiate plugin window object from manifest metadata."""
        manifest = info.get('manifest', {}).get('plugin', {})
        win_config = manifest.get('window', {})
        w = int(win_config.get('default_width', 40))
        h = int(win_config.get('default_height', 15))
        try:
            cls = info.get('class')
            x, y = self._next_window_offset(8, 3)
            return cls(manifest.get('name', plugin_id), x, y, w, h)
        except _RUNTIME_ISOLATION_ERRORS:
            LOGGER.debug('failed to open plugin %s', plugin_id, exc_info=True)
            return None

    @staticmethod
    def _split_config_csv(raw):
        """Return lowercased non-empty comma-separated tokens from *raw* string."""
        if not isinstance(raw, str):
            return set()
        return {token.strip().lower() for token in raw.split(",") if token.strip()}

    @staticmethod
    def _menu_item_visibility_key(label, action):
        """Return stable visibility key for one global menu item."""
        if isinstance(action, AppAction):
            return action.value.lower()
        if isinstance(action, str):
            return action.lower()
        base_label = str(label or "").split("  ")[0].strip().lower()
        return base_label

    def _icon_visibility_key(self, icon):
        """Return stable visibility key for one desktop icon entry."""
        hide_key = icon.get("hide_key")
        if isinstance(hide_key, str) and hide_key.strip():
            return hide_key.strip().lower()
        return str(icon.get("label", "")).strip().lower()

    def _plugin_icon_art(self, plugin_name):
        """Build compact 3x4 icon art for plugin desktop entries."""
        token = ''.join(ch for ch in str(plugin_name) if ch.isalnum())[:2].upper()
        if not token:
            token = "PL"
        if len(token) == 1:
            token += " "
        if self.use_unicode:
            return ["┌──┐", f"│{token}│", "└──┘"]
        return ["+--+", f"|{token}|", "+--+"]

    def _build_plugin_icons(self):
        """Return plugin entries as desktop icons."""
        icons = []
        for plugin_id, info in (getattr(self, "_plugins", None) or {}).items():
            plugin_info = (info.get("manifest", {}) or {}).get("plugin", {}) or {}
            name = str(plugin_info.get("name") or plugin_id)
            icons.append(
                {
                    "label": name,
                    "action": f"plugin:{plugin_id}",
                    "art": self._plugin_icon_art(name),
                    "category": "Plugins",
                    "hide_key": f"plugin:{plugin_id}",
                }
            )
        icons.sort(key=lambda item: (item.get("label", "").lower(), item.get("action", "")))
        return icons

    def _build_desktop_icon_catalog(self):
        """Return full desktop icon catalog (apps, games, plugins)."""
        base_icons = ICONS if self.use_unicode else ICONS_ASCII
        catalog = [dict(icon) for icon in base_icons]
        catalog.extend(self._build_plugin_icons())
        return catalog

    def _build_menu_editor_catalog(self):
        """Return editable menu entries (apps, games, plugins) with stable keys."""
        from ..ui.menu import DEFAULT_GLOBAL_ITEMS

        entries = []
        for category, items in DEFAULT_GLOBAL_ITEMS.items():
            for label, action in items:
                if action is None:
                    continue
                base_label = str(label).split("  ")[0].strip()
                entries.append(
                    {
                        "category": category,
                        "label": base_label,
                        "action": action,
                        "key": self._menu_item_visibility_key(base_label, action),
                    }
                )

        for plugin_id, info in (getattr(self, "_plugins", None) or {}).items():
            plugin_info = (info.get("manifest", {}) or {}).get("plugin", {}) or {}
            name = str(plugin_info.get("name") or plugin_id)
            action = f"plugin:{plugin_id}"
            entries.append(
                {
                    "category": "Plugins",
                    "label": name,
                    "action": action,
                    "key": self._menu_item_visibility_key(name, action),
                }
            )

        entries.sort(key=lambda item: (item["category"].lower(), item["label"].lower()))
        return entries

    def _get_hidden_icon_labels(self):
        """Return set of lowercased hidden desktop icon keys from config."""
        raw = getattr(self.config, 'hidden_icons', "")
        return self._split_config_csv(raw)

    def _get_hidden_menu_keys(self):
        """Return set of lowercased hidden global menu item keys from config."""
        raw = getattr(self.config, 'hidden_menu_items', "")
        return self._split_config_csv(raw)

    @staticmethod
    def _normalize_icon_style(style):
        """Return supported icon style key."""
        normalized = str(style or ICON_STYLE_DEFAULT).strip().lower()
        if normalized == ICON_STYLE_RETRO_01:
            return ICON_STYLE_MINI
        if normalized in (ICON_STYLE_DEFAULT, ICON_STYLE_MINI, ICON_STYLE_BRAILLE, ICON_STYLE_CODEX):
            return normalized
        return ICON_STYLE_DEFAULT

    @staticmethod
    def _icon_style_variants():
        """Return per-icon style variants keyed by action/value key."""
        return {
            AppAction.FILE_MANAGER.value: {"mini": ":D", "braille": "⠋⠊", "codex": "⟠F"},
            AppAction.NOTEPAD.value: {"mini": ":|", "braille": "⠝⠏", "codex": "⟠N"},
            AppAction.ASCII_VIDEO.value: {"mini": "AV", "braille": "⠁⠧", "codex": "⟠V"},
            AppAction.TERMINAL.value: {"mini": ">:", "braille": "⠞⠍", "codex": "⟠T"},
            AppAction.CALCULATOR.value: {"mini": "+)", "braille": "⠉⠁", "codex": "⟠C"},
            AppAction.LOG_VIEWER.value: {"mini": "LG", "braille": "⠇⠛", "codex": "⟠L"},
            AppAction.PROCESS_MANAGER.value: {"mini": "PS", "braille": "⠏⠎", "codex": "⟠P"},
            AppAction.CLOCK_CALENDAR.value: {"mini": "CK", "braille": "⠉⠅", "codex": "⟠K"},
            AppAction.IMAGE_VIEWER.value: {"mini": "IM", "braille": "⠊⠍", "codex": "⟠I"},
            AppAction.TRASH_BIN.value: {"mini": "TR", "braille": "⠞⠗", "codex": "⟠R"},
            AppAction.SETTINGS.value: {"mini": "8)", "braille": "⠎⠞", "codex": "⟠S"},
            AppAction.ABOUT.value: {"mini": "i)", "braille": "⠁⠃", "codex": "⟠A"},
            AppAction.MINESWEEPER.value: {"mini": "MX", "braille": "⠍⠭", "codex": "⟠M"},
            AppAction.SOLITAIRE.value: {"mini": "SL", "braille": "⠎⠇", "codex": "⟠$"},
            AppAction.SNAKE.value: {"mini": "SN", "braille": "⠎⠝", "codex": "⟠Z"},
            AppAction.CHARMAP.value: {"mini": "CH", "braille": "⠉⠓", "codex": "⟠H"},
            AppAction.CLIPBOARD.value: {"mini": "CB", "braille": "⠉⠃", "codex": "⟠B"},
            AppAction.HEX_VIEWER.value: {"mini": "0x", "braille": "⠓⠭", "codex": "⟠X"},
            AppAction.WIFI_MANAGER.value: {"mini": "))", "braille": "⠺⠋", "codex": "⟠W"},
            AppAction.DESKTOP_ICON_MANAGER.value: {"mini": "DT", "braille": "⠙⠞", "codex": "⟠D"},
            AppAction.ICONS.value: {"mini": ":)", "braille": "⠊⠉", "codex": "⟠O"},
            AppAction.MENU_EDITOR.value: {"mini": "MN", "braille": "⠍⠝", "codex": "⟠E"},
            AppAction.MARKDOWN_VIEWER.value: {"mini": "MD", "braille": "⠍⠙", "codex": "⟠Y"},
            AppAction.SYSTEM_MONITOR.value: {"mini": "SM", "braille": "⠎⠍", "codex": "⟠U"},
            AppAction.CONTROL_PANEL.value: {"mini": "CT", "braille": "⠉⠞", "codex": "⟠Q"},
            AppAction.TETRIS.value: {"mini": "TT", "braille": "⠞⠞", "codex": "⟠#"},
            AppAction.RETRONET.value: {"mini": "RN", "braille": "⠗⠝", "codex": "⟠G"},
        }

    def _style_symbol_for_icon(self, icon, style):
        """Return style-specific symbol token for one icon."""
        action = icon.get("action")
        key = getattr(action, "value", action)
        key = str(key or "").lower()
        by_icon = self._icon_style_variants().get(key, {})

        if key.startswith("plugin:"):
            if style == ICON_STYLE_MINI:
                return ":)"
            if style == ICON_STYLE_BRAILLE:
                return "⠏⠇"
            if style == ICON_STYLE_CODEX:
                return "⟠PL"
            return None

        return by_icon.get(style)

    def _styled_icon_entry(self, icon):
        """Return style-adjusted icon entry for current desktop icon style."""
        style = self._normalize_icon_style(getattr(self, "icon_style", ICON_STYLE_DEFAULT))
        if style == ICON_STYLE_DEFAULT:
            return dict(icon)

        styled = dict(icon)
        symbol = self._style_symbol_for_icon(styled, style)
        if symbol:
            styled["symbol"] = symbol
            token = symbol[:2].ljust(2)
            if self.use_unicode and style in (ICON_STYLE_MINI, ICON_STYLE_CODEX):
                styled["art"] = ["╭──╮", f"│{token}│", "╰──╯"]
            elif self.use_unicode and style == ICON_STYLE_BRAILLE:
                styled["art"] = ["┌──┐", f"│{token}│", "└──┘"]
            else:
                styled["art"] = ["+--+", f"|{token}|", "+--+"]
        return styled

    def icon_style_preview_symbol(self, style, icon_key=AppAction.FILE_MANAGER.value):
        """Return one preview symbol token for *style* and *icon_key*."""
        normalized = self._normalize_icon_style(style)
        if normalized == ICON_STYLE_DEFAULT:
            base_icons = ICONS if getattr(self, "use_unicode", True) else ICONS_ASCII
            target_key = str(icon_key or "").lower()
            for icon in base_icons:
                action = icon.get("action")
                action_key = getattr(action, "value", action)
                if str(action_key or "").lower() != target_key:
                    continue
                symbol = icon.get("symbol")
                if isinstance(symbol, str) and symbol:
                    return symbol
                art = icon.get("art") or []
                if len(art) >= 2 and isinstance(art[1], str):
                    mid = art[1].strip("| ").strip()
                    if mid:
                        return mid
            return "[]"
        probe_icon = {"action": icon_key}
        return self._style_symbol_for_icon(probe_icon, normalized) or "[]"

    def set_icon_style(self, style):
        """Set desktop icon style and refresh icon catalog."""
        self.icon_style = self._normalize_icon_style(style)
        self.refresh_icons()

    def apply_theme(self, theme_name):
        """Apply a theme immediately to current runtime."""
        self.theme = get_theme(theme_name)
        self.theme_name = self.theme.key
        init_colors(self.theme)

    def refresh_icons(self):
        """Rebuild desktop icons list based on config and unicode support."""
        hidden_keys = self._get_hidden_icon_labels()
        catalog = self._build_desktop_icon_catalog()
        visible = [icon for icon in catalog if self._icon_visibility_key(icon) not in hidden_keys]
        self.icons = [self._styled_icon_entry(icon) for icon in visible]

    def apply_preferences(self, *, show_hidden=None, word_wrap_default=None, sunday_first=None, apply_to_open_windows=False):
        """Apply runtime preferences used by app windows and defaults."""
        if show_hidden is not None:
            self.default_show_hidden = bool(show_hidden)
        if word_wrap_default is not None:
            self.default_word_wrap = bool(word_wrap_default)
        if sunday_first is not None:
            self.default_sunday_first = bool(sunday_first)

        if not apply_to_open_windows:
            return

        for win in list(self.windows):
            if hasattr(win, 'show_hidden') and hasattr(win, '_rebuild_content'):
                if win.show_hidden != self.default_show_hidden:
                    win.show_hidden = self.default_show_hidden
                    win._rebuild_content()
            if hasattr(win, 'wrap_mode') and hasattr(win, '_invalidate_wrap'):
                if win.wrap_mode != self.default_word_wrap:
                    win.wrap_mode = self.default_word_wrap
                    win.view_left = 0
                    win._invalidate_wrap()
                    ensure_visible = getattr(win, '_ensure_cursor_visible', None)
                    if callable(ensure_visible):
                        ensure_visible()

    def persist_config(self):
        """Persist current runtime preferences to ~/.config/retrotui/config.toml."""
        # Sync back clock preferences from any open Clock window
        from ..apps.clock import ClockCalendarWindow
        for win in self.windows:
            if isinstance(win, ClockCalendarWindow):
                self.default_sunday_first = win.week_starts_sunday
                break
        self.config = AppConfig(
            theme=self.theme_name,
            show_hidden=self.default_show_hidden,
            word_wrap_default=self.default_word_wrap,
            sunday_first=self.default_sunday_first,
            show_welcome=self.show_welcome,
            icon_style=self._normalize_icon_style(getattr(self, "icon_style", ICON_STYLE_DEFAULT)),
            hidden_icons=getattr(self.config, 'hidden_icons', ""),
            hidden_menu_items=getattr(self.config, 'hidden_menu_items', ""),
        )
        path = save_config(self.config)
        try:
            self._save_icon_positions(path)
        except _CONFIG_PERSIST_ERRORS:
            LOGGER.debug('failed to save icon positions', exc_info=True)
        return path

    def _load_icon_positions(self):
        from .config import default_config_path
        return self._icon_mgr.load(default_config_path())

    def _save_icon_positions(self, cfg_path=None):
        from .config import default_config_path
        path = cfg_path if cfg_path is not None else default_config_path()
        self._icon_mgr.save(path)

    def handle_right_click(self, mx, my, bstate):
        """Dispatch right-clicks to windows or desktop. Return True if handled."""
        # If a context menu is already open, let it consume the click first.
        if self.context_menu and self.context_menu.active:
            try:
                action = self.context_menu.handle_click(mx, my)
            except _INPUT_ROUTE_ERRORS:
                LOGGER.debug('context menu click handler failed', exc_info=True)
                action = None
            if action is not None:
                self.execute_action(action)
                return True
            # If the menu remains open (e.g., separator click), consume event.
            is_open = getattr(self.context_menu, "is_open", None)
            if callable(is_open) and is_open():
                return True

        # Try windows first (topmost)
        for win in reversed(self.windows):
            if not getattr(win, 'visible', False):
                continue
            contains = getattr(win, 'contains', None)
            if not callable(contains) or not contains(mx, my):
                continue

            # Route subsequent context-menu actions to the clicked window.
            self.set_active_window(win)

            handler = getattr(win, 'handle_right_click', None)
            if callable(handler):
                try:
                    res = _invoke_mouse_handler(handler, mx, my, bstate)
                except _INPUT_ROUTE_ERRORS:
                    LOGGER.debug('window right-click handler failed', exc_info=True)
                    res = None

                # If window handled it (returned True or ActionResult), we stop.
                if isinstance(res, list):
                    from ..ui.context_menu import ContextMenu
                    self.context_menu = ContextMenu(self.theme)
                    self.context_menu.show(mx, my, res)
                    return True

                if res:
                    self._dispatch_window_result(res, win)
                    return True

        # Desktop hook
        try:
            return bool(self._handle_desktop_right_click(mx, my, bstate))
        except _INPUT_ROUTE_ERRORS:
            LOGGER.debug('desktop right-click handler failed', exc_info=True)
            return False

    def _handle_desktop_right_click(self, mx, my, bstate):
        """Open a desktop context menu or icon-specific menu at (mx,my)."""
        icon_idx = self.get_icon_at(mx, my)
        from ..ui.context_menu import ContextMenu

        if icon_idx >= 0:
            # Icon menu
            # Select the icon first
            self.selected_icon = icon_idx
            icon = self.icons[icon_idx]
            items = [
                {'label': 'Open', 'action': icon.get('action')},
                {'separator': True},
                {'label': 'Properties', 'action': lambda selected_icon=icon: self._show_icon_properties(selected_icon)},
            ]
        else:
            # Desktop menu
            items = [
                {'label': 'New Terminal', 'action': AppAction.TERMINAL},
                {'label': 'New Notepad', 'action': AppAction.NOTEPAD},
                {'separator': True},
                {'label': 'Desktop Icons', 'action': AppAction.DESKTOP_ICON_MANAGER},
                {'label': 'Icons', 'action': AppAction.ICONS},
                {'label': 'Menu Editor', 'action': AppAction.MENU_EDITOR},
                {'label': 'Sort Icons (A-Z)', 'action': self.sort_desktop_icons},
                {'separator': True},
                {'label': 'Theme', 'action': AppAction.SETTINGS},
                {'label': 'Settings', 'action': AppAction.SETTINGS},
                {'separator': True},
                {'label': 'About', 'action': AppAction.ABOUT},
                {'label': 'Exit', 'action': AppAction.EXIT},
            ]

        self.context_menu = ContextMenu(self.theme)
        self.context_menu.show(mx, my, items)
        return True

    def _show_icon_properties(self, icon):
        """Show a simple properties dialog for a desktop icon."""
        label = str(icon.get('label', 'Unknown'))
        category = str(icon.get('category', 'Apps'))
        action = icon.get('action')
        action_name = getattr(action, 'value', None) or str(action)
        message = (
            f'Name: {label}\n'
            f'Category: {category}\n'
            f'Action: {action_name}\n'
            f'RetroTUI: {APP_VERSION}'
        )
        self.dialog = Dialog(f'{label} Properties', message, ['OK'], width=54)
        return None

    def sort_desktop_icons(self):
        """Sort desktop icons alphabetically and persist the updated grid positions."""
        self._get_icon_mgr().sort_positions()
        self.selected_icon = -1
        return None

    def _validate_terminal_size(self):
        """Fail fast when terminal is too small for the base desktop layout."""
        h, w = self.stdscr.getmaxyx()
        if h < self.MIN_TERM_HEIGHT or w < self.MIN_TERM_WIDTH:
            raise ValueError(
                f'Terminal too small ({w}x{h}). '
                f'Minimum supported size is {self.MIN_TERM_WIDTH}x{self.MIN_TERM_HEIGHT}.'
            )

    def cleanup(self):
        """Restore terminal state."""
        self._restore_runtime_signal_handlers()
        op_state = getattr(self, '_background_operation', None)
        if op_state:
            thread = op_state.get('thread')
            if thread and thread.is_alive():
                thread.join(timeout=self.BACKGROUND_OPERATION_JOIN_TIMEOUT)
                if thread.is_alive():
                    LOGGER.warning(
                        'Background operation did not finish within %.1fs during shutdown.',
                        self.BACKGROUND_OPERATION_JOIN_TIMEOUT,
                    )
        for win in list(self.windows):
            self._close_window_safely(win)
        disable_mouse_support()

    def _install_runtime_signal_handlers(self):
        """Install runtime signal handlers (main thread only)."""
        if getattr(self, '_sigint_handler_installed', False):
            return
        if threading.current_thread() is not threading.main_thread():
            return
        planned = []
        sigint = getattr(signal, "SIGINT", None)
        if sigint is not None:
            planned.append((sigint, self._handle_sigint))
        sigbreak = getattr(signal, "SIGBREAK", None)
        if sigbreak is not None:
            planned.append((sigbreak, self._handle_sigint))
        sigtstp = getattr(signal, "SIGTSTP", None)
        if sigtstp is not None:
            planned.append((sigtstp, self._handle_sigtstp))
        for name in ("SIGTERM", "SIGHUP"):
            sig = getattr(signal, name, None)
            if sig is not None:
                planned.append((sig, self._handle_shutdown_signal))

        prev_handlers = {}
        for sig, handler in planned:
            try:
                previous = signal.getsignal(sig)
                signal.signal(sig, handler)
                prev_handlers[sig] = previous
            except (AttributeError, ValueError, OSError):
                continue

        self._prev_signal_handlers = prev_handlers
        self._prev_sigint_handler = prev_handlers.get(sigint)
        self._sigint_handler_installed = bool(prev_handlers)

    def _restore_runtime_signal_handlers(self):
        """Restore process signal handlers changed for runtime."""
        if not getattr(self, '_sigint_handler_installed', False):
            return
        prev_handlers = dict(getattr(self, "_prev_signal_handlers", {}) or {})
        sigint = getattr(signal, "SIGINT", None)
        if sigint is not None and sigint not in prev_handlers:
            prev = getattr(self, "_prev_sigint_handler", None)
            if prev is not None:
                prev_handlers[sigint] = prev

        for sig, prev in prev_handlers.items():
            if prev is None:
                continue
            try:
                signal.signal(sig, prev)
            except (AttributeError, ValueError, OSError):
                continue

        self._prev_signal_handlers = {}
        self._prev_sigint_handler = None
        self._sigint_handler_installed = False
        self._shutdown_signal = None

    def _handle_sigint(self, _signum, _frame):
        """Queue SIGINT as in-app Ctrl+C key instead of terminating session."""
        self._queue_pending_signal_key('\x03')

    def _handle_sigtstp(self, _signum, _frame):
        """Queue SIGTSTP as in-app Ctrl+Z key instead of suspending session."""
        self._queue_pending_signal_key('\x1a')

    def _queue_pending_signal_key(self, key):
        """Queue one pending control key generated by runtime signal handlers."""
        if not isinstance(key, str) or len(key) != 1:
            return
        queue = getattr(self, "_pending_signal_keys", None)
        if not isinstance(queue, list):
            queue = []
            self._pending_signal_keys = queue
        queue.append(key)
        if key == '\x03':
            self._pending_sigint = True

    def _handle_shutdown_signal(self, signum, _frame):
        """Request a clean shutdown on external termination signals."""
        self._shutdown_signal = signum
        self.running = False

    def _consume_pending_signal_key(self):
        """Return next queued control key generated by signal handlers."""
        queue = getattr(self, "_pending_signal_keys", None)
        if isinstance(queue, list) and queue:
            key = queue.pop(0)
            if key == '\x03':
                self._pending_sigint = any(item == '\x03' for item in queue)
            return key
        if getattr(self, "_pending_sigint", False):
            self._pending_sigint = False
            return '\x03'
        return None

    def _consume_pending_sigint(self):
        """Compatibility wrapper: return queued Ctrl+C key when available."""
        queue = getattr(self, "_pending_signal_keys", None)
        if isinstance(queue, list) and queue:
            for idx, key in enumerate(queue):
                if key == '\x03':
                    del queue[idx]
                    self._pending_sigint = any(item == '\x03' for item in queue)
                    return '\x03'
        if getattr(self, "_pending_sigint", False):
            self._pending_sigint = False
            return '\x03'
        return None

    def draw_desktop(self, frame_size=None):
        """Draw the desktop background pattern."""
        if frame_size is None:
            return draw_desktop(self)
        return draw_desktop(self, frame_size=frame_size)

    def draw_icons(self, frame_size=None):
        """Draw desktop icons (3x4 art + label)."""
        if frame_size is None:
            return draw_icons(self)
        return draw_icons(self, frame_size=frame_size)

    def draw_taskbar(self, frame_size=None):
        """Draw taskbar row with minimized window buttons."""
        if frame_size is None:
            return draw_taskbar(self)
        return draw_taskbar(self, frame_size=frame_size)

    def draw_statusbar(self, frame_size=None):
        """Draw the bottom status bar."""
        if frame_size is None:
            return draw_statusbar(self, APP_VERSION)
        return draw_statusbar(self, APP_VERSION, frame_size=frame_size)

    def get_icon_screen_pos(self, index):
        """Return (x, y) for icon at index, checking persisted positions then default grid."""
        return self._icon_mgr.get_screen_pos(index)

    def get_icon_at(self, mx, my):
        """Return icon index at mouse position, or -1."""
        return self._icon_mgr.get_icon_at(mx, my)

    def set_active_window(self, win):
        """Set a window as active (bring to front)."""
        self.window_mgr.set_active_window(win)

    def normalize_window_layers(self):
        """Keep always-on-top windows above regular windows preserving order."""
        self.window_mgr.normalize_window_layers()

    def close_window(self, win):
        """Close a window."""
        self.window_mgr.close_window(win)

    def _activate_last_visible_window(self):
        """Activate topmost visible window after z-order/window-list changes."""
        return self.window_mgr._activate_last_visible_window()

    @staticmethod
    def _normalize_action(action):
        """Convert legacy string actions to AppAction when possible."""
        if isinstance(action, AppAction):
            return action
        if isinstance(action, str):
            try:
                return AppAction(action)
            except ValueError:
                return action
        return action

    def _spawn_window(self, win):
        """Append a window and make it active."""
        self.windows.append(win)
        self.set_active_window(win)

    def open_plugin(self, plugin_id):
        """Instantiate and open a plugin window by id."""
        if not getattr(self, '_plugins', None):
            return
        info = self._plugins.get(plugin_id)
        if not info:
            LOGGER.debug('plugin not found: %s', plugin_id)
            return
        win = self._build_plugin_window(info, plugin_id)
        if win is not None:
            self._spawn_window(win)

    def _next_window_offset(self, base_x, base_y, step_x=2, step_y=1):
        """Return staggered window coordinates based on open window count."""
        return self.window_mgr._next_window_offset(base_x, base_y, step_x, step_y)

    def execute_action(self, action):
        """Execute a menu/icon action."""
        action = self._normalize_action(action)
        LOGGER.debug('execute_action: %s', action)

        if callable(action):
            result = self._invoke_callable_action(action)
            if result is None:
                return
            if hasattr(result, 'type'):
                self._dispatch_window_result(result, self.get_active_window())
                return
            self.execute_action(result)
            return

        # 1. Try delegating to the active window first (for context menu / internal actions)
        active_win = self.get_active_window()
        if active_win and hasattr(active_win, 'execute_action'):
            result = active_win.execute_action(action)
            if result:
                self._dispatch_window_result(result, active_win)
                return

        # 2. Fallback to global/app-level actions
        execute_app_action(self, action, LOGGER, version=APP_VERSION)

    # Margin subtracted from screen dimensions when sizing viewer windows.
    _WINDOW_MARGIN = 4

    def _detect_viewer_type(self, filepath):
        """Determine the appropriate viewer for a file.

        Returns a tuple ``(WindowClass, base_x, base_y, max_w, max_h, extra_kwargs)``.
        """
        lower_path = filepath.lower()
        ext = os.path.splitext(lower_path)[1]

        _LOG_EXTENSIONS = {'.log', '.out', '.err'}
        if ext in _LOG_EXTENSIONS or '/log/' in lower_path or '\\log\\' in lower_path:
            return (LogViewerWindow, 16, 4, 74, 22, {})

        if ext in ImageViewerWindow.IMAGE_EXTENSIONS:
            return (ImageViewerWindow, 14, 3, 84, 26, {})

        if ext == '.md':
            return (MarkdownViewerWindow, 18, 3, 70, 25, {})

        # Content-based detection: null bytes indicate a binary file.
        try:
            with open(filepath, 'rb') as f:
                chunk = f.read(BINARY_DETECT_CHUNK_SIZE)
                if b'\x00' in chunk:
                    return (HexViewerWindow, 12, 3, 92, 26, {})
        except OSError:
            pass

        # Default: plain-text viewer.
        return (
            NotepadWindow,
            18, 3, 70, 25,
            {'wrap_default': getattr(self, 'default_word_wrap', False)},
        )

    def open_file_viewer(self, filepath):
        """Open file in the best available viewer."""
        if is_video_file(filepath):
            self._play_ascii_video(filepath)
            return

        cls, base_x, base_y, max_w, max_h, extra_kwargs = self._detect_viewer_type(filepath)
        h, w = self.stdscr.getmaxyx()
        ox, oy = self._next_window_offset(base_x, base_y)
        win = cls(
            ox, oy,
            min(max_w, w - self._WINDOW_MARGIN),
            min(max_h, h - self._WINDOW_MARGIN),
            filepath=filepath,
            **extra_kwargs,
        )
        self._spawn_window(win)

    def _play_ascii_video(self, filepath, subtitle_path=None):
        """Run ASCII video playback and surface backend errors in a dialog."""
        success, error = play_ascii_video(self.stdscr, filepath, subtitle_path=subtitle_path)
        if not success:
            self.dialog = Dialog('ASCII Video Error', error, ['OK'], width=58)

    def show_url_dialog(self, source_win, default_url=None):
        """Show input dialog for web URLs."""
        from ..ui.dialog import InputDialog
        # If payload is provided, use it; otherwise fallback to current window url if available
        initial = default_url or getattr(source_win, 'url', '')
        dialog = InputDialog('RetroNet Explorer', 'Enter URL:', initial_value=initial, width=64)
        dialog.callback = source_win.open_path
        self.dialog = dialog

    def show_video_open_dialog(self):
        """Open dialog flow to play a video path without using File Manager."""
        dialog = InputDialog('Open Video', 'Enter video path:', width=64)
        dialog.callback = self._handle_video_path_input
        self.dialog = dialog

    def _handle_video_path_input(self, filepath):
        """Validate selected video path and request optional subtitle path."""
        raw_path = str(filepath or '').strip()
        if not raw_path:
            return ActionResult(ActionType.ERROR, 'Video path cannot be empty.')
        video_path = os.path.abspath(os.path.expanduser(raw_path))
        if not os.path.isfile(video_path):
            return ActionResult(ActionType.ERROR, f'Video file not found:\n{video_path}')
        if not is_video_file(video_path):
            return ActionResult(ActionType.ERROR, f'Unsupported video format:\n{video_path}')

        dialog = InputDialog(
            'Subtitles (Optional)',
            'Enter subtitle path (.srt/.ass/.vtt) or leave empty:',
            width=70,
        )
        dialog.callback = (
            lambda subtitle_path, selected_video=video_path: self._handle_subtitle_path_input(
                selected_video,
                subtitle_path,
            )
        )
        self.dialog = dialog
        return None

    def _handle_subtitle_path_input(self, video_path, subtitle_path):
        """Validate optional subtitle path and start playback."""
        subtitle = str(subtitle_path or '').strip()
        if subtitle:
            subtitle = os.path.abspath(os.path.expanduser(subtitle))
            if not os.path.isfile(subtitle):
                return ActionResult(ActionType.ERROR, f'Subtitle file not found:\n{subtitle}')
        else:
            subtitle = None
        self._play_ascii_video(video_path, subtitle_path=subtitle)
        return None

    def get_active_window(self):
        """Return the active window, if any."""
        return self.window_mgr.get_active_window()

    def _dispatch_window_result(self, result, source_win):
        """Handle ActionResult returned by window/dialog callbacks."""
        handled = self._get_dialog_dispatcher().dispatch_window_result(result, source_win)
        if handled is False and hasattr(result, 'type'):
            LOGGER.debug('Unhandled ActionResult type: %s', result.type)

    def _resolve_dialog_result(self, result_idx):
        """Apply dialog button result and run dialog callback when needed."""
        self._get_dialog_dispatcher().resolve_dialog_result(result_idx)

    def _handle_dialog_mouse(self, mx, my, bstate):
        """Handle mouse events when a modal dialog is open."""
        if not self.dialog:
            return False
        if not (bstate & self.click_flags):
            return True
        result = self.dialog.handle_click(mx, my)
        self._resolve_dialog_result(result)
        return True

    def _handle_dialog_key(self, key):
        """Handle keyboard events when a modal dialog is open."""
        if not self.dialog:
            return False
        result = self.dialog.handle_key(key)
        self._resolve_dialog_result(result)
        return True

    def handle_taskbar_click(self, mx, my):
        """Handle click on taskbar row. Returns True if handled."""
        return self.window_mgr.handle_taskbar_click(mx, my)

    def _handle_drag_resize_mouse(self, mx, my, bstate):
        """Handle active drag or resize operations."""
        return handle_drag_resize_mouse(self, mx, my, bstate)

    def _handle_global_menu_mouse(self, mx, my, bstate):
        """Handle mouse interaction when the global menu is active."""
        return handle_global_menu_mouse(self, mx, my, bstate)

    def _handle_window_mouse(self, mx, my, bstate, norm=None):
        """Route mouse events to windows in z-order."""
        if norm is None:
            norm = getattr(self, '_mouse_norm', None)
        return handle_window_mouse(self, mx, my, bstate, norm=norm)

    def _handle_desktop_mouse(self, mx, my, bstate, norm=None):
        """Handle desktop icon interactions and deselection."""
        if norm is None:
            norm = getattr(self, '_mouse_norm', None)
        return handle_desktop_mouse(self, mx, my, bstate, norm=norm)

    def handle_mouse(self, event):
        """Handle mouse events."""
        return handle_mouse_event(self, event)

    @staticmethod
    def _key_code(key):
        """Normalize key values from get_wch()/getch() into common control codes."""
        return normalize_app_key(key)

    def _handle_menu_hotkeys(self, key_code):
        """Handle F10 and Escape interactions for menus."""
        return handle_menu_hotkeys(self, key_code)

    def _handle_global_menu_key(self, key_code):
        """Handle keyboard navigation for the global menu."""
        return handle_global_menu_key(self, key_code)

    def _cycle_focus(self):
        """Cycle focus through visible windows."""
        return cycle_focus(self)

    def _handle_active_window_key(self, key):
        """Delegate key input to active window."""
        return handle_active_window_key(self, key)

    def handle_key(self, key):
        """Handle keyboard input."""
        return handle_key_event(self, key)

    def run(self):
        """Main event loop."""
        return run_app_loop(self)
