import importlib
import pathlib
import sys
import types
import unittest
from unittest import mock


def _install_fake_curses():
    fake = types.ModuleType('curses')
    fake.KEY_LEFT = 260
    fake.KEY_RIGHT = 261
    fake.KEY_UP = 259
    fake.KEY_DOWN = 258
    fake.KEY_ENTER = 343
    fake.KEY_HOME = 262
    fake.KEY_END = 360
    fake.KEY_PPAGE = 339
    fake.KEY_NPAGE = 338
    fake.KEY_BACKSPACE = 263
    fake.KEY_DC = 330
    fake.A_BOLD = 1
    fake.A_REVERSE = 2
    fake.error = Exception
    fake.color_pair = lambda _: 0
    return fake


class WindowLogicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_curses = sys.modules.get('curses')
        sys.modules['curses'] = _install_fake_curses()
        for mod_name in (
            'retrotui.constants',
            'retrotui.utils',
            'retrotui.ui.dialog',
            'retrotui.ui.menu',
            'retrotui.ui.window',
            'retrotui.apps.notepad',
            'retrotui.apps.filemanager',
            'retrotui.core.actions',
        ):
            sys.modules.pop(mod_name, None)

        cls.actions_mod = importlib.import_module('retrotui.core.actions')
        cls.dialog_mod = importlib.import_module('retrotui.ui.dialog')
        cls.window_mod = importlib.import_module('retrotui.ui.window')
        cls.notepad_mod = importlib.import_module('retrotui.apps.notepad')
        cls.filemanager_mod = importlib.import_module('retrotui.apps.filemanager')

    @classmethod
    def tearDownClass(cls):
        for mod_name in (
            'retrotui.constants',
            'retrotui.utils',
            'retrotui.ui.dialog',
            'retrotui.ui.menu',
            'retrotui.ui.window',
            'retrotui.apps.notepad',
            'retrotui.apps.filemanager',
            'retrotui.core.actions',
        ):
            sys.modules.pop(mod_name, None)
        if cls._prev_curses is not None:
            sys.modules['curses'] = cls._prev_curses
        else:
            sys.modules.pop('curses', None)

    def test_notepad_save_without_filepath_requests_save_as(self):
        win = self.notepad_mod.NotepadWindow(0, 0, 40, 12)
        result = win._save_file()

        self.assertIsInstance(result, self.actions_mod.ActionResult)
        self.assertEqual(result.type, self.actions_mod.ActionType.REQUEST_SAVE_AS)

    def test_notepad_save_success_writes_buffer(self):
        win = self.notepad_mod.NotepadWindow(0, 0, 40, 12)
        win.buffer = ['line1', 'line2']
        win.modified = True
        target = pathlib.Path('tests') / '_tmp_notepad_save.txt'
        if target.exists():
            target.unlink()
        try:
            win.filepath = str(target)
            result = win._save_file()

            self.assertTrue(result is True)
            self.assertEqual(target.read_text(encoding='utf-8'), 'line1\nline2')
            self.assertFalse(win.modified)
        finally:
            if target.exists():
                target.unlink()

    def test_notepad_save_error_returns_typed_error(self):
        win = self.notepad_mod.NotepadWindow(0, 0, 40, 12)
        win.filepath = '/unwritable/path/note.txt'
        with mock.patch('builtins.open', side_effect=OSError('disk full')):
            result = win._save_file()

        self.assertIsInstance(result, self.actions_mod.ActionResult)
        self.assertEqual(result.type, self.actions_mod.ActionType.SAVE_ERROR)
        self.assertIn('disk full', result.payload)

    def test_file_entry_ascii_icons(self):
        dir_entry = self.filemanager_mod.FileEntry(
            'docs',
            True,
            '/tmp/docs',
            use_unicode=False,
        )
        file_entry = self.filemanager_mod.FileEntry(
            'readme.txt',
            False,
            '/tmp/readme.txt',
            size=15,
            use_unicode=False,
        )

        self.assertTrue(dir_entry.display_text.startswith('  [D]'))
        self.assertTrue(file_entry.display_text.startswith('  [F]'))

    def test_hidden_window_draw_skips_rendering(self):
        win = self.window_mod.Window('Hidden', 0, 0, 20, 8)
        win.visible = False
        win.draw_frame = mock.Mock()
        win.draw_body = mock.Mock()

        win.draw(None)

        win.draw_frame.assert_not_called()
        win.draw_body.assert_not_called()

    def test_notepad_accepts_unicode_string_input(self):
        win = self.notepad_mod.NotepadWindow(0, 0, 40, 12)

        win.handle_key('ñ')

        self.assertEqual(win.buffer[0], 'ñ')
        self.assertEqual(win.cursor_col, 1)

    def test_notepad_ctrl_s_string_key_triggers_save(self):
        win = self.notepad_mod.NotepadWindow(0, 0, 40, 12)
        win._save_file = mock.Mock(return_value=True)

        win.handle_key('\x13')  # Ctrl+S from get_wch

        win._save_file.assert_called_once()

    def test_filemanager_string_h_toggles_hidden(self):
        win = self.filemanager_mod.FileManagerWindow(0, 0, 40, 12, start_path='.')
        self.assertFalse(win.show_hidden)

        win.handle_key('h')

        self.assertTrue(win.show_hidden)

    def test_input_dialog_accepts_unicode_string_input(self):
        dialog = self.dialog_mod.InputDialog('Save As', 'Enter filename:', width=40)

        dialog.handle_key('á')

        self.assertEqual(dialog.value, 'á')
        self.assertEqual(dialog.cursor_pos, 1)

    def test_input_dialog_backspace_from_string(self):
        dialog = self.dialog_mod.InputDialog('Save As', 'Enter filename:', initial_value='abc', width=40)

        dialog.handle_key('\x7f')

        self.assertEqual(dialog.value, 'ab')
        self.assertEqual(dialog.cursor_pos, 2)


if __name__ == '__main__':
    unittest.main()
