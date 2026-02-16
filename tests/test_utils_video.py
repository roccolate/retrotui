import importlib
import sys
import types
import unittest
from unittest import mock


class PlayAsciiVideoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._prev_curses = sys.modules.get('curses')
        fake = types.ModuleType('curses')
        fake.error = Exception
        fake.def_prog_mode = lambda: None
        fake.endwin = lambda: None
        fake.reset_prog_mode = lambda: None
        sys.modules['curses'] = fake
        for mod_name in ('retrotui.constants', 'retrotui.utils'):
            sys.modules.pop(mod_name, None)
        cls.utils = importlib.import_module('retrotui.utils')

    @classmethod
    def tearDownClass(cls):
        for mod_name in ('retrotui.constants', 'retrotui.utils'):
            sys.modules.pop(mod_name, None)
        if cls._prev_curses is not None:
            sys.modules['curses'] = cls._prev_curses
        else:
            sys.modules.pop('curses', None)

    def test_no_backend_returns_error(self):
        with mock.patch('retrotui.utils.shutil.which', return_value=None):
            success, error = self.utils.play_ascii_video(None, 'demo.mp4')

        self.assertFalse(success)
        self.assertIn('mpv', error)
        self.assertIn('mplayer', error)

    def test_failed_backends_return_error(self):
        result = types.SimpleNamespace(returncode=1)

        def which(name):
            return '/usr/bin/mpv' if name == 'mpv' else None

        with mock.patch('retrotui.utils.shutil.which', side_effect=which), \
                mock.patch('retrotui.utils.curses.def_prog_mode'), \
                mock.patch('retrotui.utils.curses.endwin'), \
                mock.patch('retrotui.utils.curses.reset_prog_mode'), \
                mock.patch('retrotui.utils.subprocess.run', return_value=result) as run_mock, \
                mock.patch('retrotui.utils.time.time', side_effect=[0.0, 0.1, 1.0, 1.1]):
            success, error = self.utils.play_ascii_video(None, 'demo.mp4')

        self.assertFalse(success)
        self.assertIn('Backend probado', error)
        self.assertIn('mpv', error)
        self.assertEqual(run_mock.call_count, 2)

    def test_successful_backend_returns_ok(self):
        ok_result = types.SimpleNamespace(returncode=0)

        def which(name):
            return '/usr/bin/mpv' if name == 'mpv' else None

        with mock.patch('retrotui.utils.shutil.which', side_effect=which), \
                mock.patch('retrotui.utils.curses.def_prog_mode'), \
                mock.patch('retrotui.utils.curses.endwin'), \
                mock.patch('retrotui.utils.curses.reset_prog_mode'), \
                mock.patch('retrotui.utils.subprocess.run', return_value=ok_result):
            success, error = self.utils.play_ascii_video(None, 'demo.mp4')

        self.assertTrue(success)
        self.assertIsNone(error)

    def test_mpv_command_includes_overlay_and_subtitle_args(self):
        ok_result = types.SimpleNamespace(returncode=0)

        def which(name):
            return '/usr/bin/mpv' if name == 'mpv' else None

        with mock.patch('retrotui.utils.shutil.which', side_effect=which), \
                mock.patch('retrotui.utils.curses.def_prog_mode'), \
                mock.patch('retrotui.utils.curses.endwin'), \
                mock.patch('retrotui.utils.curses.reset_prog_mode'), \
                mock.patch('retrotui.utils.subprocess.run', return_value=ok_result) as run_mock:
            success, error = self.utils.play_ascii_video(None, 'demo.mp4', subtitle_path='captions.srt')

        self.assertTrue(success)
        self.assertIsNone(error)
        called_cmd = run_mock.call_args.args[0]
        self.assertIn('--vo=tct', called_cmd)
        self.assertIn('--osd-level=1', called_cmd)
        self.assertIn('--sub-file=', ' '.join(called_cmd))


if __name__ == '__main__':
    unittest.main()
