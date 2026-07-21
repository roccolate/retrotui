#!/usr/bin/env python3
"""Apply atomic no-replace semantics to cooperative transfer commits."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path, old, new):
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise RuntimeError(f"{path}: expected exactly one replacement target")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "retrotui/core/file_transfer.py",
    "from __future__ import annotations\n\nimport errno\n",
    "from __future__ import annotations\n\nimport ctypes\nimport errno\n",
)
replace_once(
    "retrotui/core/file_transfer.py",
    "import stat\nimport tempfile\n",
    "import stat\nimport sys\nimport tempfile\n",
)
replace_once(
    "retrotui/core/file_transfer.py",
    '''def _commit_filelike(temp_path: str, dest: str) -> None:
    # Reserve the final name without overwriting a path that appeared after the
    # initial validation, then atomically replace our own placeholder.
    fd = os.open(dest, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    try:
        os.replace(temp_path, dest)
    except Exception:
        try:
            os.unlink(dest)
        except OSError:
            pass
        raise


def _commit_directory(temp_path: str, dest: str) -> None:
    if os.path.lexists(dest):
        raise FileExistsError(dest)
    os.rename(temp_path, dest)
''',
    '''def _rename_noreplace(source: str, dest: str) -> None:
    """Atomically rename *source* without replacing an existing destination.

    Windows already gives ``os.rename`` no-replace semantics. Linux uses
    ``renameat2(RENAME_NOREPLACE)`` when libc exposes it. Other POSIX hosts
    retain a checked fallback; that fallback is safe for normal operation but
    cannot close the final cross-process race without a platform-specific API.
    """

    if os.name == "nt":
        os.rename(source, dest)
        return

    if sys.platform.startswith("linux"):
        try:
            renameat2 = ctypes.CDLL(None, use_errno=True).renameat2
        except AttributeError:
            renameat2 = None
        if renameat2 is not None:
            renameat2.argtypes = (
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_uint,
            )
            renameat2.restype = ctypes.c_int
            result = renameat2(
                -100,
                os.fsencode(source),
                -100,
                os.fsencode(dest),
                1,
            )
            if result == 0:
                return
            error_number = ctypes.get_errno()
            unsupported = {errno.ENOSYS, errno.EINVAL, errno.EOPNOTSUPP}
            if error_number not in unsupported:
                raise OSError(error_number, os.strerror(error_number), dest)

    if os.path.lexists(dest):
        raise FileExistsError(dest)
    os.rename(source, dest)


def _commit_filelike(temp_path: str, dest: str) -> None:
    _rename_noreplace(temp_path, dest)


def _commit_directory(temp_path: str, dest: str) -> None:
    _rename_noreplace(temp_path, dest)
''',
)
replace_once(
    "retrotui/core/file_transfer.py",
    '''def _try_atomic_move(source: str, dest: str) -> bool:
    try:
        os.rename(source, dest)
        return True
    except OSError as exc:
        if exc.errno == errno.EXDEV:
            return False
        raise
''',
    '''def _try_atomic_move(source: str, dest: str) -> bool:
    try:
        _rename_noreplace(source, dest)
        return True
    except OSError as exc:
        if exc.errno == errno.EXDEV:
            return False
        raise
''',
)
replace_once(
    "tests/test_file_transfer.py",
    '''    def test_atomic_move_does_not_copy_payload(self):
''',
    '''    def test_atomic_no_replace_preserves_existing_destination(self):
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
''',
)
print("atomic no-replace refinement applied")
