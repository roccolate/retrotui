"""
Desktop icon styling, catalog building, and visibility filtering.
"""

import functools

from ..constants import ICONS, ICONS_ASCII
from .actions import AppAction

ICON_STYLE_DEFAULT = "default"
ICON_STYLE_MINI = "mini"
ICON_STYLE_BRAILLE = "braille"
ICON_STYLE_RETRO_01 = "retro_01"  # Legacy alias kept for backwards compatibility.


# ---------------------------------------------------------------------------
# Braille pixel art helpers
# ---------------------------------------------------------------------------

def _grid_to_braille(text):
    """Convert an 8-wide x 12-tall pixel grid to 4x3 braille characters.

    ``#`` = filled dot, any other character = empty.  The grid is supplied as
    a multi-line string (12 lines of up to 8 characters each).
    """
    lines = text.strip().splitlines()
    while len(lines) < 12:
        lines.append("")
    pixels = []
    for line in lines[:12]:
        pixels.append([(1 if i < len(line) and line[i] == "#" else 0) for i in range(8)])
    result = []
    for br in range(3):
        row = ""
        for bc in range(4):
            val = 0
            r, c = br * 4, bc * 2
            if pixels[r][c]:       val |= 0x01
            if pixels[r + 1][c]:   val |= 0x02
            if pixels[r + 2][c]:   val |= 0x04
            if pixels[r][c + 1]:   val |= 0x08
            if pixels[r + 1][c + 1]: val |= 0x10
            if pixels[r + 2][c + 1]: val |= 0x20
            if pixels[r + 3][c]:   val |= 0x40
            if pixels[r + 3][c + 1]: val |= 0x80
            row += chr(0x2800 + val)
        result.append(row)
    return result


