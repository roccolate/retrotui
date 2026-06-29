"""Plugin discovery and loading for RetroTUI."""
import os
import sys
import importlib.util
from pathlib import Path

_PLUGIN_IMPORT_ERRORS = (
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
)
_PLUGIN_DISCOVERY_PARSE_ERRORS = (
    AttributeError,
    LookupError,
    OSError,
    RuntimeError,
    TypeError,
    UnicodeError,
    ValueError,
)

try:
    import tomllib  # Python 3.11+
except _PLUGIN_IMPORT_ERRORS:
    try:
        import tomli as tomllib  # type: ignore
    except _PLUGIN_IMPORT_ERRORS:
        tomllib = None  # type: ignore

_DEFAULT_PLUGIN_DIR = os.path.join(os.path.expanduser("~"), ".config", "retrotui", "plugins")
PLUGIN_DIR = _DEFAULT_PLUGIN_DIR


def _bundled_plugin_dir():
    """Return the package-internal bundled plugins directory."""
    return str(Path(__file__).resolve().parent.parent / "bundled_plugins")


def _repo_examples_plugin_dir():
    """Return repo-local bundled examples/plugins path when available."""
    return str(Path(__file__).resolve().parents[2] / "examples" / "plugins")


def _cwd_examples_plugin_dir():
    """Return cwd-local examples/plugins path when available."""
    return str((Path.cwd() / "examples" / "plugins").resolve())


def _iter_plugin_dirs():
    """Yield plugin directories in discovery priority order."""
    seen = set()

    # Explicit runtime override (single directory).
    forced = str(os.environ.get("RETROTUI_PLUGIN_DIR", "") or "").strip()
    if forced:
        norm = os.path.normcase(os.path.normpath(forced))
        if norm not in seen:
            seen.add(norm)
            yield forced

    # Optional multi-directory override using OS path separator.
    path_list = str(os.environ.get("RETROTUI_PLUGIN_PATH", "") or "").strip()
    if path_list:
        for raw in path_list.split(os.pathsep):
            candidate = raw.strip()
            if not candidate:
                continue
            norm = os.path.normcase(os.path.normpath(candidate))
            if norm in seen:
                continue
            seen.add(norm)
            yield candidate

    # Primary user plugin directory.
    primary = str(PLUGIN_DIR or "").strip()
    if primary:
        norm = os.path.normcase(os.path.normpath(primary))
        if norm not in seen:
            seen.add(norm)
            yield primary

    # Bundled plugins shipped with the package (always included after user
    # plugins so user plugin ids can intentionally override bundled ones).
    bundled = _bundled_plugin_dir()
    if bundled:
        norm = os.path.normcase(os.path.normpath(bundled))
        if norm not in seen:
            seen.add(norm)
            yield bundled

    # Bundled examples: include when using default plugin dir to keep
    # built-in plugins visible out of the box. Earlier directories win on
    # duplicate ids because discovery skips ids it has already seen.
    if primary and os.path.normcase(os.path.normpath(primary)) == os.path.normcase(os.path.normpath(_DEFAULT_PLUGIN_DIR)):
        for candidate in (_repo_examples_plugin_dir(), _cwd_examples_plugin_dir()):
            norm = os.path.normcase(os.path.normpath(candidate))
            if candidate and norm not in seen:
                seen.add(norm)
                yield candidate


def discover_plugins():
    """Scan plugin directory and return list of plugin manifests.

    Returns list of dicts (manifest) with added key '_path' pointing to plugin folder.
    """
    plugins = []
    seen_ids = set()
    for plugin_dir in _iter_plugin_dirs():
        if not os.path.isdir(plugin_dir):
            continue
        for entry in os.scandir(plugin_dir):
            if not entry.is_dir():
                continue
            manifest_path = os.path.join(entry.path, "plugin.toml")
            if not os.path.exists(manifest_path):
                continue

            try:
                if tomllib is None:
                    # Fallback path — only basic ``key = value`` lines.
                    # ``tomllib`` is stdlib on Python 3.11+; on older
                    # interpreters the fallback is intentionally naive and
                    # only supports the slice of TOML RetroTUI plugins
                    # actually use. We emit a loud warning so plugin
                    # authors know the cost: arrays, inline tables and
                    # multi-line strings silently come back as raw text.
                    LOGGER.warning(
                        "Falling back to minimal TOML parser for plugin "
                        "manifest %s (Python < 3.11 without tomli). "
                        "Use Python 3.11+ or install tomli to support "
                        "rich manifests.", manifest_path,
                    )
                    with open(manifest_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    manifest = {"plugin": {}}
                    current = None
                    for line in content.splitlines():
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if line.startswith("[") and line.endswith("]"):
                            current = line.strip("[]").strip()
                            if current not in manifest:
                                manifest[current] = {}
                            continue
                        if "=" in line and current:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip('"')
                            manifest[current][k] = v
                else:
                    with open(manifest_path, "rb") as f:
                        manifest = tomllib.load(f)

                plugin_id = str((manifest.get("plugin", {}) or {}).get("id") or "").strip()
                if plugin_id:
                    plugin_key = plugin_id.lower()
                    if plugin_key in seen_ids:
                        continue
                    seen_ids.add(plugin_key)
                manifest["_path"] = entry.path
                plugins.append(manifest)
            except _PLUGIN_DISCOVERY_PARSE_ERRORS:
                # Skip malformed plugins silently
                continue

    return plugins


def load_plugin(manifest):
    """Import plugin module and return the app class.

    Loads <plugin>.__init__.py as a module and returns module.Plugin or module.App.
    Sets the returned class.PLUGIN_ID if present.
    """
    plugin_path = manifest.get("_path")
    if not plugin_path:
        return None
    init_path = os.path.join(plugin_path, "__init__.py")
    if not os.path.exists(init_path):
        return None

    plugin_id = manifest.get("plugin", {}).get("id")
    try:
        spec = importlib.util.spec_from_file_location(f"retrotui_plugin_{plugin_id}", init_path)
        if spec is None or getattr(spec, "loader", None) is None:
            return None
        module = importlib.util.module_from_spec(spec)
        # Do not modify sys.path here; importing the plugin module should
        # work using standard import mechanics. Executing the spec loads
        # the module directly from its file.
        spec.loader.exec_module(module)  # type: ignore
    except _PLUGIN_IMPORT_ERRORS:
        return None

    app_class = getattr(module, "Plugin", None) or getattr(module, "App", None)
    if app_class and plugin_id:
        try:
            setattr(app_class, "PLUGIN_ID", plugin_id)
        except _PLUGIN_IMPORT_ERRORS:
            pass
    return app_class
