import importlib
import sys
import types
import unittest
from pathlib import Path
from unittest import mock


def _install_fake_curses():
    fake = types.ModuleType("curses")
    fake.COLOR_BLACK = 0
    fake.COLOR_BLUE = 4
    fake.COLOR_CYAN = 6
    fake.COLOR_GREEN = 2
    fake.COLOR_WHITE = 7
    fake.COLOR_YELLOW = 3
    fake.error = Exception
    fake.color_pair = lambda value: value
    return fake


class ThemeAndConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_curses = sys.modules.get("curses")
        sys.modules["curses"] = _install_fake_curses()

        for mod_name in (
            "retrotui.constants",
            "retrotui.theme",
            "retrotui.core.config",
        ):
            sys.modules.pop(mod_name, None)

        cls.theme = importlib.import_module("retrotui.theme")
        cls.config = importlib.import_module("retrotui.core.config")

    @classmethod
    def tearDownClass(cls):
        for mod_name in (
            "retrotui.constants",
            "retrotui.theme",
            "retrotui.core.config",
        ):
            sys.modules.pop(mod_name, None)
        if cls._prev_curses is not None:
            sys.modules["curses"] = cls._prev_curses
        else:
            sys.modules.pop("curses", None)

    def test_list_themes_and_get_theme_fallback(self):
        keys = [theme.key for theme in self.theme.list_themes()]
        self.assertEqual(keys, ["win31", "dos_cga", "win95", "hacker", "amiga"])
        self.assertEqual(self.theme.get_theme(None).key, "win31")
        self.assertEqual(self.theme.get_theme("unknown").key, "win31")
        self.assertEqual(self.theme.get_theme("hacker").key, "hacker")

    def test_default_config_path_uses_home(self):
        fake_home = Path("/tmp/fakehome")
        with mock.patch.object(self.config.Path, "home", return_value=fake_home):
            cfg_path = self.config.default_config_path()
        self.assertEqual(cfg_path, fake_home / ".config" / "retrotui" / "config.toml")

    def test_coerce_bool_and_parse_scalar_helpers(self):
        self.assertTrue(self.config._coerce_bool(True))
        self.assertTrue(self.config._coerce_bool("on"))
        self.assertFalse(self.config._coerce_bool("off"))
        self.assertFalse(self.config._coerce_bool("garbage", default=False))
        self.assertEqual(self.config._parse_scalar(""), "")
        self.assertEqual(self.config._parse_scalar('"abc"'), "abc")
        self.assertTrue(self.config._parse_scalar("true"))
        self.assertFalse(self.config._parse_scalar("false"))
        self.assertEqual(self.config._parse_scalar("42"), 42)
        self.assertEqual(self.config._parse_scalar("x"), "x")

    def test_fallback_parse_toml_and_parse_toml_paths(self):
        parsed = self.config._fallback_parse_toml(
            """
            # comment
            global_key = "yes"
            [ui]
            theme = "win95"
            show_hidden = true
            bad_line
            [misc]
            value = 5
            plain = "root"
            """
        )
        self.assertEqual(parsed["global_key"], "yes")
        self.assertEqual(parsed["ui"]["theme"], "win95")
        self.assertTrue(parsed["ui"]["show_hidden"])
        self.assertEqual(parsed["misc"]["value"], 5)
        self.assertEqual(parsed["misc"]["plain"], "root")

        with mock.patch.object(self.config, "tomllib", types.SimpleNamespace(loads=lambda _: {"ui": {"theme": "amiga"}})):
            parsed_fast = self.config._parse_toml("[ui]\ntheme='x'")
        self.assertEqual(parsed_fast["ui"]["theme"], "amiga")

        broken = types.SimpleNamespace(loads=mock.Mock(side_effect=ValueError("bad toml")))
        with mock.patch.object(self.config, "tomllib", broken):
            parsed_fallback = self.config._parse_toml('[ui]\ntheme = "dos_cga"\n')
        self.assertEqual(parsed_fallback["ui"]["theme"], "dos_cga")

    def test_normalize_and_load_config_branches(self):
        normalized = self.config._normalize_config({"ui": {"theme": "WIN95", "show_hidden": "yes", "word_wrap_default": "1"}})
        self.assertEqual(normalized.theme, "win95")
        self.assertTrue(normalized.show_hidden)
        self.assertTrue(normalized.word_wrap_default)

        fallback = self.config._normalize_config({"ui": {"theme": "invalid", "show_hidden": "no", "word_wrap_default": "0"}})
        self.assertEqual(fallback.theme, self.theme.DEFAULT_THEME)
        self.assertFalse(fallback.show_hidden)
        self.assertFalse(fallback.word_wrap_default)

        not_dict = self.config._normalize_config({"ui": "bad"})
        self.assertEqual(not_dict.theme, self.theme.DEFAULT_THEME)

        with mock.patch.object(Path, "read_text", side_effect=OSError("missing")):
            missing = self.config.load_config(Path("/tmp/does-not-exist-xyz.toml"))
        self.assertEqual(missing, self.config.AppConfig())

        with mock.patch.object(
            Path,
            "read_text",
            return_value='[ui]\ntheme = "hacker"\nshow_hidden = true\nword_wrap_default = false\n',
        ):
            loaded = self.config.load_config(Path("/tmp/config.toml"))
        self.assertEqual(loaded.theme, "hacker")
        self.assertTrue(loaded.show_hidden)
        self.assertFalse(loaded.word_wrap_default)

    def test_serialize_and_save_config(self):
        config = self.config.AppConfig(theme="amiga", show_hidden=True, word_wrap_default=False)
        text = self.config.serialize_config(config)
        self.assertIn('theme = "amiga"', text)
        self.assertIn("show_hidden = true", text)
        self.assertIn("word_wrap_default = false", text)

        cfg_file = Path("/tmp/nested/config.toml")
        with (
            mock.patch.object(Path, "mkdir") as mkdir,
            mock.patch.object(Path, "write_text") as write_text,
        ):
            written = self.config.save_config(config, cfg_file)
        self.assertEqual(written, cfg_file)
        mkdir.assert_called_once_with(parents=True, exist_ok=True)
        write_text.assert_called_once()

    def test_config_module_handles_missing_tomllib_import(self):
        real_import = __import__

        def fake_import(name, *args, **kwargs):
            if name == "tomllib":
                raise ModuleNotFoundError("no tomllib")
            return real_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=fake_import):
            sys.modules.pop("retrotui.core.config", None)
            fallback_mod = importlib.import_module("retrotui.core.config")

        self.assertIsNone(fallback_mod.tomllib)
        parsed = fallback_mod._parse_toml('[ui]\ntheme = "win31"\n')
        self.assertEqual(parsed["ui"]["theme"], "win31")

        sys.modules.pop("retrotui.core.config", None)
        importlib.import_module("retrotui.core.config")


if __name__ == "__main__":
    unittest.main()
