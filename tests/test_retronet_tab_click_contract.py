"""Regression contract for RetroNet tab-bar mouse handling."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

_TESTS_DIR = Path(__file__).resolve().parent
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))

from _support import make_fake_curses

sys.modules["curses"] = make_fake_curses()

from retrotui.apps.retronet import RetroNetWindow
from retrotui.core.actions import ActionType


class RetroNetTabClickContractTests(unittest.TestCase):
    def setUp(self):
        self.thread_patcher = mock.patch("retrotui.apps.retronet.threading.Thread")
        self.thread_patcher.start()
        self.addCleanup(self.thread_patcher.stop)

        with (
            mock.patch("retrotui.apps.retronet.theme_attr", return_value=0),
            mock.patch("retrotui.apps.retronet._cleanup_stale_viewsource_files"),
        ):
            self.win = RetroNetWindow(0, 0, 80, 24)

        self.win.body_rect = mock.Mock(return_value=(5, 7, 60, 18))
        self.win._new_tab("", activate=True)
        self.win.tabs[0].title = "One"
        self.win.tabs[1].title = "Two"

    def test_click_passes_body_width_without_sidebar(self):
        bx, by, bw, _ = self.win.body_rect()

        with mock.patch.object(
            self.win, "_handle_tab_bar_click", return_value=None
        ) as handler:
            result = self.win.handle_click(bx + 1, by)

        handler.assert_called_once_with(
            0,
            bw,
            content_x=bx,
            content_w=bw,
        )
        self.assertEqual(result.type, ActionType.REFRESH)

    def test_click_negotiates_content_width_with_sidebar(self):
        self.win.show_sidebar = True
        bx, by, bw, _ = self.win.body_rect()
        sidebar_w = self.win._sidebar_width(bw)
        content_x = bx + sidebar_w

        with mock.patch.object(
            self.win, "_handle_tab_bar_click", return_value=None
        ) as handler:
            result = self.win.handle_click(content_x + 1, by)

        handler.assert_called_once_with(
            0,
            bw,
            content_x=content_x,
            content_w=bw - sidebar_w,
        )
        self.assertEqual(result.type, ActionType.REFRESH)

    def test_click_switches_tabs_without_name_error(self):
        bx, by, _, _ = self.win.body_rect()
        self.win.active_tab_idx = 1

        result = self.win.handle_click(bx + 1, by)

        self.assertEqual(result.type, ActionType.REFRESH)
        self.assertEqual(self.win.active_tab_idx, 0)
        self.assertEqual(len(self.win.tabs), 2)

    def test_click_close_marker_closes_exact_tab(self):
        bx, by, bw, _ = self.win.body_rect()
        first_label = self.win._tab_chip_label(self.win.tabs[0])
        first_width = self.win._tab_chip_width(
            first_label,
            content_x=bx,
            tab_x=bx + 1,
            content_w=bw,
        )

        result = self.win.handle_click(bx + 1 + first_width - 1, by)

        self.assertEqual(result.type, ActionType.REFRESH)
        self.assertEqual(len(self.win.tabs), 1)
        self.assertEqual(self.win.tabs[0].title, "Two")
        self.assertEqual(self.win.active_tab_idx, 0)

    def test_click_plus_creates_and_activates_new_tab(self):
        bx, by, bw, _ = self.win.body_rect()
        cursor = 0
        tab_x = bx + 1
        for tab in self.win.tabs:
            label = self.win._tab_chip_label(tab)
            chip_width = self.win._tab_chip_width(
                label,
                content_x=bx,
                tab_x=tab_x,
                content_w=bw,
            )
            cursor += chip_width
            tab_x += chip_width - 1

        result = self.win.handle_click(bx + 1 + cursor, by)

        self.assertEqual(result.type, ActionType.REFRESH)
        self.assertEqual(len(self.win.tabs), 3)
        self.assertEqual(self.win.active_tab_idx, 2)


if __name__ == "__main__":
    unittest.main()
