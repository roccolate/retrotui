"""
Main RetroTUI Application Class.
"""
import curses
import logging
import signal
import threading

from ..constants import (
    ICONS, ICONS_ASCII,
    TERMINAL_INPUT_TIMEOUT_MS,
    TERMINAL_LIVE_INPUT_TIMEOUT_MS,
    TERMINAL_BACKGROUND_INPUT_TIMEOUT_MS,
    WELCOME_WIN_WIDTH, WELCOME_WIN_HEIGHT,
    WIN_MIN_WIDTH, WIN_MIN_HEIGHT,
    _CURSES_ERROR,
)
from ..utils import check_unicode_support, init_colors
from ..theme import get_theme
from ..ui.dialog import Dialog, InputDialog, ProgressDialog
from ..ui.window import Window
from .config import AppConfig, CONFIG_SCHEMA_VERSION, load_config, save_config
from .actions import ActionResult, ActionType, AppAction, SaveConfirmPayload
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
from .mouse_utils import _is_button1_click_event
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
from .dialog_workflow import DialogWorkflowId, bind_dialog
from .bootstrap import (
    configure_terminal,
    disable_flow_control,
    detect_mouse_backend,
    enable_mouse_support,
    disable_mouse_support,
)
from .window_manager import WindowManager
from .icon_styles import (
    ICON_STYLE_DEFAULT,
    ICON_STYLE_MINI,
    ICON_STYLE_BRAILLE,
    ICON_STYLE_RETRO_01,
    normalize_icon_style,
    icon_style_variants as _icon_style_variants,
    style_symbol_for_icon as _style_symbol_for_icon,
    styled_icon_entry as _styled_icon_entry,
    icon_style_preview_symbol as _icon_style_preview_symbol,
    icon_visibility_key as _icon_visibility_key,
    get_hidden_icon_labels as _get_hidden_icon_labels,
    split_config_csv as _split_config_csv,
    plugin_icon_art as _plugin_icon_art,
    build_plugin_icons as _build_plugin_icons,
    build_desktop_icon_catalog as _build_desktop_icon_catalog,
    refresh_icons as _refresh_icons,
)
from .signal_handler import (
    install_runtime_signal_handlers,
    restore_runtime_signal_handlers,
    queue_pending_signal_key,
    consume_pending_signal_key,
    consume_pending_sigint,
)
from .plugin_manager import (
    load_plugins_runtime,
    register_plugin_manifest,
    build_plugin_menu_items,
    build_plugin_window,
    open_plugin as _open_plugin,
)
from .menu_builder import (
    menu_item_visibility_key as _menu_item_visibility_key,
    get_hidden_menu_keys as _get_hidden_menu_keys,
    build_global_menu_items,
    rebuild_global_menu,
    build_menu_editor_catalog,
)
from .viewer import (
    show_url_dialog as _show_url_dialog,
    show_video_open_dialog as _show_video_open_dialog,
)
from .context_menu_handler import (
    handle_right_click as _handle_right_click,
    handle_desktop_right_click as _handle_desktop_right_click,
    show_icon_properties as _show_icon_properties,
)

LOGGER = logging.getLogger(__name__)

