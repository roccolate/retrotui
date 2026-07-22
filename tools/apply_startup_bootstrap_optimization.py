"""Apply the startup bootstrap optimization cut.

Temporary one-shot helper. It is removed before the pull request is merged.
"""

from __future__ import annotations

from pathlib import Path


APP_PATH = Path("retrotui/core/app.py")
TEST_PATH = Path("tests/test_core_app.py")


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


def replace_first(text: str, old: str, new: str, *, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"{label}: match not found")
    return text.replace(old, new, 1)


def patch_app() -> None:
    text = APP_PATH.read_text(encoding="utf-8")

    text = replace_once(
        text,
        "    WELCOME_WIN_WIDTH, WELCOME_WIN_HEIGHT,\n",
        "",
        label="welcome constants import",
    )
    # app.py also has a local Window import in show_bookmarks_window; only the
    # top-level import belongs to the extracted welcome controller.
    text = replace_first(
        text,
        "from ..ui.window import Window\n",
        "",
        label="top-level Window import",
    )
    text = replace_once(
        text,
        "from .content import build_welcome_content\n",
        "",
        label="welcome content import",
    )
    text = replace_once(
        text,
        "from .event_loop import run_app_loop\n",
        "from .event_loop import run_app_loop\nfrom .welcome import open_welcome_window\n",
        label="welcome controller import",
    )

    text = replace_once(
        text,
        "        self.refresh_icons()\n        self._rebuild_global_menu()\n",
        "",
        label="duplicate shell catalog bootstrap",
    )

    old_plugin_comment = '''        # Plugin discovery and registration (optional; failures should not crash).\n        self._load_plugins_runtime()\n'''
    new_plugin_comment = '''        # Plugin discovery owns the single final icon/menu catalog build.\n        # Building before discovery would compile both catalogs twice at startup.\n        self._load_plugins_runtime()\n'''
    text = replace_once(
        text,
        old_plugin_comment,
        new_plugin_comment,
        label="plugin bootstrap comment",
    )

    start_marker = "        # Create a welcome window if enabled\n"
    end_marker = "            self._spawn_window(win)\n"
    start = text.find(start_marker)
    if start < 0:
        raise RuntimeError("welcome block start not found")
    end = text.find(end_marker, start)
    if end < 0:
        raise RuntimeError("welcome block end not found")
    end += len(end_marker)
    replacement = '''        # Welcome behavior is isolated from the application composition root.\n        if self.show_welcome:\n            open_welcome_window(self, APP_VERSION)\n'''
    text = text[:start] + replacement + text[end:]

    APP_PATH.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    text = TEST_PATH.read_text(encoding="utf-8")

    setup_anchor = '            "retrotui.core.plugin_manager",\n            "retrotui.core.app",\n'
    setup_replacement = (
        '            "retrotui.core.plugin_manager",\n'
        '            "retrotui.core.welcome",\n'
        '            "retrotui.core.app",\n'
    )
    if text.count(setup_anchor) != 2:
        raise RuntimeError(
            "test module cleanup lists: expected two plugin/app anchors, "
            f"found {text.count(setup_anchor)}"
        )
    text = text.replace(setup_anchor, setup_replacement)

    import_anchor = '''        cls.plugin_mod = importlib.import_module("retrotui.core.plugin_manager")\n        cls.curses = sys.modules["curses"]\n'''
    import_replacement = '''        cls.plugin_mod = importlib.import_module("retrotui.core.plugin_manager")\n        cls.welcome_mod = importlib.import_module("retrotui.core.welcome")\n        cls.curses = sys.modules["curses"]\n'''
    text = replace_once(
        text,
        import_anchor,
        import_replacement,
        label="welcome test module import",
    )

    text = text.replace(
        'mock.patch.object(self.app_mod, "build_welcome_content"',
        'mock.patch.object(self.welcome_mod, "build_welcome_content"',
    )
    text = text.replace(
        'mock.patch.object(self.app_mod, "Window"',
        'mock.patch.object(self.welcome_mod, "Window"',
    )

    test_anchor = "    def test_init_configures_terminal_and_creates_welcome_window(self):\n"
    if text.count(test_anchor) != 1:
        raise RuntimeError("startup catalog test insertion anchor not found uniquely")

    new_test = '''    def test_init_builds_shell_catalogs_once_after_plugin_loading(self):\n        stdscr = types.SimpleNamespace(getmaxyx=lambda: (30, 120))\n        fake_menu = types.SimpleNamespace(\n            active=False,\n            selected_menu=0,\n            selected_item=0,\n            handle_key=mock.Mock(return_value=None),\n            handle_click=mock.Mock(return_value=None),\n            handle_hover=mock.Mock(return_value=None),\n            hit_test_dropdown=mock.Mock(return_value=False),\n        )\n        events = []\n\n        def fake_refresh_icons(app):\n            events.append("icons")\n            app.icons = []\n\n        def fake_rebuild_menu(app):\n            events.append("menu")\n            app.menu = fake_menu\n\n        def fake_load_plugins(app):\n            events.append("plugins")\n            app.refresh_icons()\n            app._rebuild_global_menu()\n\n        config = types.SimpleNamespace(\n            theme="win31",\n            show_hidden=False,\n            word_wrap_default=False,\n            sunday_first=False,\n            show_welcome=False,\n            icon_style="default",\n            hidden_icons="",\n            hidden_menu_items="",\n        )\n        with (\n            mock.patch.object(self.app_mod, "check_unicode_support", return_value=True),\n            mock.patch.object(self.app_mod, "load_config", return_value=config),\n            mock.patch.object(self.app_mod, "load_plugins_runtime", side_effect=fake_load_plugins),\n            mock.patch.object(self.app_mod, "_refresh_icons", side_effect=fake_refresh_icons),\n            mock.patch.object(self.app_mod, "rebuild_global_menu", side_effect=fake_rebuild_menu),\n            mock.patch.object(self.app_mod, "configure_terminal"),\n            mock.patch.object(self.app_mod, "disable_flow_control"),\n            mock.patch.object(self.app_mod, "enable_mouse_support", return_value=(1, 2, 3)),\n            mock.patch.object(self.app_mod, "init_colors"),\n        ):\n            self.app_mod.RetroTUI(stdscr)\n\n        self.assertEqual(events, ["plugins", "icons", "menu"])\n\n'''
    text = text.replace(test_anchor, new_test + test_anchor, 1)

    TEST_PATH.write_text(text, encoding="utf-8")


def main() -> None:
    patch_app()
    patch_tests()


if __name__ == "__main__":
    main()
