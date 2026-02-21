"""Run unittest discovery and write verbose output to tests_output.txt."""
import unittest
from pathlib import Path

out = Path('tests_output.txt')
loader = unittest.TestLoader()
suite = loader.discover('tests')
with out.open('w', encoding='utf-8') as fh:
    runner = unittest.TextTestRunner(stream=fh, verbosity=2)
    result = runner.run(suite)
    fh.write('\nEXIT_CODE:%s\n' % (0 if result.wasSuccessful() else 1))
    print('Wrote', out)
