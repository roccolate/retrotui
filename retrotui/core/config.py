"""Persistent config loader/saver for RetroTUI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..theme import DEFAULT_THEME, THEMES
from .actions import AppAction

try:  # Python 3.11+
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover - exercised on Python <3.11
    tomllib = None

if tomllib is not None:
    _TOML_PARSE_ERRORS = (
        getattr(tomllib, "TOMLDecodeError", ValueError),
        TypeError,
        ValueError,
    )
else:
    _TOML_PARSE_ERRORS = (TypeError, ValueError)


PLUGIN_VISIBILITY_WILDCARD = "plugin:*"
DEFAULT_HIDDEN_MENU_ITEMS = ",".join(
    sorted(
        {
            AppAction.NEW_WINDOW.value,
            AppAction.ASCII_VIDEO.value,
            AppAction.CALCULATOR.value,
            AppAction.CLIPBOARD.value,
            AppAction.PROCESS_MANAGER.value,
            AppAction.LOG_VIEWER.value,
            AppAction.MARKDOWN_VIEWER.value,
            AppAction.SYSTEM_MONITOR.value,
            AppAction.TRASH_BIN.value,
            AppAction.CONTROL_PANEL.value,
            AppAction.SETTINGS.value,
            AppAction.DESKTOP_ICON_MANAGER.value,
            AppAction.ICONS.value,
            AppAction.MENU_EDITOR.value,
            AppAction.ABOUT.value,
            AppAction.HELP.value,
            PLUGIN_VISIBILITY_WILDCARD,
        }
    )
)
DEFAULT_HIDDEN_ICONS = ",".join(
    sorted(
        {
            "ascii vid",
            "calc",
            "logs",
            "procs",
            "trash",
            "settings",
            "about",
            "clip",
            "hex",
            "desktop",
            "icons_app",
            "menus",
            "mdview",
            "sysmon",
            "control",
            PLUGIN_VISIBILITY_WILDCARD,
        }
    )
)


@dataclass(frozen=True)
class AppConfig:
    """Persistent user-facing configuration."""

    theme: str = DEFAULT_THEME
    show_hidden: bool = False
    word_wrap_default: bool = False
    sunday_first: bool = False
    show_welcome: bool = True
    icon_style: str = "default"
    hidden_icons: str = DEFAULT_HIDDEN_ICONS
    hidden_menu_items: str = DEFAULT_HIDDEN_MENU_ITEMS


def default_config_path() -> Path:
    """Return default config path (~/.config/retrotui/config.toml)."""
    return Path.home() / ".config" / "retrotui" / "config.toml"


def _coerce_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lower = value.strip().lower()
        if lower in ("1", "true", "yes", "on"):
            return True
        if lower in ("0", "false", "no", "off"):
            return False
    return default


def _parse_scalar(token):
    token = token.strip()
    if not token:
        return ""
    if token.startswith('"') and token.endswith('"') and len(token) >= 2:
        return token[1:-1]
    lower = token.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    try:
        return int(token)
    except ValueError:
        return token


def _fallback_parse_toml(text: str) -> dict:
    """Minimal parser for simple key/value TOML used by RetroTUI config."""
    data = {}
    section = None
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            if section:
                data.setdefault(section, {})
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        parsed = _parse_scalar(value)
        if section:
            data.setdefault(section, {})[key] = parsed
        else:
            data[key] = parsed
    return data


def _parse_toml(text: str) -> dict:
    if tomllib is not None:
        try:
            return tomllib.loads(text)
        except _TOML_PARSE_ERRORS:
            return _fallback_parse_toml(text)
    return _fallback_parse_toml(text)


def _normalize_config(raw: dict) -> AppConfig:
    ui = raw.get("ui", raw)
    if not isinstance(ui, dict):
        ui = {}

    theme = str(ui.get("theme", DEFAULT_THEME)).strip().lower() or DEFAULT_THEME
    if theme not in THEMES:
        theme = DEFAULT_THEME

    show_hidden = _coerce_bool(ui.get("show_hidden"), default=False)
    word_wrap_default = _coerce_bool(ui.get("word_wrap_default"), default=False)
    sunday_first = _coerce_bool(ui.get("sunday_first"), default=False)
    show_welcome = _coerce_bool(ui.get("show_welcome"), default=True)
    icon_style = str(ui.get("icon_style", "default")).strip().lower() or "default"
    if icon_style == "retro_01":
        icon_style = "mini"
    if icon_style not in ("default", "mini", "braille"):
        icon_style = "default"
    hidden_icons = str(ui.get("hidden_icons", DEFAULT_HIDDEN_ICONS)).strip()
    hidden_menu_items = str(ui.get("hidden_menu_items", DEFAULT_HIDDEN_MENU_ITEMS)).strip()
    return AppConfig(
        theme=theme,
        show_hidden=show_hidden,
        word_wrap_default=word_wrap_default,
        sunday_first=sunday_first,
        show_welcome=show_welcome,
        icon_style=icon_style,
        hidden_icons=hidden_icons,
        hidden_menu_items=hidden_menu_items,
    )


def load_config(path: str | Path | None = None) -> AppConfig:
    """Load config from TOML file; return defaults when missing/invalid."""
    cfg_path = Path(path) if path is not None else default_config_path()
    try:
        text = cfg_path.read_text(encoding="utf-8")
    except OSError:
        return AppConfig()
    return _normalize_config(_parse_toml(text))


def serialize_config(config: AppConfig) -> str:
    """Serialize AppConfig as TOML text."""
    return (
        "# RetroTUI user configuration\n"
        "[ui]\n"
        f'theme = "{config.theme}"\n'
        f"show_hidden = {'true' if config.show_hidden else 'false'}\n"
        f"word_wrap_default = {'true' if config.word_wrap_default else 'false'}\n"
        f"sunday_first = {'true' if config.sunday_first else 'false'}\n"
        f"show_welcome = {'true' if config.show_welcome else 'false'}\n"
        f'icon_style = "{config.icon_style}"\n'
        f'hidden_icons = "{config.hidden_icons}"\n'
        f'hidden_menu_items = "{config.hidden_menu_items}"\n'
    )


def save_config(config: AppConfig, path: str | Path | None = None) -> Path:
    """Persist config and return written path."""
    cfg_path = Path(path) if path is not None else default_config_path()
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(serialize_config(config), encoding="utf-8", newline="\n")
    return cfg_path
