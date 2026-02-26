"""
Right-click context menu handling for desktop and windows.
"""

import logging

LOGGER = logging.getLogger(__name__)

_INPUT_ROUTE_ERRORS = (
    AttributeError,
    LookupError,
    OSError,
    TypeError,
    ValueError,
)


def handle_right_click(app, mx, my, bstate):
    """Dispatch right-clicks to windows or desktop. Return True if handled."""
    from .mouse_router import _invoke_mouse_handler

    # If a context menu is already open, let it consume the click first.
    if app.context_menu and app.context_menu.active:
        try:
            action = app.context_menu.handle_click(mx, my)
        except _INPUT_ROUTE_ERRORS:
            LOGGER.debug('context menu click handler failed', exc_info=True)
            action = None
        if action is not None:
            app.execute_action(action)
            return True
        is_open = getattr(app.context_menu, "is_open", None)
        if callable(is_open) and is_open():
            return True

    # Try windows first (topmost)
    for win in reversed(app.windows):
        if not getattr(win, 'visible', False):
            continue
        contains = getattr(win, 'contains', None)
        if not callable(contains) or not contains(mx, my):
            continue

        app.set_active_window(win)

        handler = getattr(win, 'handle_right_click', None)
        if callable(handler):
            try:
                res = _invoke_mouse_handler(handler, mx, my, bstate)
            except _INPUT_ROUTE_ERRORS:
                LOGGER.debug('window right-click handler failed', exc_info=True)
                res = None

            if isinstance(res, list):
                from ..ui.context_menu import ContextMenu
                app.context_menu = ContextMenu(app.theme)
                app.context_menu.show(mx, my, res)
                return True

            if res:
                app._dispatch_window_result(res, win)
                return True

    # Desktop hook
    try:
        return bool(app._handle_desktop_right_click(mx, my, bstate))
    except _INPUT_ROUTE_ERRORS:
        LOGGER.debug('desktop right-click handler failed', exc_info=True)
        return False


def handle_desktop_right_click(app, mx, my, bstate):
    """Open a desktop context menu or icon-specific menu at (mx,my)."""
    from .actions import AppAction

    icon_idx = app.get_icon_at(mx, my)

    if icon_idx >= 0:
        app.selected_icon = icon_idx
        icon = app.icons[icon_idx]
        items = [
            {'label': 'Open', 'action': icon.get('action')},
            {'separator': True},
            {'label': 'Properties', 'action': lambda selected_icon=icon: show_icon_properties(app, selected_icon)},
        ]
    else:
        items = [
            {'label': 'New Terminal', 'action': AppAction.TERMINAL},
            {'label': 'New Notepad', 'action': AppAction.NOTEPAD},
            {'separator': True},
            {'label': 'Desktop Icons', 'action': AppAction.DESKTOP_ICON_MANAGER},
            {'label': 'Icons', 'action': AppAction.ICONS},
            {'label': 'Menu Editor', 'action': AppAction.MENU_EDITOR},
            {'label': 'Sort Icons (A-Z)', 'action': app.sort_desktop_icons},
            {'separator': True},
            {'label': 'Settings', 'action': AppAction.SETTINGS},
            {'separator': True},
            {'label': 'About', 'action': AppAction.ABOUT},
            {'label': 'Exit', 'action': AppAction.EXIT},
        ]

    from ..ui.context_menu import ContextMenu
    app.context_menu = ContextMenu(app.theme)
    app.context_menu.show(mx, my, items)
    return True


def show_icon_properties(app, icon):
    """Show a simple properties dialog for a desktop icon."""
    from .app import APP_VERSION

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
    from ..ui.dialog import Dialog
    app.dialog = Dialog(f'{label} Properties', message, ['OK'], width=54)
    return None
