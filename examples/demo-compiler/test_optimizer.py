"""Executable checks for the A -> B -> updated-team-rule demo."""

from __future__ import annotations

import unittest

from optimizer import copy_range, plan_copy, r1_naive_copy


class BufferCopyDemoTests(unittest.TestCase):
    def test_a_verified_nonoverlap_rule_is_reusable_by_b(self) -> None:
        """B can reuse A's r1 rule when the ranges do not overlap."""

        memory = bytearray(b"abcdefgh")
        plan = copy_range(memory, src=0, dst=4, length=4)

        self.assertEqual(plan.knowledge_id, "COMP-014")
        self.assertEqual(plan.revision, "r1")
        self.assertEqual(plan.path, "nonoverlap-fast")
        self.assertEqual(memory, bytearray(b"abcdabcd"))

    def test_r1_fixture_reproduces_the_overlapping_buffer_bug(self) -> None:
        memory = bytearray(b"abcdef")
        r1_naive_copy(memory, src=0, dst=2, length=4)

        # Forward writes reread bytes that were already overwritten.
        self.assertEqual(memory, bytearray(b"ababab"))
        self.assertNotEqual(memory, bytearray(b"ababcd"))

    def test_r2_safe_guard_handles_overlap_in_both_directions(self) -> None:
        rightward = bytearray(b"abcdef")
        rightward_plan = copy_range(rightward, src=0, dst=2, length=4)
        self.assertEqual(rightward, bytearray(b"ababcd"))
        self.assertEqual(rightward_plan.revision, "r2")
        self.assertEqual(rightward_plan.path, "overlap-safe")

        leftward = bytearray(b"abcdef")
        leftward_plan = copy_range(leftward, src=2, dst=0, length=4)
        self.assertEqual(leftward, bytearray(b"cdefef"))
        self.assertEqual(leftward_plan.revision, "r2")
        self.assertEqual(leftward_plan.path, "overlap-safe")

    def test_public_entrypoint_never_ships_the_broken_r1_behavior(self) -> None:
        memory = bytearray(b"abcdef")
        plan = copy_range(memory, src=0, dst=2, length=4)

        self.assertEqual(plan.revision, "r2")
        self.assertEqual(memory, bytearray(b"ababcd"))

    def test_current_rule_matches_snapshot_reference_for_small_buffers(self) -> None:
        """Exercise both paths over a deterministic set of valid ranges."""

        for size in range(1, 8):
            original = bytearray(range(size))
            for src in range(size):
                for dst in range(size):
                    for length in range(size - max(src, dst) + 1):
                        expected = original.copy()
                        expected[dst : dst + length] = original[src : src + length]

                        actual = original.copy()
                        copy_range(actual, src, dst, length)

                        self.assertEqual(
                            actual,
                            expected,
                            msg=f"size={size} src={src} dst={dst} length={length}",
                        )

    def test_plan_does_not_mutate_memory_and_rejects_invalid_ranges(self) -> None:
        memory = bytearray(b"abc")
        self.assertEqual(plan_copy(memory, 0, 2, 0).revision, "r1")
        self.assertEqual(memory, bytearray(b"abc"))

        with self.assertRaises(ValueError):
            copy_range(memory, src=0, dst=2, length=2)

    def test_empty_copy_accepts_every_boundary_without_mutation(self) -> None:
        # Agent B checked the previously undocumented end-of-buffer boundary.
        for size in range(8):
            original = bytearray(range(size))
            for src in range(size + 1):
                for dst in range(size + 1):
                    memory = original.copy()
                    plan = copy_range(memory, src=src, dst=dst, length=0)
                    self.assertEqual(memory, original)
                    self.assertEqual(plan.path, "nonoverlap-fast")

    def test_positive_copy_cannot_start_at_end(self) -> None:
        for src, dst in ((3, 0), (0, 3), (3, 3)):
            with self.assertRaises(ValueError):
                copy_range(bytearray(b"abc"), src=src, dst=dst, length=1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
