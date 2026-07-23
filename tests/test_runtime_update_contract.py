import unittest

from retrotui.core.runtime_updates import RenderUpdate


class RuntimeUpdateContractTests(unittest.TestCase):
    def test_render_update_levels_are_ordered_by_invalidation_scope(self):
        self.assertLess(RenderUpdate.NONE, RenderUpdate.OVERLAY)
        self.assertLess(RenderUpdate.OVERLAY, RenderUpdate.FULL)

    def test_render_update_levels_preserve_integer_compatibility(self):
        self.assertEqual(int(RenderUpdate.NONE), 0)
        self.assertEqual(int(RenderUpdate.OVERLAY), 1)
        self.assertEqual(int(RenderUpdate.FULL), 2)


if __name__ == "__main__":
    unittest.main()
