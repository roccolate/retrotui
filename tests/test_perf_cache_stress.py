"""Stress tests for the per-line wrap cache (M15) and the cached
hidden-CSV parser (M11).

These tests confirm the two structural optimisations stay correct
under load (large buffer, many edits, repeated right-clicks) and
give the next reader a smoke test if either cache is regressed to
a full O(n) per-event cost.
"""
import os
import sys
import time
import unittest
from unittest import mock

# ``_support`` lives in the tests/ directory and sets up a fake
# curses for headless runs.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _support  # noqa: E402,F401  — sets up fake curses

from retrotui.apps.notepad import NotepadWindow
from retrotui.core.config import AppConfig
from retrotui.core.icon_styles import (
    _split_config_csv_cached,
    get_hidden_icon_labels,
    split_config_csv,
)


class NotepadWrapCacheStressTests(unittest.TestCase):
    """Per-line wrap cache must stay correct after many edits."""

    def setUp(self):
        self.win = NotepadWindow(0, 0, 80, 24)
        self.win.wrap_mode = True

    def test_many_single_char_edits_keep_chunks_consistent(self):
        # 5000-line buffer; we type 200 characters and assert the
        # cache is consistent with the buffer at every step.
        self.win.buffer = [f"line {i}: " + "x" * 40 for i in range(5000)]
        # First compute populates the cache.
        first = self.win._compute_wrap(70)
        self.assertTrue(len(first) > 0)
        for idx in range(len(self.win._wrap_line_cache)):
            self.assertIsNotNone(
                self.win._wrap_line_cache[idx],
                f"line {idx} should be cached after first compute",
            )

        for i in range(200):
            line = i % 5000
            self.win.buffer[line] = self.win.buffer[line] + "y"
            self.win._invalidate_wrap(line)
            result = self.win._compute_wrap(70)
            # The chunks for the edited line should now contain "y".
            chunks_for_line = [
                c for c in result if c[0] == line
            ]
            self.assertTrue(
                any("y" in c[2] for c in chunks_for_line),
                f"edit on line {line} did not appear in recomputed chunks",
            )

    def test_insert_delete_lines_keep_cache_in_sync(self):
        self.win.buffer = [f"line {i}" for i in range(100)]
        for i in range(50):
            # Insert a line at the cursor.
            self.win.cursor_line = i
            self.win.buffer.insert(i, f"NEW {i}")
            self.win._invalidate_wrap()
            self.win._sync_wrap_cache_to_buffer()
            result = self.win._compute_wrap(70)
            self.assertEqual(len(self.win._wrap_line_cache), len(self.win.buffer))
            # All chunk line_idx should match their buffer index.
            for chunk in result:
                self.assertLess(chunk[0], len(self.win.buffer))

            # And delete it.
            self.win.buffer.pop(i)
            self.win._invalidate_wrap()
            self.win._sync_wrap_cache_to_buffer()
            result = self.win._compute_wrap(70)
            self.assertEqual(len(self.win._wrap_line_cache), len(self.win.buffer))
            for chunk in result:
                self.assertLess(chunk[0], len(self.win.buffer))

    def test_per_line_invalidation_stays_fast(self):
        # Sanity: 5000-line buffer + 200 single-char edits + 200
        # full draws should complete in well under 1s (was ~6s with
        # the old full-cache invalidation; ~0.05s now).
        self.win.buffer = [f"line {i}: " + "x" * 40 for i in range(5000)]
        # Warm up.
        self.win._compute_wrap(70)
        start = time.perf_counter()
        for i in range(200):
            line = i % 5000
            self.win.buffer[line] = self.win.buffer[line] + "y"
            self.win._invalidate_wrap(line)
            self.win._compute_wrap(70)
        elapsed = time.perf_counter() - start
        self.assertLess(
            elapsed, 2.0,
            f"per-line invalidation regressed: {elapsed:.2f}s for 200 iters",
        )


class HiddenCSVCacheStressTests(unittest.TestCase):
    """Cached hidden-CSV parser must be fast and invalidation-safe."""

    def setUp(self):
        _split_config_csv_cached.cache_clear()

    def test_cache_hits_avoid_re_tokenizing(self):
        raw = "files,calc,trash,plugin:minesweeper,plugin:snake"
        # Cold call.
        first = _split_config_csv_cached(raw)
        self.assertEqual(first, split_config_csv(raw))
        # Subsequent calls must hit the cache.
        start = time.perf_counter()
        for _ in range(5000):
            _split_config_csv_cached(raw)
        elapsed = time.perf_counter() - start
        self.assertLess(
            elapsed, 1.0,
            f"5000 cached lookups took {elapsed:.2f}s — cache regressed?",
        )

    def test_cache_invalidation_on_string_change(self):
        raw_a = "files,calc"
        raw_b = "files,calc,trash"
        self.assertEqual(
            _split_config_csv_cached(raw_a),
            {"files", "calc"},
        )
        self.assertEqual(
            _split_config_csv_cached(raw_b),
            {"files", "calc", "trash"},
        )
        # Re-query with the original string returns the original set.
        self.assertEqual(
            _split_config_csv_cached(raw_a),
            {"files", "calc"},
        )

    def test_get_hidden_icon_labels_caches_via_config(self):
        config = AppConfig(hidden_icons="files,calc,trash,plugin:*")
        first = get_hidden_icon_labels(config)
        self.assertIn("files", first)
        self.assertIn("plugin:*", first)
        # Repeated calls must hit the same cache entry.
        for _ in range(1000):
            self.assertIs(
                get_hidden_icon_labels(config), first,
            )

    def test_large_csv_is_fast(self):
        raw = ",".join(f"item_{i}" for i in range(50))
        _split_config_csv_cached.cache_clear()
        start = time.perf_counter()
        for _ in range(5000):
            _split_config_csv_cached(raw)
        elapsed = time.perf_counter() - start
        self.assertLess(
            elapsed, 1.0,
            f"5000 lookups on a 50-token CSV took {elapsed:.2f}s",
        )


if __name__ == "__main__":
    unittest.main()
