from pathlib import Path


def replace_once(path_name, old, new):
    path = Path(path_name)
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(
            f"{path_name}: expected one match, found {count}: {old!r}"
        )
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main():
    replace_once(
        "tests/test_rendering.py",
        "                and call.args[2] == 22\n",
        "                and call.args[2] == 21\n",
    )

    replace_once(
        "tests/test_mouse_router.py",
        "        # Right side of unified top bar overlaps clock hotspot; taskbar must win.\n"
        "        self.mouse_router.handle_mouse_event(app, (0, 79, 0, 0, self.curses.BUTTON1_CLICKED))\n\n"
        "        app.handle_taskbar_click.assert_called_once_with(79, 0)\n",
        "        # Right side of the bottom taskbar overlaps the clock hotspot; taskbar must win.\n"
        "        self.mouse_router.handle_mouse_event(app, (0, 79, 24, 0, self.curses.BUTTON1_CLICKED))\n\n"
        "        app.handle_taskbar_click.assert_called_once_with(79, 24)\n",
    )
    replace_once(
        "tests/test_mouse_router.py",
        "        self.mouse_router.handle_mouse_event(app, (0, 79, 0, 0, self.curses.BUTTON1_CLICKED))\n\n"
        "        app.execute_action.assert_called_once_with(\"plugin:clock\")\n",
        "        self.mouse_router.handle_mouse_event(app, (0, 79, 24, 0, self.curses.BUTTON1_CLICKED))\n\n"
        "        app.execute_action.assert_called_once_with(\"plugin:clock\")\n",
    )
    replace_once(
        "tests/test_mouse_router.py",
        "    def test_handle_mouse_event_top_bar_free_space_can_route_taskbar(self):\n",
        "    def test_handle_mouse_event_bottom_bar_free_space_can_route_taskbar(self):\n",
    )
    replace_once(
        "tests/test_mouse_router.py",
        "        self.mouse_router.handle_mouse_event(app, (0, 40, 0, 0, self.curses.BUTTON1_CLICKED))\n\n"
        "        app.menu.handle_click.assert_not_called()\n"
        "        app.handle_taskbar_click.assert_called_once_with(40, 0)\n",
        "        self.mouse_router.handle_mouse_event(app, (0, 40, 24, 0, self.curses.BUTTON1_CLICKED))\n\n"
        "        app.menu.handle_click.assert_not_called()\n"
        "        app.handle_taskbar_click.assert_called_once_with(40, 24)\n",
    )

    replace_once(
        "tests/test_window_component.py",
        "        self.assertEqual((win.x, win.y, win.w, win.h), (0, 1, 120, 39))\n"
        "        self.assertEqual(win.y + win.h, 40)\n",
        "        self.assertEqual((win.x, win.y, win.w, win.h), (0, 0, 120, 39))\n"
        "        self.assertEqual(win.y + win.h, 39)\n",
    )
    replace_once(
        "tests/test_window_component.py",
        "        self.assertEqual((win.x, win.y), (50, 20))\n",
        "        self.assertEqual((win.x, win.y), (50, 19))\n",
    )
    replace_once(
        "tests/test_window_component.py",
        "        self.assertEqual(win.h, 35)  # clamped by term_h - y\n",
        "        self.assertEqual(win.h, 34)  # reserves the bottom taskbar row\n",
    )

    replace_once(
        "tests/test_classic_bottom_taskbar.py",
        '''    def test_global_menu_draws_on_bottom_and_opens_upward(self):
        menu = Menu({"File": [("Open", "open"), ("Exit", "exit")]})
        menu.active = True
        stdscr = types.SimpleNamespace(getmaxyx=lambda: (24, 80))

        with (
            mock.patch("retrotui.ui.menu.safe_addstr") as safe_addstr,
            mock.patch("retrotui.ui.menu.draw_box"),
        ):
            menu.draw_bar(stdscr, 80, frame_size=(24, 80))
            menu.draw_dropdown(stdscr, frame_size=(24, 80))

        self.assertEqual(menu.bar_row(), 23)
        self.assertTrue(any(call.args[1] == 23 for call in safe_addstr.call_args_list))
        rect = menu.get_dropdown_rect()
''',
        '''    def test_global_menu_draws_on_bottom_and_opens_upward(self):
        menu = Menu({"File": [("Open", "open"), ("Exit", "exit")]})
        menu.active = True
        stdscr = types.SimpleNamespace(
            getmaxyx=lambda: (24, 80),
            addnstr=mock.Mock(),
        )

        with mock.patch("retrotui.ui.menu.draw_box"):
            menu.draw_bar(stdscr, 80, frame_size=(24, 80))
            menu.draw_dropdown(stdscr, frame_size=(24, 80))

        self.assertEqual(menu.bar_row(), 23)
        self.assertTrue(
            any(call.args[0] == 23 for call in stdscr.addnstr.call_args_list)
        )
        rect = menu.get_dropdown_rect()
''',
    )
    replace_once(
        "tests/test_classic_bottom_taskbar.py",
        '''    def test_start_button_click_uses_bottom_row(self):
        menu = Menu({"File": [("Open", "open")]})
        stdscr = types.SimpleNamespace(getmaxyx=lambda: (24, 80))
        with mock.patch("retrotui.ui.menu.safe_addstr"):
            menu.draw_bar(stdscr, 80, frame_size=(24, 80))

        result = menu.handle_click(1, 23)
''',
        '''    def test_start_button_click_uses_bottom_row(self):
        menu = Menu({"File": [("Open", "open")]})
        stdscr = types.SimpleNamespace(
            getmaxyx=lambda: (24, 80),
            addnstr=mock.Mock(),
        )
        menu.draw_bar(stdscr, 80, frame_size=(24, 80))

        result = menu.handle_click(1, 23)
''',
    )

    replace_once(
        "tests/test_core_app.py",
        "        handled = app.handle_taskbar_click(2, 0)\n",
        "        handled = app.handle_taskbar_click(2, 29)\n",
    )
    replace_once(
        "tests/test_core_app.py",
        "        self.assertFalse(app.handle_taskbar_click(2, 0))  # taskbar row but no minimized\n",
        "        self.assertFalse(app.handle_taskbar_click(2, 29))  # taskbar row but no minimized\n",
    )

    replace_once(
        "tests/test_window_manager.py",
        "        self.assertTrue(wm.handle_taskbar_click(mx, 0))\n",
        "        self.assertTrue(wm.handle_taskbar_click(mx, 19))\n",
    )
    replace_once(
        "tests/test_window_manager.py",
        "    def test_taskbar_buttons_start_after_menu_in_unified_bar(self):\n",
        "    def test_taskbar_buttons_start_after_menu_in_classic_bar(self):\n",
    )
    replace_once(
        "tests/test_window_manager.py",
        "        self.assertEqual(buttons[0][0], 22)\n",
        "        self.assertEqual(buttons[0][0], 21)\n",
    )


if __name__ == "__main__":
    main()
