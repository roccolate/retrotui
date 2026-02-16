import importlib
import pathlib
import sys
import shutil
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


def _make_tmp_dir(name):
    root = pathlib.Path('tests') / f'_tmp_windows_logic_{name}'
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True, exist_ok=True)
    return root


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

    def test_notepad_load_permission_error_sets_placeholder_buffer(self):
        with mock.patch('builtins.open', side_effect=PermissionError('denied')):
            win = self.notepad_mod.NotepadWindow(0, 0, 40, 12, filepath='secret.txt')

        self.assertEqual(win.buffer, ['(Error reading file)'])
        self.assertFalse(win.modified)
        self.assertEqual(win.cursor_line, 0)
        self.assertEqual(win.cursor_col, 0)

    def test_filemanager_rebuild_content_permission_error_sets_message(self):
        with mock.patch('retrotui.apps.filemanager.os.listdir', side_effect=PermissionError):
            win = self.filemanager_mod.FileManagerWindow(0, 0, 40, 12, start_path='.')

        self.assertEqual(win.error_message, 'Permission denied')
        self.assertTrue(any('Permission denied' in row for row in win.content))

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

        win.handle_key('\u00f1')

        self.assertEqual(win.buffer[0], '\u00f1')
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

        dialog.handle_key('\u00e1')

        self.assertEqual(dialog.value, '\u00e1')
        self.assertEqual(dialog.cursor_pos, 1)

    def test_input_dialog_backspace_from_string(self):
        dialog = self.dialog_mod.InputDialog('Save As', 'Enter filename:', initial_value='abc', width=40)

        dialog.handle_key('\x7f')

        self.assertEqual(dialog.value, 'ab')
        self.assertEqual(dialog.cursor_pos, 2)

    def test_notepad_load_file_success_with_unicode_path_and_content(self):
        target = pathlib.Path('tests') / '_tmp_nota_\u00f1.txt'
        payload = 'linea 1\ncaf\u00e9\nsmile \U0001f642'
        target.write_text(payload, encoding='utf-8', newline='\n')
        try:
            win = self.notepad_mod.NotepadWindow(0, 0, 40, 12, filepath=str(target))
            self.assertEqual(win.buffer, payload.split('\n'))
            self.assertFalse(win.modified)
            self.assertEqual(win.cursor_line, 0)
            self.assertEqual(win.cursor_col, 0)
        finally:
            if target.exists():
                target.unlink()

    def test_notepad_load_large_file_keeps_all_lines(self):
        target = pathlib.Path('tests') / '_tmp_notepad_large.txt'
        lines = [f'line {i}' for i in range(2000)]
        target.write_text('\n'.join(lines), encoding='utf-8', newline='\n')
        try:
            win = self.notepad_mod.NotepadWindow(0, 0, 40, 12, filepath=str(target))
            self.assertEqual(len(win.buffer), 2000)
            self.assertEqual(win.buffer[0], 'line 0')
            self.assertEqual(win.buffer[-1], 'line 1999')
        finally:
            if target.exists():
                target.unlink()

    def test_notepad_save_as_with_long_unicode_path(self):
        filename = ('a' * 120) + '_\u00f1.txt'
        target = pathlib.Path('tests') / filename
        win = self.notepad_mod.NotepadWindow(0, 0, 40, 12)
        win.buffer = ['hola', 'mundo']
        try:
            result = win.save_as(str(target))
            self.assertTrue(result is True)
            self.assertEqual(win.filepath, str(target))
            self.assertEqual(win.title, f'Notepad - {filename}')
            self.assertEqual(target.read_text(encoding='utf-8'), 'hola\nmundo')
        finally:
            if target.exists():
                target.unlink()

    def test_notepad_editing_enter_backspace_delete_and_wrap_toggle(self):
        win = self.notepad_mod.NotepadWindow(0, 0, 40, 12)
        win.buffer = ['abcd', 'ef']
        win.cursor_line = 0
        win.cursor_col = 2

        win.handle_key(10)  # Enter
        self.assertEqual(win.buffer, ['ab', 'cd', 'ef'])
        self.assertEqual((win.cursor_line, win.cursor_col), (1, 0))

        win.handle_key(127)  # Backspace at col 0 merges with previous
        self.assertEqual(win.buffer, ['abcd', 'ef'])
        self.assertEqual((win.cursor_line, win.cursor_col), (0, 2))

        win.cursor_col = len(win.buffer[0])  # End of first line
        win.handle_key(330)  # KEY_DC merges next line
        self.assertEqual(win.buffer, ['abcdef'])

        win.view_left = 5
        win.handle_key(23)  # Ctrl+W
        self.assertTrue(win.wrap_mode)
        self.assertEqual(win.view_left, 0)

    def test_notepad_click_and_scroll_bounds(self):
        win = self.notepad_mod.NotepadWindow(0, 0, 40, 12)
        win.buffer = [f'row {i}' for i in range(60)]
        bx, by, _, _ = win.body_rect()

        win.handle_click(bx + 3, by + 4)
        self.assertEqual(win.cursor_line, 4)
        self.assertEqual(win.cursor_col, 3)

        win.view_top = 0
        win.scroll_up()
        self.assertEqual(win.view_top, 0)

        for _ in range(200):
            win.scroll_down()
        _, _, _, bh = win.body_rect()
        max_top = max(0, len(win.buffer) - (bh - 1))
        self.assertLessEqual(win.view_top, max_top)

    def test_filemanager_rebuild_content_oserror_sets_message(self):
        with mock.patch('retrotui.apps.filemanager.os.listdir', side_effect=OSError('io failure')):
            win = self.filemanager_mod.FileManagerWindow(0, 0, 40, 12, start_path='.')

        self.assertEqual(win.error_message, 'io failure')
        self.assertTrue(any('io failure' in row for row in win.content))

    def test_filemanager_rebuild_skips_entries_with_stat_errors(self):
        def fake_is_dir(path):
            return path.endswith('adir')

        def fake_is_file(path):
            return path.endswith('.txt')

        def fake_get_size(path):
            if path.endswith('bad.txt'):
                raise OSError('no stat')
            return 7

        with (
            mock.patch('retrotui.apps.filemanager.os.listdir', return_value=['good.txt', 'bad.txt', 'adir']),
            mock.patch('retrotui.apps.filemanager.os.path.isdir', side_effect=fake_is_dir),
            mock.patch('retrotui.apps.filemanager.os.path.isfile', side_effect=fake_is_file),
            mock.patch('retrotui.apps.filemanager.os.path.getsize', side_effect=fake_get_size),
        ):
            win = self.filemanager_mod.FileManagerWindow(0, 0, 40, 12, start_path='.')

        names = [entry.name for entry in win.entries]
        self.assertIn('good.txt', names)
        self.assertIn('adir', names)
        self.assertNotIn('bad.txt', names)

    def test_filemanager_activate_selected_for_file_and_directory(self):
        root = _make_tmp_dir('activate')
        try:
            file_path = root / 'data.txt'
            file_path.write_text('abc', encoding='utf-8', newline='\n')
            folder = root / 'docs'
            folder.mkdir()

            win = self.filemanager_mod.FileManagerWindow(0, 0, 50, 14, start_path=str(root))

            file_idx = next(i for i, e in enumerate(win.entries) if e.name == 'data.txt')
            dir_idx = next(i for i, e in enumerate(win.entries) if e.name == 'docs')

            win.selected_index = file_idx
            file_result = win.activate_selected()
            self.assertIsInstance(file_result, self.actions_mod.ActionResult)
            self.assertEqual(file_result.type, self.actions_mod.ActionType.OPEN_FILE)
            self.assertEqual(pathlib.Path(file_result.payload), file_path.resolve())

            win.selected_index = dir_idx
            dir_result = win.activate_selected()
            self.assertIsNone(dir_result)
            self.assertEqual(pathlib.Path(win.current_path), folder.resolve())
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_filemanager_navigate_parent_reselects_previous_directory(self):
        root = _make_tmp_dir('parent')
        try:
            child = root / 'child'
            child.mkdir()

            win = self.filemanager_mod.FileManagerWindow(0, 0, 50, 14, start_path=str(child))
            win.navigate_parent()

            self.assertEqual(pathlib.Path(win.current_path), root.resolve())
            self.assertEqual(win.entries[win.selected_index].name, 'child')
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_filemanager_key_navigation_and_scroll(self):
        root = _make_tmp_dir('nav')
        try:
            for i in range(30):
                (root / f'f{i:02}.txt').write_text('x', encoding='utf-8', newline='\n')

            win = self.filemanager_mod.FileManagerWindow(0, 0, 50, 14, start_path=str(root))
            win.handle_key(360)  # KEY_END
            self.assertEqual(win.selected_index, len(win.entries) - 1)

            win.handle_key(262)  # KEY_HOME
            self.assertEqual(win.selected_index, 0)

            win.handle_key(338)  # KEY_NPAGE
            self.assertGreater(win.selected_index, 0)

            current = win.selected_index
            win.handle_key(339)  # KEY_PPAGE
            self.assertLessEqual(win.selected_index, current)

            before = win.selected_index
            win.handle_scroll('down', steps=3)
            self.assertGreaterEqual(win.selected_index, before)
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
