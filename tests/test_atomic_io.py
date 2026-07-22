"""Regression tests for secure atomic text publication."""
import os
import stat
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from retrotui.atomic_io import atomic_write_text
from retrotui import utils


class AtomicWriteTextTests(unittest.TestCase):
    def test_utils_reexports_hardened_implementation(self):
        self.assertIs(utils.atomic_write_text, atomic_write_text)

    def test_replaces_content_and_returns_target(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "document.txt"
            target.write_text("before", encoding="utf-8")

            result = atomic_write_text(target, "after\n")

            self.assertEqual(result, target)
            self.assertEqual(target.read_text(encoding="utf-8"), "after\n")
            self.assertFalse(list(target.parent.glob(f".{target.name}.retrotui-*.tmp")))

    @unittest.skipUnless(os.name == "posix", "POSIX permission bits required")
    def test_preserves_existing_regular_file_mode(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "private.txt"
            target.write_text("before", encoding="utf-8")
            os.chmod(target, 0o640)

            atomic_write_text(target, "after")

            mode = stat.S_IMODE(os.stat(target, follow_symlinks=False).st_mode)
            self.assertEqual(mode, 0o640)

    def test_does_not_follow_predictable_temp_symlink(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "settings.toml"
            victim = root / "victim.txt"
            predictable_temp = target.with_name(target.name + ".tmp")
            victim.write_text("unchanged", encoding="utf-8")
            try:
                os.symlink(victim, predictable_temp)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlinks unavailable: {exc}")

            atomic_write_text(target, "safe")

            self.assertEqual(target.read_text(encoding="utf-8"), "safe")
            self.assertEqual(victim.read_text(encoding="utf-8"), "unchanged")
            self.assertTrue(predictable_temp.is_symlink())

    def test_concurrent_writers_publish_only_complete_payloads(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "state.txt"
            payloads = ("A" * 200_000, "B" * 200_000)
            barrier = threading.Barrier(len(payloads) + 1)
            errors = []

            def write_payload(payload):
                barrier.wait()
                try:
                    atomic_write_text(target, payload)
                except Exception as exc:  # pragma: no cover - assertion captures diagnostics
                    errors.append(exc)

            threads = [
                threading.Thread(target=write_payload, args=(payload,))
                for payload in payloads
            ]
            for thread in threads:
                thread.start()
            barrier.wait()
            for thread in threads:
                thread.join(timeout=5)

            self.assertFalse(any(thread.is_alive() for thread in threads))
            self.assertEqual(errors, [])
            self.assertIn(target.read_text(encoding="utf-8"), payloads)
            self.assertFalse(list(target.parent.glob(f".{target.name}.retrotui-*.tmp")))

    def test_replace_failure_keeps_old_target_and_cleans_temp(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "document.txt"
            target.write_text("before", encoding="utf-8")

            with mock.patch(
                "retrotui.atomic_io.os.replace",
                side_effect=OSError("simulated publish failure"),
            ):
                with self.assertRaisesRegex(OSError, "simulated publish failure"):
                    atomic_write_text(target, "after")

            self.assertEqual(target.read_text(encoding="utf-8"), "before")
            self.assertFalse(list(target.parent.glob(f".{target.name}.retrotui-*.tmp")))
            self.assertFalse(target.with_name(target.name + ".tmp").exists())

    def test_flushes_file_before_replace(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "document.txt"
            real_fsync = os.fsync
            synced_fds = []

            def record_fsync(fd):
                synced_fds.append(fd)
                return real_fsync(fd)

            with mock.patch("retrotui.atomic_io.os.fsync", side_effect=record_fsync):
                atomic_write_text(target, "durable")

            self.assertTrue(synced_fds)
            self.assertEqual(target.read_text(encoding="utf-8"), "durable")


if __name__ == "__main__":
    unittest.main()
