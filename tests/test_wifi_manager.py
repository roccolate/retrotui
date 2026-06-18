import importlib
import sys
import types
import unittest
from unittest import mock

from _support import make_fake_curses


class WifiManagerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_curses = sys.modules.get("curses")
        sys.modules["curses"] = make_fake_curses()

        for mod_name in (
            "retrotui.apps.wifi_manager",
            "retrotui.ui.window",
            "retrotui.utils",
        ):
            sys.modules.pop(mod_name, None)

        cls.mod = importlib.import_module("retrotui.apps.wifi_manager")

    @classmethod
    def tearDownClass(cls):
        for mod_name in (
            "retrotui.apps.wifi_manager",
            "retrotui.ui.window",
            "retrotui.utils",
        ):
            sys.modules.pop(mod_name, None)
        if cls._prev_curses is not None:
            sys.modules["curses"] = cls._prev_curses
        else:
            sys.modules.pop("curses", None)

    def test_draw_handles_no_nmcli(self):
        win = self.mod.WifiManagerWindow(0, 0, 60, 20)
        # Force nmcli absence
        win.nmcli = None
        with mock.patch.object(win, "draw_frame", return_value=0), mock.patch.object(
            self.mod, "safe_addstr"
        ) as safe_addstr, mock.patch.object(self.mod, "theme_attr", return_value=0):
            win.draw(None)

    def test_split_nmcli_fields_unescaped(self):
        splitter = self.mod.WifiManagerWindow._split_nmcli_fields
        # No escapes, default 5 columns.
        self.assertEqual(
            splitter("MyNet:80:WPA2:*:AA:BB:CC:DD:EE:FF", expected=5),
            ["MyNet", "80", "WPA2", "*", "AA:BB:CC:DD:EE:FF"],
        )

    def test_split_nmcli_fields_preserves_escaped_colon(self):
        splitter = self.mod.WifiManagerWindow._split_nmcli_fields
        # SSID contains a literal colon; nmcli encodes it as `\:`
        # and the BSSID is the last field, so it stays intact.
        result = splitter(r"My\:Network:42:WPA1::00\:11\:22\:33\:44\:55:66", expected=5)
        self.assertEqual(result[0], "My:Network")
        self.assertEqual(result[1], "42")
        self.assertEqual(result[2], "WPA1")
        # Empty IN-USE field after a trailing colon stays empty.
        self.assertEqual(result[3], "")
        # BSSID keeps its colons.
        self.assertEqual(result[4], "00:11:22:33:44:55:66")
