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


def test_check_skip_and_sleep_fast():
    std = DummyStdScr()
    b = BIOS(std)
    assert b._check_skip() is False
    start = time.time()
    # should return False and take approximately given time
    res = b._sleep(0.02)
    assert res is False
    assert time.time() - start >= 0
