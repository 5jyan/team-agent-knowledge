import unittest

from copy_buffer import copy_range


class CopyRangeIntegrationTest(unittest.TestCase):
    def test_requested_non_overlapping_copy(self):
        original = b"abcdefghij"

        result = copy_range(original, source_index=1, length=3, destination_index=6)

        self.assertEqual(result, b"abcdefbcdj")
        self.assertEqual(original, b"abcdefghij")

    def test_overlapping_copy_uses_original_snapshot(self):
        self.assertEqual(
            copy_range(b"abcdefghij", source_index=1, length=3, destination_index=2),
            b"abbcdfghij",
        )


if __name__ == "__main__":
    unittest.main()
