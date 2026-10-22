"""Run standalone core tests and simulated observer checks; no live game test."""
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    if sys.argv[1:]:
        raise SystemExit('Usage: python -B tools/test_offline.py')
    suite = unittest.TestSuite()
    for folder in (ROOT / 'tests', ROOT / 'experiments' / 'observer-input'):
        suite.addTests(unittest.TestLoader().discover(str(folder), pattern='test_*.py'))
    started = time.perf_counter()
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    print(f'Standalone offline verification: {time.perf_counter() - started:.3f}s')
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