# 8x12 pixel grids for braille icon art.  Each grid is keyed by either an
# AppAction value (built-in apps) or "plugin:<id>" (example plugins).
_BRAILLE_GRIDS = {
    # -- Built-in apps --------------------------------------------------
    "filemanager": """\
.####...
########
########
########
########
########
########
########
########
.######.
........
........""",
    "notepad": """\
.######.
.######.
.#..#.#.
.######.
.#..#.#.
.######.
.#..#.#.
.######.
.######.
........
........
........""",
    "asciivideo": """\
..#.....
.##.....
####..##
#####.##
####..##
.##.....
..#.....
........
........
........
........
........""",
    "terminal": """\
########
#......#
#.#....#
#..#...#
#.#.##.#
#......#
#......#
#......#
########
........
........
........""",
    "calculator": """\
########
#.####.#
#.####.#
#......#
#.#..#.#
#.#..#.#
#......#
#.#..#.#
########
........
........
........""",
    "log_viewer": """\
.######.
.######.
.##..##.
.######.
.##..##.
.######.
.##..##.
.######.
.######.
...##...
...##...
........""",
    "process_manager": """\
########
#......#
#.#.##.#
#.#.##.#
#.####.#
#.####.#
#.####.#
#......#
########
........
........
........""",
    "trash_bin": """\
.######.
########
.######.
.######.
.#.##.#.
.#.##.#.
.#.##.#.
.######.
..####..
........
........
........""",
    "settings": """\
..#..#..
.######.
########
###..###
###..###
########
.######.
..#..#..
........
........
........
........""",
    "about": """\
..####..
.######.
.##..##.
..####..
...##...
...##...
...##...
..####..
........
........
........
........""",
    "clipboard": """\
..####..
########
##....##
##.##.##
##....##
##.##.##
##....##
########
........
........
........
........""",
    "hex_viewer": """\
.##..##.
#..#.#.#
#..#..#.
#..#.#..
#..#.#.#
.##..##.
........
........
........
........
........
........""",
    "desktop_icon_manager": """\
##..##..
##..##..
........
##..##..
##..##..
........
##..##..
##..##..
........
........
........
........""",
    "icons": """\
...##...
..####..
.######.
########
.######.
..####..
...##...
........
........
........
........
........""",
    "menu_editor": """\
########
........
.######.
........
.####...
........
.######.
........
########
........
........
........""",
    "markdown_viewer": """\
.######.
.##..##.
.#.##.#.
.#....#.
.######.
.#..#.#.
.######.
.######.
.######.
........
........
........""",
    "system_monitor": """\
......#.
......##
....#.##
....####
..#.####
..######
########
########
........
........
........
........""",
    "control_panel": """\
########
#......#
#.####.#
#......#
#..###.#
#......#
#.####.#
#......#
########
........
........
........""",
    # -- Example plugins ------------------------------------------------
    "plugin:ascii-aquarium": """\
........
..#.....
.###.##.
########
.###.##.
..#.....
........
........
........
........
........
........""",
    "plugin:contacts": """\
...##...
..####..
...##...
..####..
.######.
########
.######.
..####..
........
........
........
........""",
    "plugin:cron-editor": """\
.######.
##....##
#.#...##
#..#..##
#..##.##
#.....##
##....##
.######.
........
........
........
........""",
    "plugin:db-browser": """\
.######.
########
.######.
.######.
########
.######.
.######.
########
.######.
........
........
........""",
    "plugin:disk-usage": """\
..####..
.######.
####..##
####..##
######.#
.######.
..####..
........
........
........
........
........""",
    "plugin:docker-manager": """\
#.#.#.#.
########
########
########
########
########
.######.
........
........
........
........
........""",
    "plugin:fortune-cookie": """\
..####..
.######.
.#####..
..###...
..##.#..
.##..##.
........
........
........
........
........
........""",
    "plugin:game-of-life": """\
........
.##.....
.##.##..
....##..
.....##.
##...##.
##......
........
........
........
........
........""",
    "plugin:git-status": """\
....##..
....##..
.#..##..
.##.##..
..####..
...##...
...##...
...##...
........
........
........
........""",
    "plugin:json-viewer": """\
..##....
.##.....
.##.....
##......
.##.....
.##.....
..##....
........
........
........
........
........""",
    "plugin:matrix-rain": """\
.#..#..#
.#.##..#
.#.##.##
##.##.##
##.##.##
##..#.##
##..#.#.
.#..#.#.
........
........
........
........""",
    "plugin:network-monitor": """\
.##..##.
.##..##.
..####..
...##...
..####..
.##..##.
.##..##.
........
........
........
........
........""",
    "plugin:pomodoro": """\
..####..
.######.
##.##.##
##.##.##
##..#.##
##....##
.######.
..####..
........
........
........
........""",
    "plugin:qa-runner": """\
........
......#.
.....##.
....##..
#..##...
.####...
..##....
........
........
........
........
........""",
    "plugin:rss-reader": """\
........
...####.
.#.##...
.###....
.##.....
.##.....
........
........
........
........
........
........""",
    "plugin:service-manager": """\
##...##.
.##.##..
..###...
...##...
..###...
.##.##..
##...##.
........
........
........
........
........""",
    "plugin:starwars-ascii": """\
...##...
...##...
########
.######.
..####..
.##..##.
##....##
........
........
........
........
........""",
    "plugin:sticky-notes": """\
########
########
##....##
##....##
##....##
########
########
........
........
........
........
........""",
    "plugin:system-monitor": """\
......#.
......##
....#.##
....####
..#.####
..######
########
########
........
........
........
........""",
    "plugin:todo-list": """\
.#.#####
##.#####
.#......
.#.#####
##.#####
.#......
.#.#####
##.#####
........
........
........
........""",
    "plugin:weather-widget": """\
......##
..###.##
.######.
########
########
.######.
........
........
........
........
........
........""",
}

_BRAILLE_ART = {k: _grid_to_braille(v) for k, v in _BRAILLE_GRIDS.items()}


def braille_art_for_action(action_key):
    """Return 3-line braille pixel art for *action_key*, or None."""
    return _BRAILLE_ART.get(str(action_key or "").lower())


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

