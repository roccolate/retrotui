import types
import unittest
from unittest import mock

from retrotui.apps.control_panel import ControlPanelWindow
from retrotui.core.actions import ActionType


class ControlPanelCheckboxClickTests(unittest.TestCase):
    def setUp(self):
        self.app = types.SimpleNamespace(
            theme_name="win31",
            default_show_hidden=False,
            default_word_wrap=False,
            show_welcome=True,
            config=types.SimpleNamespace(
                sunday_first=False,
                show_welcome=True,
            ),
            apply_theme=mock.Mock(),
            apply_preferences=mock.Mock(),
            persist_config=mock.Mock(),
        )
        self.window = ControlPanelWindow(4, 3, 60, 18, self.app)

    def _right_pane_origin(self):
        bx, by, _bw, _bh = self.window.body_rect()
        return bx + 20, by + 1

    def test_click_show_hidden_checkbox_toggles_and_persists(self):
        self.window.selected_cat = 1
        rx, ry = self._right_pane_origin()

        result = self.window.handle_click(rx, ry + 2)

        self.assertTrue(self.window.show_hidden)
        self.app.apply_preferences.assert_called_once_with(show_hidden=True)
        self.app.persist_config.assert_called_once_with()
        self.assertEqual(result.type, ActionType.REFRESH)

    def test_click_word_wrap_checkbox_toggles_and_persists(self):
        self.window.selected_cat = 1
        rx, ry = self._right_pane_origin()

        result = self.window.handle_click(rx + 5, ry + 4)

        self.assertTrue(self.window.word_wrap_default)
        self.app.apply_preferences.assert_called_once_with(word_wrap_default=True)
        self.app.persist_config.assert_called_once_with()
        self.assertEqual(result.type, ActionType.REFRESH)

    def test_click_sunday_first_checkbox_toggles_and_updates_windows(self):
        self.window.selected_cat = 2
        rx, ry = self._right_pane_origin()

        result = self.window.handle_click(rx + 8, ry + 2)

        self.assertTrue(self.window.sunday_first)
        self.app.apply_preferences.assert_called_once_with(
            sunday_first=True,
            apply_to_open_windows=True,
        )
        self.app.persist_config.assert_called_once_with()
        self.assertEqual(result.type, ActionType.REFRESH)

    def test_click_welcome_checkbox_uses_rendered_hitbox(self):
        self.window.selected_cat = 3
        rx, ry = self._right_pane_origin()

        result = self.window.handle_click(rx + 4, ry + 2)

        self.assertFalse(self.window.show_welcome)
        self.app.apply_preferences.assert_called_once_with(
            show_welcome=False,
            apply_to_open_windows=True,
        )
        self.app.persist_config.assert_called_once_with()
        self.assertEqual(result.type, ActionType.REFRESH)

    def test_click_outside_rendered_checkbox_label_does_not_toggle(self):
        self.window.selected_cat = 1
        rx, ry = self._right_pane_origin()
        label = "[ ] Show hidden files"

        result = self.window.handle_click(rx + len(label), ry + 2)

        self.assertFalse(self.window.show_hidden)
        self.app.apply_preferences.assert_not_called()
        self.app.persist_config.assert_not_called()
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
