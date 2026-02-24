import unittest

from retrotui.core.profile_compare import compare_profiles
from retrotui.core.profile_metrics import BaselineProfile


class ProfileCompareTests(unittest.TestCase):
    def test_compare_profiles_calculates_numeric_deltas(self):
        before = BaselineProfile(
            boot_ms=100.0,
            redraw_ratio=0.200,
            draw_ms=20.0,
            dispatch_ms=10.0,
            input_wait_ms=900.0,
            loops=100,
            redraws=20,
            events=15,
        )
        after = BaselineProfile(
            boot_ms=80.0,
            redraw_ratio=0.150,
            draw_ms=16.0,
            dispatch_ms=8.0,
            input_wait_ms=940.0,
            loops=120,
            redraws=18,
            events=17,
        )

        delta = compare_profiles(before, after)

        self.assertEqual(delta.boot_ms_delta, -20.0)
        self.assertAlmostEqual(delta.redraw_ratio_delta, -0.05, places=6)
        self.assertEqual(delta.draw_ms_delta, -4.0)
        self.assertEqual(delta.dispatch_ms_delta, -2.0)
        self.assertEqual(delta.input_wait_ms_delta, 40.0)
        self.assertEqual(delta.loops_delta, 20)
        self.assertEqual(delta.redraws_delta, -2)
        self.assertEqual(delta.events_delta, 2)

    def test_compare_profiles_keeps_none_when_side_missing(self):
        before = BaselineProfile(
            boot_ms=None,
            redraw_ratio=None,
            draw_ms=None,
            dispatch_ms=None,
            input_wait_ms=None,
            loops=None,
            redraws=None,
            events=None,
        )
        after = BaselineProfile(
            boot_ms=70.0,
            redraw_ratio=0.1,
            draw_ms=5.0,
            dispatch_ms=2.0,
            input_wait_ms=1000.0,
            loops=200,
            redraws=20,
            events=50,
        )

        delta = compare_profiles(before, after)

        self.assertIsNone(delta.boot_ms_delta)
        self.assertIsNone(delta.redraw_ratio_delta)
        self.assertIsNone(delta.draw_ms_delta)
        self.assertIsNone(delta.dispatch_ms_delta)
        self.assertIsNone(delta.input_wait_ms_delta)
        self.assertIsNone(delta.loops_delta)
        self.assertIsNone(delta.redraws_delta)
        self.assertIsNone(delta.events_delta)


if __name__ == "__main__":
    unittest.main()
