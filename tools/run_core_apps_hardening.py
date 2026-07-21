#!/usr/bin/env python3
"""Run the temporary core-app hardening applicator with robust test insertion."""

from pathlib import Path

import apply_core_apps_hardening as implementation


def insert_test_method(path: str, block: str) -> None:
    if path == "tests/test_retronet.py":
        block = block.replace(
            '        mock_urlopen.side_effect = ssl.SSLError("certificate verify failed")\n',
            '        self.win._worker_scope.cancel()\n'
            '        mock_urlopen.reset_mock()\n'
            '        mock_urlopen.side_effect = ssl.SSLError("certificate verify failed")\n',
            1,
        )

    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    marker = '\n\nif __name__ == "__main__":\n'
    if marker in text:
        updated = text.replace(marker, block + marker, 1)
    else:
        updated = text.rstrip() + block + "\n"
    file_path.write_text(updated, encoding="utf-8")


implementation.insert_before_final_main = insert_test_method
implementation.main()
