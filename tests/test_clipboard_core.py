import importlib
import subprocess
import unittest
from unittest import mock


class ClipboardCoreTests(unittest.TestCase):
    def setUp(self):
        self.clip = importlib.reload(importlib.import_module("retrotui.core.clipboard"))
        self.clip.clear_clipboard()

    def test_detect_backend_priority(self):
        with mock.patch.object(self.clip.shutil, "which", side_effect=lambda name: {
            "wl-copy": "/usr/bin/wl-copy",
            "wl-paste": "/usr/bin/wl-paste",
            "xclip": "/usr/bin/xclip",
            "xsel": "/usr/bin/xsel",
        }.get(name)):
            self.assertEqual(self.clip._detect_backend(), "wl")

        with mock.patch.object(self.clip.shutil, "which", side_effect=lambda name: {
            "xclip": "/usr/bin/xclip",
            "xsel": "/usr/bin/xsel",
        }.get(name)):
            self.assertEqual(self.clip._detect_backend(), "xclip")

        with mock.patch.object(self.clip.shutil, "which", side_effect=lambda name: {
            "xsel": "/usr/bin/xsel",
        }.get(name)):
            self.assertEqual(self.clip._detect_backend(), "xsel")

        with mock.patch.object(self.clip.shutil, "which", return_value=None):
            self.assertIsNone(self.clip._detect_backend())

    def test_system_copy_backends_and_errors(self):
        with (
            mock.patch.object(self.clip, "_detect_backend", return_value="wl"),
            mock.patch.object(
                self.clip.subprocess,
                "run",
                return_value=subprocess.CompletedProcess(args=["wl-copy"], returncode=0),
            ) as run_mock,
        ):
            self.assertTrue(self.clip._system_copy("abc"))
            run_mock.assert_called_once()
            self.assertEqual(run_mock.call_args.kwargs["input"], "abc")

        with (
            mock.patch.object(self.clip, "_detect_backend", return_value="xclip"),
            mock.patch.object(
                self.clip.subprocess,
                "run",
                return_value=subprocess.CompletedProcess(args=["xclip"], returncode=1),
            ),
        ):
            self.assertFalse(self.clip._system_copy("abc"))

        with (
            mock.patch.object(self.clip, "_detect_backend", return_value="xsel"),
            mock.patch.object(self.clip.subprocess, "run", side_effect=OSError("missing")),
        ):
            self.assertFalse(self.clip._system_copy("abc"))

        with mock.patch.object(self.clip, "_detect_backend", return_value=None):
            self.assertFalse(self.clip._system_copy("abc"))

    def test_system_paste_backends_and_errors(self):
        with (
            mock.patch.object(self.clip, "_detect_backend", return_value="wl"),
            mock.patch.object(
                self.clip.subprocess,
                "run",
                return_value=subprocess.CompletedProcess(args=["wl-paste"], returncode=0, stdout="wl"),
            ),
        ):
            self.assertEqual(self.clip._system_paste(), "wl")

        with (
            mock.patch.object(self.clip, "_detect_backend", return_value="xclip"),
            mock.patch.object(
                self.clip.subprocess,
                "run",
                return_value=subprocess.CompletedProcess(args=["xclip"], returncode=0, stdout="xc"),
            ),
        ):
            self.assertEqual(self.clip._system_paste(), "xc")

        with (
            mock.patch.object(self.clip, "_detect_backend", return_value="xsel"),
            mock.patch.object(
                self.clip.subprocess,
                "run",
                return_value=subprocess.CompletedProcess(args=["xsel"], returncode=1, stdout="bad"),
            ),
        ):
            self.assertIsNone(self.clip._system_paste())

        with (
            mock.patch.object(self.clip, "_detect_backend", return_value="xsel"),
            mock.patch.object(self.clip.subprocess, "run", side_effect=OSError("missing")),
        ):
            self.assertIsNone(self.clip._system_paste())

        with mock.patch.object(self.clip, "_detect_backend", return_value=None):
            self.assertIsNone(self.clip._system_paste())

    def test_copy_and_paste_text_with_sync_options(self):
        with mock.patch.object(self.clip, "_system_copy") as system_copy:
            copied = self.clip.copy_text("local", sync_system=True)
        self.assertEqual(copied, "local")
        system_copy.assert_called_once_with("local")
        self.assertTrue(self.clip.has_clipboard_text())
        self.assertEqual(self.clip.paste_text(sync_system=False), "local")

        with mock.patch.object(self.clip, "_system_paste", return_value="remote"):
            self.assertEqual(self.clip.paste_text(sync_system=True), "remote")
        self.assertEqual(self.clip.paste_text(sync_system=False), "remote")

        with mock.patch.object(self.clip, "_system_paste", return_value=None):
            self.assertEqual(self.clip.paste_text(sync_system=True), "remote")

    def test_clear_clipboard(self):
        self.clip.copy_text("abc", sync_system=False)
        self.assertTrue(self.clip.has_clipboard_text())
        self.clip.clear_clipboard()
        self.assertFalse(self.clip.has_clipboard_text())
        self.assertEqual(self.clip.paste_text(sync_system=False), "")


if __name__ == "__main__":
    unittest.main()
