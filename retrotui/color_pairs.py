"""Capability-aware color-pair negotiation for curses backends.

RetroTUI historically uses stable logical pair IDs up to 121. Some curses
backends expose fewer pairs. This module installs a transparent compatibility
layer that keeps those logical IDs while compacting their actual allocations.
"""

from __future__ import annotations

from typing import Any


# Pair 0 is reserved by curses. The highest legacy logical pair is 121, so a
# backend that does not expose COLOR_PAIRS in a test double is treated as the
# historical full-capability environment.
LEGACY_COLOR_PAIR_CAPACITY = 122


class ColorPairNegotiator:
    """Map RetroTUI logical pair IDs onto the pairs a backend can provide."""

    def __init__(self, curses_module: Any):
        self.curses = curses_module
        self._original_start_color = getattr(curses_module, "start_color", None)
        self._original_init_pair = getattr(curses_module, "init_pair", None)
        self._original_color_pair = getattr(curses_module, "color_pair", None)
        self.reset()

    def reset(self) -> None:
        """Forget allocations before a new theme/color initialization pass."""
        self._logical_to_actual: dict[int, int] = {}
        self._logical_definitions: dict[int, tuple[int, int]] = {}
        self._combo_to_actual: dict[tuple[int, int], int] = {}
        self._actual_definitions: dict[int, tuple[int, int]] = {}
        self._actual_users: dict[int, set[int]] = {}

    def color_pair_capacity(self) -> int:
        """Return the backend pair count, including reserved pair zero."""
        raw = getattr(self.curses, "COLOR_PAIRS", None)
        if raw is None:
            return LEGACY_COLOR_PAIR_CAPACITY
        try:
            return max(0, int(raw))
        except (TypeError, ValueError):
            return 0

    def start_color(self, *args, **kwargs):
        """Delegate to curses and begin a fresh allocation generation."""
        if callable(self._original_start_color):
            result = self._original_start_color(*args, **kwargs)
        else:
            result = None
        self.reset()
        return result

    def _first_free_actual(self, capacity: int) -> int:
        for pair_id in range(1, capacity):
            if pair_id not in self._actual_definitions:
                return pair_id
        return 0

    def _release_logical(self, logical: int) -> int:
        """Detach a logical mapping and release an actual pair when unused."""
        actual = self._logical_to_actual.pop(logical, 0)
        combo = self._logical_definitions.pop(logical, None)
        if actual <= 0:
            return actual

        users = self._actual_users.get(actual)
        if users is not None:
            users.discard(logical)
            if users:
                return actual
            self._actual_users.pop(actual, None)

        actual_combo = self._actual_definitions.pop(actual, None)
        if (
            actual_combo is not None
            and self._combo_to_actual.get(actual_combo) == actual
        ):
            self._combo_to_actual.pop(actual_combo, None)
        elif combo is not None and self._combo_to_actual.get(combo) == actual:
            self._combo_to_actual.pop(combo, None)
        return actual

    def _bind_logical(
        self,
        logical: int,
        combo: tuple[int, int],
        actual: int,
    ) -> None:
        self._logical_definitions[logical] = combo
        self._logical_to_actual[logical] = actual
        if actual <= 0:
            return
        self._actual_definitions[actual] = combo
        self._actual_users.setdefault(actual, set()).add(logical)
        self._combo_to_actual.setdefault(combo, actual)

    def init_pair(self, logical_pair_id, fg, bg):
        """Initialize a logical pair without exceeding ``COLOR_PAIRS``.

        On constrained terminals equal foreground/background combinations share
        one actual pair. Redefining a logical pair preserves legacy curses
        semantics without mutating an actual pair shared by another logical ID.
        When all slots are exhausted, the pair degrades to pair zero.
        """
        try:
            logical = int(logical_pair_id)
            combo = (int(fg), int(bg))
        except (TypeError, ValueError):
            return None

        if logical <= 0:
            return None

        previous_combo = self._logical_definitions.get(logical)
        if previous_combo == combo:
            return None

        capacity = self.color_pair_capacity()
        if capacity <= 1 or not callable(self._original_init_pair):
            self._release_logical(logical)
            self._bind_logical(logical, combo, 0)
            return None

        compact = capacity < LEGACY_COLOR_PAIR_CAPACITY
        previous_actual = self._logical_to_actual.get(logical, 0)
        actual = 0
        needs_init = True

        if compact:
            shared_combo_actual = self._combo_to_actual.get(combo, 0)
            if shared_combo_actual:
                actual = shared_combo_actual
                needs_init = False
            elif (
                previous_actual > 0
                and len(self._actual_users.get(previous_actual, ())) <= 1
            ):
                actual = previous_actual
            elif (
                0 < logical < capacity
                and logical not in self._actual_definitions
            ):
                actual = logical
            else:
                actual = self._first_free_actual(capacity)
        elif 0 < logical < capacity:
            users = self._actual_users.get(logical, set())
            if not users or users == {logical}:
                actual = logical
            else:
                actual = self._first_free_actual(capacity)
        else:
            actual = self._first_free_actual(capacity)

        self._release_logical(logical)

        if not actual:
            self._bind_logical(logical, combo, 0)
            return None

        if needs_init:
            try:
                result = self._original_init_pair(actual, combo[0], combo[1])
            except Exception:
                # Curses errors are backend-boundary failures; degrading one
                # pair must not abort application startup.
                self._bind_logical(logical, combo, 0)
                return None
        else:
            result = None

        self._bind_logical(logical, combo, actual)
        return result

    def resolve_pair_id(self, logical_pair_id) -> int:
        """Resolve a logical ID to an initialized backend pair or pair zero."""
        try:
            logical = int(logical_pair_id)
        except (TypeError, ValueError):
            return 0

        mapped = self._logical_to_actual.get(logical)
        if mapped is not None:
            return mapped

        capacity = self.color_pair_capacity()
        if capacity >= LEGACY_COLOR_PAIR_CAPACITY and 0 <= logical < capacity:
            return logical
        return 0

    def color_pair(self, logical_pair_id):
        """Return the curses attribute for a negotiated logical pair."""
        actual = self.resolve_pair_id(logical_pair_id)
        if not callable(self._original_color_pair):
            return 0
        try:
            return self._original_color_pair(actual)
        except Exception:
            return 0

    def snapshot(self) -> dict[str, Any]:
        """Return diagnostics for tests and runtime reporting."""
        capacity = self.color_pair_capacity()
        return {
            "color_pairs": capacity,
            "compact": capacity < LEGACY_COLOR_PAIR_CAPACITY,
            "logical_to_actual": dict(self._logical_to_actual),
            "actual_definitions": dict(self._actual_definitions),
        }


def install_color_pair_negotiation(curses_module: Any) -> ColorPairNegotiator:
    """Install negotiation wrappers once on a curses-compatible module."""
    existing = getattr(curses_module, "_retrotui_color_pair_negotiator", None)
    if existing is not None and getattr(existing, "curses", None) is curses_module:
        return existing

    negotiator = ColorPairNegotiator(curses_module)
    if callable(negotiator._original_start_color):
        curses_module.start_color = negotiator.start_color
    if callable(negotiator._original_init_pair):
        curses_module.init_pair = negotiator.init_pair
    if callable(negotiator._original_color_pair):
        curses_module.color_pair = negotiator.color_pair
    curses_module._retrotui_color_pair_negotiator = negotiator
    return negotiator
