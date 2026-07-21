"""Correct generated ICH/ECH expectations, then remove this helper."""

from pathlib import Path

root = Path(__file__).resolve().parents[1]
path = root / "tests/test_terminal_component.py"
text = path.read_text(encoding="utf-8")
replacements = {
    'self.assertEqual("".join(ch for ch, _ in active.get_row(0)), "A ABCD")':
        'self.assertEqual("".join(ch for ch, _ in active.get_row(0)), "A BCDE")',
    'self.assertEqual("".join(ch for ch, _ in active.get_row(0)), "A  BCD")':
        'self.assertEqual("".join(ch for ch, _ in active.get_row(0)), "A  CDE")',
}
for old, new in replacements.items():
    if text.count(old) != 1:
        raise RuntimeError(f"expected generated assertion once: {old}")
    text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
Path(__file__).unlink()
