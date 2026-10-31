"""Executable tests for the integrated byte-buffer copy function."""

from __future__ import annotations

import unittest

from buffer_copy import copy_range


class CopyRangeTests(unittest.TestCase):
    def test_requested_non_overlapping_copy(self) -> None:
        source = b"abcdefghij"

        actual = copy_range(source, src=1, dst=6, length=3)

        self.assertEqual(actual, b"abcdefbcdj")
        self.assertEqual(source, b"abcdefghij")

    def test_overlapping_copy_snapshots_source(self) -> None:
        self.assertEqual(copy_range(b"abcdef", src=0, dst=2, length=4), b"ababcd")
        self.assertEqual(copy_range(b"abcdef", src=2, dst=0, length=4), b"cdefef")

    def test_invalid_ranges_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            copy_range(b"abc", src=0, dst=2, length=2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
