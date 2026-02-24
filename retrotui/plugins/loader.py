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


PLUGIN_DIR = os.path.join(os.path.expanduser("~"), ".config", "retrotui", "plugins")


def discover_plugins():
    """Scan plugin directory and return list of plugin manifests.

    Returns list of dicts (manifest) with added key '_path' pointing to plugin folder.
    """
    plugins = []
    if not os.path.isdir(PLUGIN_DIR):
        return plugins

    for entry in os.scandir(PLUGIN_DIR):
        if not entry.is_dir():
            continue
        manifest_path = os.path.join(entry.path, "plugin.toml")
        if not os.path.exists(manifest_path):
            continue

        try:
            if tomllib is None:
                # Graceful fallback: parse minimal TOML manually (only basic key=values)
                with open(manifest_path, "r", encoding="utf-8") as f:
                    content = f.read()
                # Fallback: try to extract the [plugin] table using a naive approach
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
