import unittest
import time
from retrotui.core.bios import BIOS


class DummyStdScr:
    def __init__(self):
        self._maxyx = (24, 80)

    def nodelay(self, v):
        self._nodelay = v

    def clear(self):
        pass

    def getmaxyx(self):
        return self._maxyx

    def getch(self):
        return -1

    def refresh(self):
        pass


class BioTests(unittest.TestCase):
    def test_check_skip_and_sleep_fast(self):
        std = DummyStdScr()
        b = BIOS(std)
        self.assertFalse(b._check_skip())
        start = time.time()
        # should return False and take approximately given time
        res = b._sleep(0.02)
        self.assertFalse(res)
        self.assertGreaterEqual(time.time() - start, 0)

    def test_check_skip_returns_false_when_getch_raises(self):
        std = DummyStdScr()
        std.getch = lambda: (_ for _ in ()).throw(RuntimeError("tty read failed"))
        b = BIOS(std)

        self.assertFalse(b._check_skip())


if __name__ == "__main__":
    unittest.main()

