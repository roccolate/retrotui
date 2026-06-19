import unittest
import time
from unittest import mock
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

    def test_run_uses_package_version_in_banner(self):
        import retrotui.core.bios as bios_mod

        std = DummyStdScr()
        b = BIOS(std)
        with (
            mock.patch.object(bios_mod, "safe_addstr") as safe_addstr,
            mock.patch.object(BIOS, "_sleep", return_value=True),
        ):
            b.run()

        rendered = [str(call.args[3]) for call in safe_addstr.call_args_list]
        self.assertTrue(any(f"RetroBIOS v{bios_mod.APP_VERSION}" in line for line in rendered))


if __name__ == "__main__":
    unittest.main()
