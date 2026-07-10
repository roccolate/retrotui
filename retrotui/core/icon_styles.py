"""
Desktop icon styling, catalog building, and visibility filtering.
"""

import functools

from ..constants import ICONS, ICONS_ASCII
from .actions import AppAction

ICON_STYLE_DEFAULT = "default"
ICON_STYLE_WIN31_ART = "win31_art"
ICON_STYLE_RETRO_01 = "retro_01"

# Deprecated style keys kept as input aliases so old configs do not break.
ICON_STYLE_MINI = "mini"
ICON_STYLE_BRAILLE = "braille"


# ---------------------------------------------------------------------------
# Win31 Art — compact 3-line per-app icon art
# ---------------------------------------------------------------------------

_WIN31_ART_UNICODE = {
    AppAction.FILE_MANAGER.value: ["┌──┐", "│▒▒│", "└──┘"],
    AppAction.NOTEPAD.value: ["╔══╗", "║≡≡║", "╚══╝"],
    AppAction.ASCII_VIDEO.value: ["╭──╮", "│▶ │", "╰──╯"],
    AppAction.TERMINAL.value: ["┌──┐", "│>_│", "└──┘"],
    AppAction.CALCULATOR.value: ["╭──╮", "│+=│", "╰──╯"],
    AppAction.LOG_VIEWER.value: ["╔══╗", "║≣!║", "╚══╝"],
    AppAction.PROCESS_MANAGER.value: ["╭──╮", "│▓▓│", "╰──╯"],
    AppAction.TRASH_BIN.value: ["╭──╮", "│╳ │", "╰──╯"],
    AppAction.SETTINGS.value: ["╭──╮", "│⚙ │", "╰──╯"],
    AppAction.ABOUT.value: ["╭──╮", "│ ?│", "╰──╯"],
    AppAction.CLIPBOARD.value: ["┌──┐", "│▣ │", "└──┘"],
    AppAction.HEX_VIEWER.value: ["┌──┐", "│0x│", "└──┘"],
    AppAction.DESKTOP_ICON_MANAGER.value: ["╭──╮", "│▦ │", "╰──╯"],
    AppAction.ICONS.value: ["╭──╮", "│◇ │", "╰──╯"],
    AppAction.MENU_EDITOR.value: ["╔══╗", "║☰ ║", "╚══╝"],
    AppAction.MARKDOWN_VIEWER.value: ["╭──╮", "│M↓│", "╰──╯"],
    AppAction.SYSTEM_MONITOR.value: ["╭──╮", "│▁▇│", "╰──╯"],
    AppAction.CONTROL_PANEL.value: ["╔══╗", "║▣ ║", "╚══╝"],
}

_WIN31_ART_ASCII = {
    AppAction.FILE_MANAGER.value: ["+--+", "|##|", "+--+"],
    AppAction.NOTEPAD.value: ["+==+", "|==|", "+==+"],
    AppAction.ASCII_VIDEO.value: ["+--+", "|> |", "+--+"],
    AppAction.TERMINAL.value: ["+--+", "|>_|", "+--+"],
    AppAction.CALCULATOR.value: ["+--+", "|+=|", "+--+"],
    AppAction.LOG_VIEWER.value: ["+==+", "|=!|", "+==+"],
    AppAction.PROCESS_MANAGER.value: ["+--+", "|##|", "+--+"],
    AppAction.TRASH_BIN.value: ["+--+", "|X |", "+--+"],
    AppAction.SETTINGS.value: ["+--+", "|**|", "+--+"],
    AppAction.ABOUT.value: ["+--+", "| ?|", "+--+"],
    AppAction.CLIPBOARD.value: ["+--+", "|[]|", "+--+"],
    AppAction.HEX_VIEWER.value: ["+--+", "|0x|", "+--+"],
    AppAction.DESKTOP_ICON_MANAGER.value: ["+--+", "|[]|", "+--+"],
    AppAction.ICONS.value: ["+--+", "|<>|", "+--+"],
    AppAction.MENU_EDITOR.value: ["+==+", "|# |", "+==+"],
    AppAction.MARKDOWN_VIEWER.value: ["+--+", "|MD|", "+--+"],
    AppAction.SYSTEM_MONITOR.value: ["+--+", "|/_|", "+--+"],
    AppAction.CONTROL_PANEL.value: ["+==+", "|[]|", "+==+"],
}


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
    """Return supported icon style key.

    User-facing styles are intentionally small:
    - default: current clean letter boxes
    - win31_art: the expressive 3-line v0.2.2-style icons
    - retro_01: tiny mini boxes for very small screens

    Historical ``mini`` maps to ``retro_01``. Historical ``braille`` and
    ``codex`` fall back to the stable default style.
    """
    normalized = str(style or ICON_STYLE_DEFAULT).strip().lower()
    if normalized in (ICON_STYLE_RETRO_01, ICON_STYLE_MINI, "retro01", "retro-01"):
        return ICON_STYLE_RETRO_01
    if normalized in (ICON_STYLE_WIN31_ART, "win31", "win31-art", "classic_art"):
        return ICON_STYLE_WIN31_ART
    if normalized in (ICON_STYLE_DEFAULT, "classic"):
        return ICON_STYLE_DEFAULT
    return ICON_STYLE_DEFAULT


