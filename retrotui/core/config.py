"""Persistent config loader/saver for RetroTUI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..theme import DEFAULT_THEME, THEMES
from .actions import AppAction

try:  # Python 3.11+
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover - exercised on Python <3.11
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError:
        tomllib = None

if tomllib is not None:
    _TOML_PARSE_ERRORS = (
        getattr(tomllib, "TOMLDecodeError", ValueError),
        TypeError,
        ValueError,
    )
else:
    _TOML_PARSE_ERRORS = (TypeError, ValueError)


CONFIG_SCHEMA_VERSION = 1
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
            PLUGIN_VISIBILITY_WILDCARD,
        }
    )
)


@dataclass(frozen=True)
class AppConfig:
    """Persistent user-facing configuration."""

    schema_version: int = CONFIG_SCHEMA_VERSION
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


def _strip_inline_comment(line: str) -> str:
    """Remove TOML comments outside quoted strings."""
    quote = None
    escape = False
    for idx, ch in enumerate(line):
        if escape:
            escape = False
            continue
        if quote == '"' and ch == "\\":
            escape = True
            continue
        if ch in ('"', "'"):
            if quote == ch:
                quote = None
            elif quote is None:
                quote = ch
            continue
        if ch == "#" and quote is None:
            return line[:idx]
    return line


def _decode_basic_string(value: str) -> str:
    """Decode the small TOML escape subset RetroTUI writes.

    Thin wrapper around ``utils.decode_toml_basic_string`` kept for
    backwards compatibility (tests import this name).
    """
    from ..utils import decode_toml_basic_string as _utils_decode

    return _utils_decode(value)


def _parse_scalar(token):
    token = token.strip()
    if not token:
        return ""
    if len(token) >= 2 and token[0] == token[-1] == '"':
        return _decode_basic_string(token[1:-1])
    if len(token) >= 2 and token[0] == token[-1] == "'":
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
        line = _strip_inline_comment(raw_line).strip()
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


def _coerce_schema_version(value, default=0):
    try:
        version = int(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return max(0, version)


def _config_schema_version(raw: dict) -> int:
    """Read schema metadata while accepting pre-versioned legacy files."""
    if not isinstance(raw, dict):
        return 0
    meta = raw.get("meta")
    if isinstance(meta, dict) and "schema_version" in meta:
        return _coerce_schema_version(meta.get("schema_version"))
    if "schema_version" in raw:
        return _coerce_schema_version(raw.get("schema_version"))
    if "config_version" in raw:
        return _coerce_schema_version(raw.get("config_version"))
    return 0


def _migrate_config(raw: dict) -> tuple[dict, int]:
    """Migrate legacy schema 0 into the current structured representation."""
    if not isinstance(raw, dict):
        raw = {}
    version = _config_schema_version(raw)
    if version > 0:
        return raw, version

    migrated = dict(raw)
    if not isinstance(migrated.get("ui"), dict):
        ui_keys = {
            "theme",
            "show_hidden",
            "word_wrap_default",
            "sunday_first",
            "show_welcome",
            "icon_style",
            "hidden_icons",
            "hidden_menu_items",
        }
        legacy_ui = {
            key: migrated[key]
            for key in ui_keys
            if key in migrated
        }
        migrated["ui"] = legacy_ui
    migrated["meta"] = {"schema_version": CONFIG_SCHEMA_VERSION}
    return migrated, CONFIG_SCHEMA_VERSION


def _normalize_icon_style_value(value) -> str:
    icon_style = str(value or "default").strip().lower() or "default"
    if icon_style in ("mini", "retro_01", "retro01", "retro-01"):
        return "retro_01"
    if icon_style in ("win31_art", "win31", "win31-art", "classic_art"):
        return "win31_art"
    if icon_style in ("default", "classic"):
        return "default"
    return "default"


def _normalize_config(raw: dict) -> AppConfig:
    raw, schema_version = _migrate_config(raw)
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
    icon_style = _normalize_icon_style_value(ui.get("icon_style", "default"))
    hidden_icons = str(ui.get("hidden_icons", DEFAULT_HIDDEN_ICONS)).strip()
    hidden_menu_items = str(ui.get("hidden_menu_items", DEFAULT_HIDDEN_MENU_ITEMS)).strip()
    return AppConfig(
        schema_version=schema_version,
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


def serialize_config(config: AppConfig, *, icon_positions=None) -> str:
    """Serialize AppConfig as TOML text.

    ``icon_positions`` is an optional ``{key: (x, y)}`` mapping rendered as
    an extra ``[icons]`` section. Including it in the same string avoids
    the previous double-write (one for the main config, one to splice in
    the icons block afterwards).
    """
    from ..utils import toml_basic_string
    schema_version = _coerce_schema_version(
        getattr(config, "schema_version", CONFIG_SCHEMA_VERSION),
        default=CONFIG_SCHEMA_VERSION,
    )
    if schema_version > CONFIG_SCHEMA_VERSION:
        raise ValueError(
            "Refusing to overwrite config schema "
            f"{schema_version} with older schema {CONFIG_SCHEMA_VERSION}."
        )
    body = (
        "# RetroTUI user configuration\n"
        "[meta]\n"
        f"schema_version = {CONFIG_SCHEMA_VERSION}\n"
        "\n"
        "[ui]\n"
        f'theme = "{toml_basic_string(config.theme)}"\n'
        f"show_hidden = {'true' if config.show_hidden else 'false'}\n"
        f"word_wrap_default = {'true' if config.word_wrap_default else 'false'}\n"
        f"sunday_first = {'true' if config.sunday_first else 'false'}\n"
        f"show_welcome = {'true' if config.show_welcome else 'false'}\n"
        f'icon_style = "{toml_basic_string(config.icon_style)}"\n'
        f'hidden_icons = "{toml_basic_string(config.hidden_icons)}"\n'
        f'hidden_menu_items = "{toml_basic_string(config.hidden_menu_items)}"\n'
    )
    if icon_positions:
        lines = [body.rstrip("\n"), "", "[icons]"]
        for name, (x, y) in sorted(icon_positions.items()):
            lines.append(f'"{toml_basic_string(name)}" = "{int(x)},{int(y)}"')
        return "\n".join(lines) + "\n"
    return body


def save_config(
    config: AppConfig,
    path: str | Path | None = None,
    *,
    icon_positions=None,
) -> Path:
    """Persist config and return written path."""
    from ..utils import atomic_write_text
    cfg_path = Path(path) if path is not None else default_config_path()
    return atomic_write_text(
        cfg_path, serialize_config(config, icon_positions=icon_positions),
    )
