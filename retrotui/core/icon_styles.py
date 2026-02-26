"""
Desktop icon styling, catalog building, and visibility filtering.
"""

from ..constants import ICONS, ICONS_ASCII
from .actions import AppAction

ICON_STYLE_DEFAULT = "default"
ICON_STYLE_MINI = "mini"
ICON_STYLE_BRAILLE = "braille"
ICON_STYLE_CODEX = "codex"
ICON_STYLE_RETRO_01 = "retro_01"  # Legacy alias kept for backwards compatibility.


def split_config_csv(raw):
    """Return lowercased non-empty comma-separated tokens from *raw* string."""
    if not isinstance(raw, str):
        return set()
    return {token.strip().lower() for token in raw.split(",") if token.strip()}


def normalize_icon_style(style):
    """Return supported icon style key."""
    normalized = str(style or ICON_STYLE_DEFAULT).strip().lower()
    if normalized == ICON_STYLE_RETRO_01:
        return ICON_STYLE_MINI
    if normalized in (ICON_STYLE_DEFAULT, ICON_STYLE_MINI, ICON_STYLE_BRAILLE, ICON_STYLE_CODEX):
        return normalized
    return ICON_STYLE_DEFAULT


def icon_style_variants():
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


def style_symbol_for_icon(icon, style):
    """Return style-specific symbol token for one icon."""
    action = icon.get("action")
    key = getattr(action, "value", action)
    key = str(key or "").lower()
    by_icon = icon_style_variants().get(key, {})

    if key.startswith("plugin:"):
        if style == ICON_STYLE_MINI:
            return ":)"
        if style == ICON_STYLE_BRAILLE:
            return "⠏⠇"
        if style == ICON_STYLE_CODEX:
            return "⟠PL"
        return None

    return by_icon.get(style)


def styled_icon_entry(icon, style, use_unicode):
    """Return style-adjusted icon entry for current desktop icon style."""
    style = normalize_icon_style(style)
    if style == ICON_STYLE_DEFAULT:
        # Default style is the classic 3-line grid icon set.
        styled = dict(icon)
        styled.pop("symbol", None)
        return styled

    styled = dict(icon)
    symbol = style_symbol_for_icon(styled, style)
    if symbol:
        styled["symbol"] = symbol
        token = symbol[:2].ljust(2)
        if use_unicode and style in (ICON_STYLE_MINI, ICON_STYLE_CODEX):
            styled["art"] = ["╭──╮", f"│{token}│", "╰──╯"]
        elif use_unicode and style == ICON_STYLE_BRAILLE:
            styled["art"] = ["┌──┐", f"│{token}│", "└──┘"]
        else:
            styled["art"] = ["+--+", f"|{token}|", "+--+"]
    return styled


def icon_style_preview_symbol(style, icon_key, use_unicode):
    """Return one preview symbol token for *style* and *icon_key*."""
    normalized = normalize_icon_style(style)
    if normalized == ICON_STYLE_DEFAULT:
        base_icons = ICONS if use_unicode else ICONS_ASCII
        target_key = str(icon_key or "").lower()
        for icon in base_icons:
            action = icon.get("action")
            action_key = getattr(action, "value", action)
            if str(action_key or "").lower() != target_key:
                continue
            art = icon.get("art") or []
            if len(art) >= 2 and isinstance(art[1], str):
                mid = art[1].strip("| ").strip()
                if mid:
                    return mid
            symbol = icon.get("symbol")
            if isinstance(symbol, str) and symbol:
                return symbol
        return "[]"
    probe_icon = {"action": icon_key}
    return style_symbol_for_icon(probe_icon, normalized) or "[]"


def icon_visibility_key(icon):
    """Return stable visibility key for one desktop icon entry."""
    hide_key = icon.get("hide_key")
    if isinstance(hide_key, str) and hide_key.strip():
        return hide_key.strip().lower()
    return str(icon.get("label", "")).strip().lower()


def get_hidden_icon_labels(config):
    """Return set of lowercased hidden desktop icon keys from config."""
    raw = getattr(config, 'hidden_icons', "")
    return split_config_csv(raw)


def plugin_icon_art(name, use_unicode):
    """Build compact 3x4 icon art for plugin desktop entries."""
    token = ''.join(ch for ch in str(name) if ch.isalnum())[:2].upper()
    if not token:
        token = "PL"
    if len(token) == 1:
        token += " "
    if use_unicode:
        return ["┌──┐", f"│{token}│", "└──┘"]
    return ["+--+", f"|{token}|", "+--+"]


def build_plugin_icons(plugins, use_unicode):
    """Return plugin entries as desktop icons."""
    icons = []
    for plugin_id, info in (plugins or {}).items():
        plugin_info = (info.get("manifest", {}) or {}).get("plugin", {}) or {}
        name = str(plugin_info.get("name") or plugin_id)
        icons.append(
            {
                "label": name,
                "action": f"plugin:{plugin_id}",
                "art": plugin_icon_art(name, use_unicode),
                "category": "Plugins",
                "hide_key": f"plugin:{plugin_id}",
            }
        )
    icons.sort(key=lambda item: (item.get("label", "").lower(), item.get("action", "")))
    return icons


def build_desktop_icon_catalog(plugins, use_unicode):
    """Return full desktop icon catalog (apps, games, plugins)."""
    base_icons = ICONS if use_unicode else ICONS_ASCII
    catalog = [dict(icon) for icon in base_icons]
    catalog.extend(build_plugin_icons(plugins, use_unicode))
    return catalog


def refresh_icons(app):
    """Rebuild desktop icons list based on config and unicode support."""
    hidden_keys = get_hidden_icon_labels(app.config)
    catalog = build_desktop_icon_catalog(
        getattr(app, "_plugins", None),
        app.use_unicode,
    )
    visible = [icon for icon in catalog if icon_visibility_key(icon) not in hidden_keys]
    app.icons = [
        styled_icon_entry(icon, getattr(app, "icon_style", ICON_STYLE_DEFAULT), app.use_unicode)
        for icon in visible
    ]