@functools.lru_cache(maxsize=32)
def _split_config_csv_cached(raw):
    """Cached variant of :func:`split_config_csv` keyed on the raw string.

    The same raw CSV (e.g. ``"files,calc"``) is parsed many times per
    session — every right-click rebuilds the context menu, every menu
    build re-reads the hidden-list. The result is invalidated
    implicitly when the raw string changes (``functools.lru_cache`` keys
    on the string value, not on the config instance), so editing the
    preferences through the Settings window produces a fresh parse.
    """
    return split_config_csv(raw)


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
    if normalized in (ICON_STYLE_DEFAULT, ICON_STYLE_MINI, ICON_STYLE_BRAILLE):
        return normalized
    return ICON_STYLE_DEFAULT


# Cached at module import; the variants table is static so it should not
# be rebuilt on every ``icon_style_variants()`` call (which the icon
# preview panel and ``style_symbol_for_icon`` invoke per row).
_ICON_STYLE_VARIANTS = None


def icon_style_variants():
    """Return per-icon style variants keyed by action/value key."""
    global _ICON_STYLE_VARIANTS
    if _ICON_STYLE_VARIANTS is None:
        _ICON_STYLE_VARIANTS = {
            AppAction.FILE_MANAGER.value: {"mini": ":D"},
            AppAction.NOTEPAD.value: {"mini": ":|"},
            AppAction.ASCII_VIDEO.value: {"mini": "AV"},
            AppAction.TERMINAL.value: {"mini": ">:"},
            AppAction.CALCULATOR.value: {"mini": "+)"},
            AppAction.LOG_VIEWER.value: {"mini": "LG"},
            AppAction.PROCESS_MANAGER.value: {"mini": "PS"},
            AppAction.TRASH_BIN.value: {"mini": "TR"},
            AppAction.SETTINGS.value: {"mini": "8)"},
            AppAction.ABOUT.value: {"mini": "i)"},
            AppAction.CLIPBOARD.value: {"mini": "CB"},
            AppAction.HEX_VIEWER.value: {"mini": "0x"},
            AppAction.DESKTOP_ICON_MANAGER.value: {"mini": "DT"},
            AppAction.ICONS.value: {"mini": ":)"},
            AppAction.MENU_EDITOR.value: {"mini": "MN"},
            AppAction.MARKDOWN_VIEWER.value: {"mini": "MD"},
            AppAction.SYSTEM_MONITOR.value: {"mini": "SM"},
            AppAction.CONTROL_PANEL.value: {"mini": "CT"},
        }
    return _ICON_STYLE_VARIANTS


def style_symbol_for_icon(icon, style):
    """Return style-specific symbol token for one icon."""
    if style == ICON_STYLE_BRAILLE:
        return None  # Braille uses pixel art, not symbols.
    action = icon.get("action")
    key = getattr(action, "value", action)
    key = str(key or "").lower()
    by_icon = icon_style_variants().get(key, {})

    if key.startswith("plugin:"):
        token = icon.get("_token", "")
        if style == ICON_STYLE_MINI:
            return token if token else ":)"
        return None

    return by_icon.get(style)


def styled_icon_entry(icon, style, use_unicode):
    """Return style-adjusted icon entry for current desktop icon style."""
    style = normalize_icon_style(style)
    if style == ICON_STYLE_DEFAULT:
        styled = dict(icon)
        styled.pop("symbol", None)
        return styled

    # Braille pixel art — use pre-computed 3-line art directly.
    if style == ICON_STYLE_BRAILLE:
        styled = dict(icon)
        action = icon.get("action")
        key = getattr(action, "value", action)
        key = str(key or "").lower()
        art = braille_art_for_action(key)
        if art:
            styled["art"] = list(art)
            styled.pop("symbol", None)
        return styled

    # Mini style — symbol inside a box.
    styled = dict(icon)
    symbol = style_symbol_for_icon(styled, style)
    if symbol:
        styled["symbol"] = symbol
        token = symbol[:2].ljust(2)
        if use_unicode:
            styled["art"] = ["╭──╮", f"│{token}│", "╰──╯"]
        else:
            styled["art"] = ["+--+", f"|{token}|", "+--+"]
    return styled


