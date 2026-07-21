#!/usr/bin/env python3
"""Convert embedded patch payload delimiters without importing the preparer."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = root / "tools" / "prepare_cooperative_file_transfers.py"
target = root / "tools" / "prepare_cooperative_file_transfers_fixed.py"
lines = source.read_text(encoding="utf-8").splitlines(keepends=True)

known_starts = (
    '"""def perform_copy(',
    '"""    def copy_selected(',
    '"""    def _dual_copy_move_between_panes(',
    '"""    @staticmethod',
    '"""    def poll_background_operation',
)

out = []
in_payload = False
for line in lines:
    stripped = line.lstrip()
    if not in_payload:
        starts_payload = False
        if ', """\\' in line:
            line = line.replace('"""\\', "r'''", 1)
            starts_payload = True
        elif stripped.startswith(known_starts):
            line = line.replace('"""', "r'''", 1)
            starts_payload = True
        elif stripped.strip() == '"""':
            line = line.replace('"""', "r'''", 1)
            starts_payload = True
        elif 'text[:start] + """    def _run_file_operation_with_progress' in line:
            line = line.replace('"""', "r'''", 1)
            starts_payload = True
        elif 'dialog_text[:dialog_start] + """class ProgressDialog:' in line:
            line = line.replace('"""', "r'''", 1)
            starts_payload = True
        in_payload = starts_payload
        out.append(line)
        continue

    closing = stripped.startswith('""")') or stripped.startswith('""",') or stripped.startswith('""" +')
    if closing:
        line = line.replace('"""', "'''", 1)
        in_payload = False
    out.append(line)

if in_payload:
    raise RuntimeError("unterminated embedded payload while repairing preparer")

target.write_text(''.join(out), encoding="utf-8")
print(target)