# Cached at module import; the variants table is static so it should not
# be rebuilt on every ``icon_style_variants()`` call (which the icon
# preview panel and ``style_symbol_for_icon`` invoke per row).
_ICON_STYLE_VARIANTS = None


def icon_style_variants():
    """Return per-icon retro_01 variants keyed by action/value key."""
    global _ICON_STYLE_VARIANTS
    if _ICON_STYLE_VARIANTS is None:
        _ICON_STYLE_VARIANTS = {
            AppAction.FILE_MANAGER.value: {ICON_STYLE_RETRO_01: ":D"},
            AppAction.NOTEPAD.value: {ICON_STYLE_RETRO_01: ":|"},
            AppAction.ASCII_VIDEO.value: {ICON_STYLE_RETRO_01: "AV"},
            AppAction.TERMINAL.value: {ICON_STYLE_RETRO_01: ">:"},
            AppAction.CALCULATOR.value: {ICON_STYLE_RETRO_01: "+)"},
            AppAction.LOG_VIEWER.value: {ICON_STYLE_RETRO_01: "LG"},
            AppAction.PROCESS_MANAGER.value: {ICON_STYLE_RETRO_01: "PS"},
            AppAction.TRASH_BIN.value: {ICON_STYLE_RETRO_01: "TR"},
            AppAction.SETTINGS.value: {ICON_STYLE_RETRO_01: "8)"},
            AppAction.ABOUT.value: {ICON_STYLE_RETRO_01: "i)"},
            AppAction.CLIPBOARD.value: {ICON_STYLE_RETRO_01: "CB"},
            AppAction.HEX_VIEWER.value: {ICON_STYLE_RETRO_01: "0x"},
            AppAction.DESKTOP_ICON_MANAGER.value: {ICON_STYLE_RETRO_01: "DT"},
            AppAction.ICONS.value: {ICON_STYLE_RETRO_01: ":)"},
            AppAction.MENU_EDITOR.value: {ICON_STYLE_RETRO_01: "MN"},
            AppAction.MARKDOWN_VIEWER.value: {ICON_STYLE_RETRO_01: "MD"},
            AppAction.SYSTEM_MONITOR.value: {ICON_STYLE_RETRO_01: "SM"},
            AppAction.CONTROL_PANEL.value: {ICON_STYLE_RETRO_01: "CT"},
        }
    return _ICON_STYLE_VARIANTS


def _action_key(action):
    key = getattr(action, "value", action)
    return str(key or "").lower()


def style_symbol_for_icon(icon, style):
    """Return style-specific symbol token for one icon."""
    style = normalize_icon_style(style)
    action = icon.get("action")
    key = _action_key(action)
    by_icon = icon_style_variants().get(key, {})

    if key.startswith("plugin:"):
        token = icon.get("_token", "")
        if style == ICON_STYLE_RETRO_01:
            return token if token else ":)"
        return None

    return by_icon.get(style)


def _win31_art_for_icon(icon, use_unicode):
    action = icon.get("action")
    key = _action_key(action)
    if key.startswith("plugin:"):
        token = icon.get("_token", "")
        label = icon.get("label", "")
        return plugin_icon_art(label, use_unicode, token=token)
    table = _WIN31_ART_UNICODE if use_unicode else _WIN31_ART_ASCII
    return table.get(key)


def styled_icon_entry(icon, style, use_unicode):
    """Return style-adjusted icon entry for current desktop icon style."""
    style = normalize_icon_style(style)
    if style == ICON_STYLE_DEFAULT:
        styled = dict(icon)
        styled.pop("symbol", None)
        return styled

    if style == ICON_STYLE_WIN31_ART:
        styled = dict(icon)
        art = _win31_art_for_icon(styled, use_unicode)
        if art:
            styled["art"] = list(art)
            styled.pop("symbol", None)
        return styled

    # Retro 0.1 style — tiny symbol inside a rounded box for small screens.
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
            mid = art[1].strip("| ║│").strip()
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


def _middle_token_from_art(art):
    if art and len(art) >= 2 and isinstance(art[1], str):
        return art[1].strip("| ║│").strip() or art[1]
    return "[]"


def icon_style_preview_symbol(style, icon_key, use_unicode):
    """Return one preview symbol token for *style* and *icon_key*."""
    normalized = normalize_icon_style(style)
    target_key = str(icon_key or "").lower()
    if normalized == ICON_STYLE_DEFAULT:
        return _preview_symbol_lookup(use_unicode).get(target_key, "[]")
    if normalized == ICON_STYLE_WIN31_ART:
        probe = {"action": target_key, "label": target_key}
        return _middle_token_from_art(_win31_art_for_icon(probe, use_unicode))
    probe_icon = {"action": target_key}
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