APP_VERSION = '0.9.5'
_CONFIG_PERSIST_ERRORS = (OSError, UnicodeError, ValueError, TypeError)
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

    def _show_save_confirm_dialog(self, win, payload=None):
        """Prompt before a destructive operation on unsaved work."""
        from ..ui.dialog import Dialog

        try:
            title = getattr(win, "title", "Notepad")
        except Exception:
            title = "Notepad"
        message = (
            f"{title} has unsaved changes.\n"
            "Discard them and continue?"
        )
        request = SaveConfirmPayload.from_value(payload)
        on_discard = request.on_discard
        on_cancel = request.on_cancel
        if request.message.strip():
            message = request.message
        if on_discard is None:
            fallback = getattr(win, "_do_open_path_force", None)
            if callable(fallback):
                on_discard = fallback

        self.dialog = bind_dialog(
            Dialog(
                title="Discard unsaved changes?",
                message=message,
                buttons=["Discard", "Cancel"],
                width=58,
            ),
            workflow_id=DialogWorkflowId.SAVE_CONFIRM,
            source_window=win,
            on_accept=on_discard,
            on_cancel=on_cancel,
        )

    def show_rename_dialog(self, win):
        return self.file_ops.show_rename_dialog(win)

    def show_delete_confirm_dialog(self, win):
        return self.file_ops.show_delete_confirm_dialog(win)

    def show_restore_trash(self, win):
        return self.file_ops.show_restore_trash(win)

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

    def _run_file_operation_with_progress(self, win, *, operation, destination=None, source_path=None):
        return self.file_ops._run_file_operation_with_progress(
            win,
            operation=operation,
            destination=destination,
            source_path=source_path,
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

    # ------------------------------------------------------------------
    # Event bus / IPC / Notifications (lazy-init for test compatibility)
    # ------------------------------------------------------------------

    @property
    def event_bus(self):
        """Return the EventBus, creating it lazily if needed."""
        if not hasattr(self, '_event_bus'):
            from .event_bus import EventBus
            self._event_bus = EventBus()
        return self._event_bus

    @property
    def ipc(self):
        """Return the IPCRouter, creating it lazily if needed."""
        if not hasattr(self, '_ipc'):
            from .ipc import IPCRouter
            self._ipc = IPCRouter(self.event_bus, lambda: self.windows)
        return self._ipc

    @property
    def notifications(self):
        """Return the NotificationManager, creating it lazily if needed."""
        if not hasattr(self, '_notifications'):
            from .notifications import NotificationManager
            self._notifications = NotificationManager(self.event_bus)
        return self._notifications

    def publish_event(self, topic, data=None, *, source=None):
        """Publish an event on the bus."""
        return self.event_bus.publish(topic, data, source=source)

    def notify(self, message, **kwargs):
        """Show a toast notification."""
        self.notifications.notify(message, **kwargs)
        self._dirty = True

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
        self._cleanup_started = False
        self._cleanup_complete = False
        # Create the lifecycle bus before managers so events and
        # subscriptions never depend on accidental access order.
        self._event_bus = self.event_bus
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
        self.icon_style = normalize_icon_style(getattr(self.config, "icon_style", ICON_STYLE_DEFAULT))
        self._dirty = True  # Render flag: redraw only when True
        self._dragging_win = None   # O(1) drag tracking
        self._resizing_win = None   # O(1) resize tracking
        # O(1) selection-drag owner pointer — set by
        # ``mouse_utils._set_mouse_selecting`` whenever a window starts
        # a text selection drag. ``_pointer_capture_owner`` and
        # ``_route_selection_drag_owner`` read this instead of walking
        # ``app.windows`` on every mouse event.
        self._mouse_selecting_window = None
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
            win = Window(
                'Welcome to RetroTUI',
                w // 2 - WELCOME_WIN_WIDTH // 2,
                h // 2 - WELCOME_WIN_HEIGHT // 2,
                WELCOME_WIN_WIDTH,
                WELCOME_WIN_HEIGHT,
                content=welcome_content,
                resizable=False,
                minimizable=False,
                maximizable=False,
            )

            def _refresh_welcome_content():
                win.content = build_welcome_content(
                    APP_VERSION,
                    show_on_startup=self.show_welcome,
                )

            def _persist_welcome_preference(show_on_startup):
                self.apply_preferences(show_welcome=show_on_startup)
                _refresh_welcome_content()
                self.persist_config()
                self._dirty = True

            def _toggle_welcome_preference():
                _persist_welcome_preference(not self.show_welcome)
                return ActionResult(ActionType.REFRESH)

            def _welcome_checkbox_row():
                for idx, line in enumerate(getattr(win, "content", ())):
                    if "Show welcome on startup" in line:
                        return win.y + 1 + idx
                return None

            # Custom handler to process the startup preference checkbox.
            def _welcome_handle_key(key):
                if getattr(curses, "KEY_F9", -1) == key or key == "KEY_F9":
                    _persist_welcome_preference(False)
                    self.close_window(win)
                    return ActionResult(ActionType.REFRESH)
                if key in (" ", "\n", "\r", 10, 13, getattr(curses, "KEY_ENTER", -1)):
                    return _toggle_welcome_preference()
                return Window.handle_key(win, key)

            def _welcome_handle_click(mx, my, bstate=None):
                _ = bstate
                checkbox_y = _welcome_checkbox_row()
                if checkbox_y is not None and my == checkbox_y:
                    bx, _by, bw, _bh = win.body_rect()
                    if bx <= mx < bx + bw:
                        return _toggle_welcome_preference()
                return Window.handle_click(win, mx, my)

            win.handle_key = _welcome_handle_key
            win.handle_click = _welcome_handle_click
            self._spawn_window(win)
        # load persisted icon positions (if any)
        try:
            self._load_icon_positions()
        except _CONFIG_PERSIST_ERRORS:
            # don't fail startup on parse errors
            LOGGER.debug('failed to load icon positions', exc_info=True)

    # ------------------------------------------------------------------
    # Plugin system (delegates to plugin_manager module)
    # ------------------------------------------------------------------

    def _load_plugins_runtime(self):
        """Discover and register plugins (best effort; never crash startup)."""
        load_plugins_runtime(self)

    def _register_plugin_manifest(self, manifest, load_plugin_fn):
        """Register one plugin manifest with defensive isolation."""
        register_plugin_manifest(self, manifest, load_plugin_fn)

    def _build_plugin_menu_items(self):
        """Build dynamic plugin entries as menu tuples ``(label, action)``."""
        return build_plugin_menu_items(self)

    def _build_plugin_window(self, info, plugin_id):
        """Instantiate plugin window object from manifest metadata."""
        return build_plugin_window(self, info, plugin_id)

    def open_plugin(self, plugin_id):
        """Instantiate and open a plugin window by id."""
        _open_plugin(self, plugin_id)

    # ------------------------------------------------------------------
    # Menu building (delegates to menu_builder module)
    # ------------------------------------------------------------------

    @staticmethod
    def _split_config_csv(raw):
        """Return lowercased non-empty comma-separated tokens from *raw* string."""
        return _split_config_csv(raw)

    @staticmethod
    def _menu_item_visibility_key(label, action):
        """Return stable visibility key for one global menu item."""
        return _menu_item_visibility_key(label, action)

    def _get_hidden_menu_keys(self):
        """Return set of lowercased hidden global menu item keys from config."""
        return _get_hidden_menu_keys(self.config)

    def _build_global_menu_items(self):
        """Return global menu items with hidden-label filtering and plugin section."""
        return build_global_menu_items(self)

    def _rebuild_global_menu(self):
        """Rebuild global menu preserving previous selection when possible."""
        rebuild_global_menu(self)

    def _build_menu_editor_catalog(self):
        """Return editable menu entries (apps, games, plugins) with stable keys."""
        return build_menu_editor_catalog(self)

    # ------------------------------------------------------------------
    # Icon system (delegates to icon_styles module)
    # ------------------------------------------------------------------

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

    @staticmethod
    def _normalize_icon_style(style):
        """Return supported icon style key."""
        return normalize_icon_style(style)

    @staticmethod
    def _icon_style_variants():
        """Return per-icon style variants keyed by action/value key."""
        return _icon_style_variants()

    def _style_symbol_for_icon(self, icon, style):
        """Return style-specific symbol token for one icon."""
        return _style_symbol_for_icon(icon, style)

    def _styled_icon_entry(self, icon):
        """Return style-adjusted icon entry for current desktop icon style."""
        return _styled_icon_entry(
            icon,
            getattr(self, "icon_style", ICON_STYLE_DEFAULT),
            getattr(self, "use_unicode", True),
        )

    def icon_style_preview_symbol(self, style, icon_key=AppAction.FILE_MANAGER.value):
        """Return one preview symbol token for *style* and *icon_key*."""
        return _icon_style_preview_symbol(
            style,
            icon_key,
            getattr(self, "use_unicode", True),
        )

    def set_icon_style(self, style):
        """Set desktop icon style and refresh icon catalog."""
        self.icon_style = normalize_icon_style(style)
        self.refresh_icons()

    def _icon_visibility_key(self, icon):
        """Return stable visibility key for one desktop icon entry."""
        return _icon_visibility_key(icon)

    def _get_hidden_icon_labels(self):
        """Return set of lowercased hidden desktop icon keys from config."""
        return _get_hidden_icon_labels(self.config)

    def _plugin_icon_art(self, plugin_name):
        """Build compact 3x4 icon art for plugin desktop entries."""
        return _plugin_icon_art(plugin_name, self.use_unicode)

    def _build_plugin_icons(self):
        """Return plugin entries as desktop icons."""
        return _build_plugin_icons(getattr(self, "_plugins", None), self.use_unicode)

    def _build_desktop_icon_catalog(self):
        """Return full desktop icon catalog (apps, games, plugins)."""
        return _build_desktop_icon_catalog(getattr(self, "_plugins", None), self.use_unicode)

    def refresh_icons(self):
        """Rebuild desktop icons list based on config and unicode support."""
        _refresh_icons(self)

    # ------------------------------------------------------------------
    # Theme & preferences
    # ------------------------------------------------------------------

    def apply_theme(self, theme_name):
        """Apply a theme immediately to current runtime."""
        self.theme = get_theme(theme_name)
        self.theme_name = self.theme.key
        init_colors(self.theme)
        # New palette won't show until the renderer picks up the new
        # color pairs; flag the next frame so the change is visible
        # immediately even when no other UI event would dirty the
        # screen.
        self._dirty = True

    def apply_preferences(
        self,
        *,
        show_hidden=None,
        word_wrap_default=None,
        sunday_first=None,
        show_welcome=None,
        apply_to_open_windows=False,
    ):
        """Apply runtime preferences used by app windows and defaults."""
        if show_hidden is not None:
            self.default_show_hidden = bool(show_hidden)
        if word_wrap_default is not None:
            self.default_word_wrap = bool(word_wrap_default)
        if sunday_first is not None:
            self.default_sunday_first = bool(sunday_first)
        if show_welcome is not None:
            self.show_welcome = bool(show_welcome)

        if hasattr(self, '_event_bus'):
            self._event_bus.publish("config.changed", data={
                "show_hidden": getattr(self, "default_show_hidden", None),
                "word_wrap_default": getattr(self, "default_word_wrap", None),
                "sunday_first": getattr(self, "default_sunday_first", None),
                "show_welcome": getattr(self, "show_welcome", None),
            })

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
                    # ``view_left`` is currently unique to NotepadWindow.
                    # ``setattr`` keeps the call safe for any future
                    # class that has ``wrap_mode`` + ``_invalidate_wrap``
                    # but not ``view_left``.
                    setattr(win, 'view_left', 0)
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
            schema_version=getattr(
                self.config,
                "schema_version",
                CONFIG_SCHEMA_VERSION,
            ),
            theme=self.theme_name,
            show_hidden=self.default_show_hidden,
            word_wrap_default=self.default_word_wrap,
            sunday_first=self.default_sunday_first,
            show_welcome=self.show_welcome,
            icon_style=normalize_icon_style(getattr(self, "icon_style", ICON_STYLE_DEFAULT)),
            hidden_icons=getattr(self.config, 'hidden_icons', ""),
            hidden_menu_items=getattr(self.config, 'hidden_menu_items', ""),
        )
        # Bundle the icon positions into the same write so the file is
        # only persisted once per change (was two writes: one for the
        # ``[ui]`` block, one to splice in ``[icons]`` afterwards).
        try:
            icon_positions = dict(getattr(self._icon_mgr, "positions", {}) or {})
        except _CONFIG_PERSIST_ERRORS:
            icon_positions = None
        return save_config(self.config, icon_positions=icon_positions)

    def _load_icon_positions(self):
        from .config import default_config_path
        return self._icon_mgr.load(default_config_path())

    def _save_icon_positions(self, cfg_path=None):
        from .config import default_config_path
        path = cfg_path if cfg_path is not None else default_config_path()
        self._icon_mgr.save(path)

    # ------------------------------------------------------------------
    # Right-click handling
    # ------------------------------------------------------------------

    def handle_right_click(self, mx, my, bstate):
        """Dispatch right-clicks to windows or desktop. Return True if handled."""
        return _handle_right_click(self, mx, my, bstate)

    def _handle_desktop_right_click(self, mx, my, bstate):
        """Open a desktop context menu or icon-specific menu at (mx,my)."""
        return _handle_desktop_right_click(self, mx, my, bstate)

    def _show_icon_properties(self, icon):
        """Show a simple properties dialog for a desktop icon."""
        return _show_icon_properties(self, icon)

    def sort_desktop_icons(self):
        """Sort desktop icons alphabetically and persist the updated grid positions."""
        self._get_icon_mgr().sort_positions()
        self.selected_icon = -1
        return None

    # ------------------------------------------------------------------
    # Terminal validation & lifecycle
    # ------------------------------------------------------------------

    def _validate_terminal_size(self):
        """Fail fast when terminal is too small for the base desktop layout."""
        h, w = self.stdscr.getmaxyx()
        if h < self.MIN_TERM_HEIGHT or w < self.MIN_TERM_WIDTH:
            raise ValueError(
                f'Terminal too small ({w}x{h}). '
                f'Minimum supported size is {self.MIN_TERM_WIDTH}x{self.MIN_TERM_HEIGHT}.'
            )

    def _check_terminal_size_post_resize(self):
        """Re-check terminal size after SIGWINCH without raising.

        Returns True when the new size is too small for the base desktop.
        Callers can clamp their drawing to the validated size or surface a
        transient status message.
        """
        try:
            h, w = self.stdscr.getmaxyx()
        except (AttributeError, OSError, ValueError):
            return True
        return h < self.MIN_TERM_HEIGHT or w < self.MIN_TERM_WIDTH

    def cleanup(self):
        """Run one idempotent, ordered shutdown pass.

        Returns True when every side-effecting global worker and window cleanup
        hook confirmed completion. Terminal restoration still runs on failures.
        """
        if getattr(self, "_cleanup_complete", False):
            return getattr(self, "_cleanup_result", True)
        if getattr(self, "_cleanup_started", False):
            LOGGER.warning("Ignoring re-entrant RetroTUI cleanup request.")
            return False

        self._cleanup_started = True
        self.running = False
        success = True
        try:
            self._restore_runtime_signal_handlers()

            file_ops = getattr(self, "_file_ops", None)
            if file_ops is not None:
                stopped = file_ops.shutdown(
                    timeout=self.BACKGROUND_OPERATION_JOIN_TIMEOUT
                )
                if not stopped:
                    success = False
                    LOGGER.warning(
                        "File operation worker did not stop within %.1fs during shutdown.",
                        self.BACKGROUND_OPERATION_JOIN_TIMEOUT,
                    )
            else:
                # Compatibility for partially constructed app instances and
                # pre-WorkerScope background-operation state.
                op_state = getattr(self, "_background_operation", None)
                thread = op_state.get("thread") if isinstance(op_state, dict) else None
                if thread is not None and thread.is_alive():
                    thread.join(timeout=self.BACKGROUND_OPERATION_JOIN_TIMEOUT)
                    if thread.is_alive():
                        success = False
                        LOGGER.warning(
                            "Legacy background operation did not finish within %.1fs during shutdown.",
                            self.BACKGROUND_OPERATION_JOIN_TIMEOUT,
                        )

            for win in list(self.windows):
                if not self.window_mgr.close_window(win, force=True):
                    success = False
                    LOGGER.warning("Window cleanup was not verified for %r", win)

            self.dialog = None
            self.context_menu = None
            if hasattr(self, "_notifications"):
                self._notifications.cleanup()
            if hasattr(self, "_event_bus"):
                self._event_bus.clear()
        except Exception:
            success = False
            raise
        finally:
            self._cleanup_result = success
            disable_mouse_support()
            self._cleanup_complete = True
            self._cleanup_started = False
        return success

    # ------------------------------------------------------------------
    # Signal handling (delegates to signal_handler module)
    # ------------------------------------------------------------------

    def _install_runtime_signal_handlers(self):
        """Install runtime signal handlers (main thread only)."""
        install_runtime_signal_handlers(self)

    def _restore_runtime_signal_handlers(self):
        """Restore process signal handlers changed for runtime."""
        restore_runtime_signal_handlers(self)

    def _handle_sigint(self, _signum, _frame):
        """Queue SIGINT as in-app Ctrl+C key instead of terminating session."""
        queue_pending_signal_key(self, '\x03')

    def _handle_sigtstp(self, _signum, _frame):
        """Queue SIGTSTP as in-app Ctrl+Z key instead of suspending session."""
        queue_pending_signal_key(self, '\x1a')

    def _queue_pending_signal_key(self, key):
        """Queue one pending control key generated by runtime signal handlers."""
        queue_pending_signal_key(self, key)

    def _handle_shutdown_signal(self, signum, _frame):
        """Request a clean shutdown on external termination signals."""
        self._shutdown_signal = signum
        self.running = False

    def _consume_pending_signal_key(self):
        """Return next queued control key generated by signal handlers."""
        return consume_pending_signal_key(self)

    def _consume_pending_sigint(self):
        """Compatibility wrapper: return queued Ctrl+C key when available."""
        return consume_pending_sigint(self)

    # ------------------------------------------------------------------
    # Drawing (delegates to rendering module)
    # ------------------------------------------------------------------

    def draw_desktop(self, frame_size=None):
        """Draw the desktop background pattern."""
        return draw_desktop(self, frame_size=frame_size)

    def draw_icons(self, frame_size=None):
        """Draw desktop icons (3x4 art + label)."""
        return draw_icons(self, frame_size=frame_size)

    def draw_taskbar(self, frame_size=None):
        """Draw minimized window buttons on the shell bar."""
        return draw_taskbar(self, frame_size=frame_size)

    def draw_statusbar(self, frame_size=None):
        """Draw legacy bottom status content when configured."""
        return draw_statusbar(self, APP_VERSION, frame_size=frame_size)

    # ------------------------------------------------------------------
    # Icon position & window management
    # ------------------------------------------------------------------

    def get_icon_screen_pos(self, index, *, frame_size=None):
        """Return (x, y) for icon at index, checking persisted positions then default grid."""
        return self._icon_mgr.get_screen_pos(index, frame_size=frame_size)

    def get_icon_at(self, mx, my, *, frame_size=None):
        """Return icon index at mouse position, or -1."""
        return self._icon_mgr.get_icon_at(mx, my, frame_size=frame_size)

    def set_active_window(self, win):
        """Set a window as active (bring to front)."""
        self.window_mgr.set_active_window(win)

    def normalize_window_layers(self):
        """Keep always-on-top windows above regular windows preserving order."""
        self.window_mgr.normalize_window_layers()

    def close_window(self, win, *, force=False):
        """Request that a window close, or force it during shutdown."""
        return self.window_mgr.close_window(win, force=force)

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
        """Open *win* through the authoritative lifecycle manager."""
        return self.window_mgr._spawn_window(win)

    def _next_window_offset(self, base_x, base_y, step_x=2, step_y=1):
        """Return staggered window coordinates based on open window count."""
        return self.window_mgr._next_window_offset(base_x, base_y, step_x, step_y)

    # ------------------------------------------------------------------
    # Action execution
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # File viewers (delegates to viewer module)
    # ------------------------------------------------------------------

    def open_file_viewer(self, filepath):
        """Open file in the best available viewer."""
        from .viewer import open_file_viewer as _open_file_viewer
        _open_file_viewer(self, filepath)

    def _play_ascii_video(self, filepath, subtitle_path=None):
        """Run ASCII video playback and surface backend errors in a dialog."""
        from .viewer import play_ascii_video as _play_video
        _play_video(self, filepath, subtitle_path=subtitle_path)

    def show_url_dialog(self, source_win, default_url=None):
        """Show input dialog for web URLs."""
        _show_url_dialog(self, source_win, default_url=default_url)

    def show_bookmarks_window(self, source_win):
        """Open the RetroNet bookmarks window anchored to the source browser."""
        from ..apps.retronet import BookmarksWindow
        from ..ui.window import Window
        h, w = self.stdscr.getmaxyx()
        ox, oy = self._next_window_offset(20, 4)
        win: Window = BookmarksWindow(
            ox, oy,
            min(64, max(WIN_MIN_WIDTH, w - 4)),
            min(20, max(WIN_MIN_HEIGHT, h - 4)),
            source_win=source_win,
        )
        self._spawn_window(win)

    def show_add_bookmark_dialog(self, source_win):
        """Prompt for a title and add the source window's URL to bookmarks."""
        from ..ui.dialog import InputDialog
        from .actions import ActionResult, ActionType
        from .bookmarks import add_bookmark

        url = getattr(source_win, 'url', '') or ''
        title = url.split('//', 1)[-1].split('/', 1)[0] or url or "Bookmark"

        def _on_title(value):
            clean = (value or "").strip() or title
            add_bookmark(clean, url)
            return ActionResult(ActionType.REFRESH)

        self.dialog = InputDialog(
            'Add Bookmark',
            'Title for this URL:',
            initial_value=title,
            width=54,
        )
        self.dialog.callback = _on_title

    def show_video_open_dialog(self):
        """Open dialog flow to play a video path without using File Manager."""
        _show_video_open_dialog(self)

    def _handle_video_path_input(self, filepath):
        """Validate selected video path and request optional subtitle path."""
        from .viewer import handle_video_path_input as _handle_vpi
        return _handle_vpi(self, filepath)

    def _handle_subtitle_path_input(self, video_path, subtitle_path):
        """Validate optional subtitle path and start playback."""
        from .viewer import handle_subtitle_path_input as _handle_spi
        return _handle_spi(self, video_path, subtitle_path)

    # ------------------------------------------------------------------
    # Dialog & input routing
    # ------------------------------------------------------------------

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
        # ``click_flags`` also matches BUTTON1_PRESSED, so dragging the
        # mouse over a button would fire ``handle_click`` repeatedly on
        # motion-with-button-down. Restrict to genuine click-like events.
        if not _is_button1_click_event(bstate):
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
        """Handle click on taskbar buttons. Returns True if handled."""
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
