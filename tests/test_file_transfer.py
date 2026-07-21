import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock


class CooperativeFileTransferTests(unittest.TestCase):
    def test_copy_file_reports_progress_and_commits_complete_payload(self):
        from retrotui.core import file_transfer as transfer

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.bin"
            dest = root / "dest.bin"
            payload = (b"retro-tui-" * 300_000) + b"done"
            source.write_bytes(payload)
            updates = []

            result = transfer.cooperative_copy(
                source,
                dest,
                progress_callback=updates.append,
                chunk_size=64 * 1024,
            )

            self.assertEqual(dest.read_bytes(), payload)
            self.assertEqual(result.phase, "completed")
            self.assertEqual(result.bytes_done, len(payload))
            self.assertEqual(result.total_bytes, len(payload))
            self.assertTrue(any(item.phase == "copying" for item in updates))
            self.assertEqual(updates[-1].phase, "completed")

    def test_cancelled_copy_removes_partial_destination_and_temp_file(self):
        from retrotui.core import file_transfer as transfer

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "large.bin"
            dest = root / "dest.bin"
            source.write_bytes(b"x" * (3 * 1024 * 1024))
            cancel_event = threading.Event()

            def on_progress(progress):
                if progress.bytes_done >= 64 * 1024:
                    cancel_event.set()

            with self.assertRaises(transfer.TransferCancelled):
                transfer.cooperative_copy(
                    source,
                    dest,
                    cancel_event=cancel_event,
                    progress_callback=on_progress,
                    chunk_size=64 * 1024,
                )

            self.assertFalse(dest.exists())
            self.assertEqual(
                [path for path in root.iterdir() if ".retrotui-" in path.name],
                [],
            )

    def test_directory_copy_preserves_nested_files(self):
        from retrotui.core import file_transfer as transfer

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "tree"
            dest = root / "tree-copy"
            (source / "nested").mkdir(parents=True)
            (source / "a.txt").write_text("alpha", encoding="utf-8")
            (source / "nested" / "b.txt").write_text("beta", encoding="utf-8")

            result = transfer.cooperative_copy(source, dest, chunk_size=2)

            self.assertEqual((dest / "a.txt").read_text(encoding="utf-8"), "alpha")
            self.assertEqual(
                (dest / "nested" / "b.txt").read_text(encoding="utf-8"),
                "beta",
            )
            self.assertEqual(result.files_done, 2)
            self.assertEqual(result.total_files, 2)

    def test_cross_filesystem_move_rolls_back_destination_when_source_cleanup_fails(self):
        from retrotui.core import file_transfer as transfer

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.txt"
            dest = root / "dest.txt"
            source.write_text("payload", encoding="utf-8")

            with (
                mock.patch.object(transfer, "_try_atomic_move", return_value=False),
                mock.patch.object(
                    transfer,
                    "_remove_source_after_copy",
                    side_effect=OSError("cannot remove source"),
                ),
            ):
                with self.assertRaisesRegex(OSError, "rolled back"):
                    transfer.cooperative_move(source, dest)

            self.assertTrue(source.exists())
            self.assertFalse(dest.exists())

    def test_atomic_no_replace_preserves_existing_destination(self):
        from retrotui.core import file_transfer as transfer

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.txt"
            dest = root / "dest.txt"
            source.write_text("new payload", encoding="utf-8")
            dest.write_text("existing payload", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                transfer._rename_noreplace(source, dest)

            self.assertEqual(source.read_text(encoding="utf-8"), "new payload")
            self.assertEqual(dest.read_text(encoding="utf-8"), "existing payload")

    def test_atomic_move_does_not_copy_payload(self):
        from retrotui.core import file_transfer as transfer

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.txt"
            dest = root / "dest.txt"
            source.write_text("payload", encoding="utf-8")

            with mock.patch.object(
                transfer,
                "cooperative_copy",
                side_effect=AssertionError("copy fallback should not run"),
            ):
                result = transfer.cooperative_move(source, dest)

            self.assertFalse(source.exists())
            self.assertEqual(dest.read_text(encoding="utf-8"), "payload")
            self.assertEqual(result.phase, "completed")


if __name__ == "__main__":
    unittest.main()