_PREVIEW_SYMBOL_CACHE = {}


def _preview_symbol_lookup(use_unicode):
    """Return a ``{action_key: token}`` dict for fast preview lookups."""
    cache_key = bool(use_unicode)
    cached = _PREVIEW_SYMBOL_CACHE.get(cache_key)
    if cached is not None:
        return cached
    base_icons = ICONS if use_unicode else ICONS_ASCII
    lookup = {}
    for icon in base_icons:
        action = icon.get("action")
        action_key = getattr(action, "value", action)
        if action_key in lookup:
            continue
        token = None
        art = icon.get("art") or []
        if len(art) >= 2 and isinstance(art[1], str):
            mid = art[1].strip("| ").strip()
            if mid:
                token = mid
        if token is None:
            symbol = icon.get("symbol")
            if isinstance(symbol, str) and symbol:
                token = symbol
        if token is not None:
            lookup[str(action_key or "").lower()] = token
    _PREVIEW_SYMBOL_CACHE[cache_key] = lookup
    return lookup


def icon_style_preview_symbol(style, icon_key, use_unicode):
    """Return one preview symbol token for *style* and *icon_key*."""
    normalized = normalize_icon_style(style)
    if normalized == ICON_STYLE_DEFAULT:
        target_key = str(icon_key or "").lower()
        return _preview_symbol_lookup(use_unicode).get(target_key, "[]")
    if normalized == ICON_STYLE_BRAILLE:
        art = braille_art_for_action(icon_key)
        if art and len(art) >= 2:
            return art[1]
        return "⣿⣿"
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
    return _split_config_csv_cached(raw)


def is_icon_key_hidden(icon_key, hidden_keys):
    """Return True when an icon key is explicitly or wildcard-hidden."""
    key = str(icon_key or "").strip().lower()
    if key in hidden_keys:
        return True
    return key.startswith("plugin:") and "plugin:*" in hidden_keys


def plugin_icon_art(name, use_unicode, token=None):
    """Build compact 3x4 icon art for plugin desktop entries."""
    if not token:
        token = ''.join(ch for ch in str(name) if ch.isalnum())[:2].upper()
    if not token:
        token = "PL"
    if len(token) == 1:
        token += " "
    token = token[:2]
    if use_unicode:
        return ["┌──┐", f"│{token}│", "└──┘"]
    return ["+--+", f"|{token}|", "+--+"]


def build_plugin_icons(plugins, use_unicode):
    """Return plugin entries as desktop icons."""
    icons = []
    for plugin_id, info in (plugins or {}).items():
        plugin_info = (info.get("manifest", {}) or {}).get("plugin", {}) or {}
        name = str(plugin_info.get("name") or plugin_id)
        icon_section = plugin_info.get("icon") or {}
        # Support both [plugin.icon] table and legacy flat icon = "emoji" string.
        if isinstance(icon_section, str):
            emoji = icon_section
            token = None
        else:
            emoji = icon_section.get("emoji") or plugin_info.get("icon_legacy")
            token = icon_section.get("token")
        entry = {
            "label": name,
            "action": f"plugin:{plugin_id}",
            "art": plugin_icon_art(name, use_unicode, token=token),
            "category": "Plugins",
            "hide_key": f"plugin:{plugin_id}",
        }
        if isinstance(emoji, str) and emoji.strip():
            entry["symbol"] = emoji.strip()
        if isinstance(token, str) and token.strip():
            entry["_token"] = token.strip()[:2].upper()
        icons.append(entry)
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
    visible = [icon for icon in catalog if not is_icon_key_hidden(icon_visibility_key(icon), hidden_keys)]
    app.icons = [
        styled_icon_entry(icon, getattr(app, "icon_style", ICON_STYLE_DEFAULT), app.use_unicode)
        for icon in visible
    ]
