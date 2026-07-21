import tempfile
import threading
import unittest
from pathlib import Path


class TrashTransactionTests(unittest.TestCase):
    def test_move_to_trash_and_restore_round_trip(self):
        from retrotui.core import trash_transaction as tx

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_dir = root / "source"
            trash_dir = root / "trash"
            source_dir.mkdir()
            trash_dir.mkdir()
            source = source_dir / "hello.txt"
            source.write_text("hello", encoding="utf-8")
            trashed = trash_dir / "hello.txt"

            moved = tx.transactional_move_to_trash(str(source), str(trashed))
            self.assertEqual(moved.phase, "completed")
            self.assertFalse(source.exists())
            self.assertEqual(trashed.read_text(encoding="utf-8"), "hello")
            stored_original = Path(tx.read_trash_metadata(str(trashed)))
            self.assertEqual(stored_original.name, source.name)
            self.assertTrue(stored_original.parent.samefile(source.parent))

            restored = tx.transactional_restore(str(trashed), str(source))
            self.assertEqual(restored.phase, "completed")
            self.assertEqual(source.read_text(encoding="utf-8"), "hello")
            self.assertFalse(trashed.exists())
            self.assertFalse(Path(tx.trash_metadata_path(str(trashed))).exists())

    def test_cancel_before_commit_preserves_source_and_cleans_journal(self):
        from retrotui.core import trash_transaction as tx
        from retrotui.core.file_transfer import TransferCancelled

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trash_dir = root / "trash"
            trash_dir.mkdir()
            source = root / "payload.bin"
            source.write_bytes(b"x" * 1024)
            destination = trash_dir / "payload.bin"
            cancel = threading.Event()
            cancel.set()

            with self.assertRaises(TransferCancelled):
                tx.transactional_move_to_trash(
                    str(source),
                    str(destination),
                    cancel_event=cancel,
                )

            self.assertTrue(source.exists())
            self.assertFalse(destination.exists())
            self.assertFalse(Path(tx.trash_metadata_path(str(destination))).exists())
            self.assertFalse((trash_dir / ".retrotui-transactions").exists())

    def test_recovery_rolls_back_duplicate_destination_and_preserves_source(self):
        from retrotui.core import trash_transaction as tx

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trash_dir = root / "trash"
            trash_dir.mkdir()
            source = root / "original.txt"
            destination = trash_dir / "original.txt"
            source.write_text("source", encoding="utf-8")
            destination.write_text("copy", encoding="utf-8")
            tx.write_trash_metadata(str(destination), str(source))
            journal = tx._new_journal(
                "trash",
                source=str(source),
                destination=str(destination),
                metadata=tx.trash_metadata_path(str(destination)),
            )
            tx._write_journal(str(trash_dir), journal)

            self.assertEqual(tx.recover_trash_transactions(str(trash_dir)), [])
            self.assertEqual(source.read_text(encoding="utf-8"), "source")
            self.assertFalse(destination.exists())
            self.assertFalse(Path(tx.trash_metadata_path(str(destination))).exists())
            self.assertFalse((trash_dir / ".retrotui-transactions").exists())

    def test_deferred_permanent_delete_is_resumed_by_recovery(self):
        from retrotui.core import trash_transaction as tx

        with tempfile.TemporaryDirectory() as tmp:
            trash_dir = Path(tmp) / "trash"
            trash_dir.mkdir()
            target = trash_dir / "tree"
            target.mkdir()
            for index in range(5):
                (target / f"{index}.bin").write_bytes(b"x" * 32)
            cancel = threading.Event()

            def on_progress(progress):
                if progress.phase == "deleting" and progress.files_done >= 1:
                    cancel.set()

            result = tx.transactional_permanent_delete(
                str(target),
                str(trash_dir),
                cancel_event=cancel,
                progress_callback=on_progress,
            )
            self.assertEqual(result.phase, "deferred")
            self.assertFalse(target.exists())
            self.assertTrue((trash_dir / ".retrotui-transactions").is_dir())
            self.assertTrue((trash_dir / ".retrotui-pending-delete").is_dir())

            self.assertEqual(tx.recover_trash_transactions(str(trash_dir)), [])
            self.assertFalse((trash_dir / ".retrotui-transactions").exists())
            self.assertFalse((trash_dir / ".retrotui-pending-delete").exists())
            self.assertEqual(tx.list_trash_items(str(trash_dir)), [])

    def test_restore_never_replaces_existing_target(self):
        from retrotui.core import trash_transaction as tx

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trash_dir = root / "trash"
            trash_dir.mkdir()
            trashed = trash_dir / "item.txt"
            target = root / "item.txt"
            trashed.write_text("trash", encoding="utf-8")
            target.write_text("existing", encoding="utf-8")
            tx.write_trash_metadata(str(trashed), str(target))

            with self.assertRaises(FileExistsError):
                tx.transactional_restore(str(trashed), str(target))

            self.assertEqual(target.read_text(encoding="utf-8"), "existing")
            self.assertEqual(trashed.read_text(encoding="utf-8"), "trash")

    def test_listing_excludes_metadata_journals_and_pending_cleanup(self):
        from retrotui.core import trash_transaction as tx

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "visible.txt").write_text("x", encoding="utf-8")
            (root / "visible.txt.trashinfo").write_text("{}", encoding="utf-8")
            (root / ".retrotui-transactions").mkdir()
            (root / ".retrotui-pending-delete").mkdir()
            (root / ".visible.txt.retrotui-abc.part").write_text("partial", encoding="utf-8")

            self.assertEqual(
                tx.list_trash_items(str(root)),
                [str(root / "visible.txt")],
            )


if __name__ == "__main__":
    unittest.main()
