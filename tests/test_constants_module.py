import importlib
import sys
import types
import unittest
from pathlib import Path


class ConstantsModuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_curses = sys.modules.get("curses")
        sys.modules["curses"] = types.ModuleType("curses")
        for mod_name in ("retrotui.constants", "retrotui.core.actions"):
            sys.modules.pop(mod_name, None)
        cls.package = importlib.import_module("retrotui")
        cls.constants = importlib.import_module("retrotui.constants")

    @classmethod
    def tearDownClass(cls):
        for mod_name in ("retrotui.constants", "retrotui.core.actions"):
            sys.modules.pop(mod_name, None)
        if cls._prev_curses is not None:
            sys.modules["curses"] = cls._prev_curses
        else:
            sys.modules.pop("curses", None)

    def test_package_exposes_version(self):
        self.assertEqual(self.package.__version__, "0.3.6")

    def test_icons_and_ascii_icons_are_aligned(self):
        self.assertEqual(len(self.constants.ICONS), len(self.constants.ICONS_ASCII))
        self.assertGreaterEqual(len(self.constants.ICONS), 6)

        for unicode_icon, ascii_icon in zip(self.constants.ICONS, self.constants.ICONS_ASCII):
            self.assertIn("label", unicode_icon)
            self.assertIn("action", unicode_icon)
            self.assertIn("art", unicode_icon)
            self.assertEqual(unicode_icon["label"], ascii_icon["label"])
            self.assertEqual(unicode_icon["action"], ascii_icon["action"])
            self.assertEqual(len(unicode_icon["art"]), 3)
            self.assertEqual(len(ascii_icon["art"]), 3)

    def test_video_extensions_include_common_formats(self):
        for ext in (".mp4", ".mkv", ".webm", ".avi", ".mov"):
            self.assertIn(ext, self.constants.VIDEO_EXTENSIONS)

    def test_border_characters_and_patterns_are_non_empty(self):
        chars = (
            self.constants.BOX_TL,
            self.constants.BOX_TR,
            self.constants.BOX_BL,
            self.constants.BOX_BR,
            self.constants.BOX_H,
            self.constants.BOX_V,
            self.constants.SB_TL,
            self.constants.SB_TR,
            self.constants.SB_BL,
            self.constants.SB_BR,
            self.constants.SB_H,
            self.constants.SB_V,
            self.constants.DESKTOP_PATTERN,
        )
        for ch in chars:
            self.assertIsInstance(ch, str)
            self.assertGreaterEqual(len(ch), 1)

    def test_color_pair_ids_are_positive_ints(self):
        ids = [
            self.constants.C_DESKTOP,
            self.constants.C_MENUBAR,
            self.constants.C_MENU_ITEM,
            self.constants.C_MENU_SEL,
            self.constants.C_WIN_BORDER,
            self.constants.C_WIN_TITLE,
            self.constants.C_WIN_TITLE_INV,
            self.constants.C_WIN_BODY,
            self.constants.C_BUTTON,
            self.constants.C_BUTTON_SEL,
            self.constants.C_DIALOG,
            self.constants.C_STATUS,
            self.constants.C_ICON,
            self.constants.C_ICON_SEL,
            self.constants.C_SCROLLBAR,
            self.constants.C_WIN_INACTIVE,
            self.constants.C_FM_SELECTED,
            self.constants.C_FM_DIR,
            self.constants.C_TASKBAR,
        ]
        self.assertTrue(all(isinstance(value, int) and value > 0 for value in ids))
        self.assertEqual(len(set(ids)), len(ids))

    def test_constants_source_executes_with_package_context(self):
        source_path = Path("retrotui/constants.py").resolve()
        source = source_path.read_text(encoding="utf-8")
        namespace = {"__name__": "retrotui.constants_exec", "__package__": "retrotui"}

        exec(compile(source, str(source_path), "exec"), namespace)

        self.assertIn("ICONS", namespace)
        self.assertIn("ICONS_ASCII", namespace)
        self.assertIn("VIDEO_EXTENSIONS", namespace)

    def test_package_init_source_sets_version(self):
        source_path = Path("retrotui/__init__.py").resolve()
        source = source_path.read_text(encoding="utf-8")
        namespace = {"__name__": "retrotui.__init___exec", "__package__": "retrotui"}

        exec(compile(source, str(source_path), "exec"), namespace)

        self.assertEqual(namespace.get("__version__"), "0.3.6")


if __name__ == "__main__":
    unittest.main()
