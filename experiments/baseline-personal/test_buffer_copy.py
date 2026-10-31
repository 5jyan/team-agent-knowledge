import unittest

from buffer_copy import copy_bytes_segment


class CopyBytesSegmentTests(unittest.TestCase):
    def test_copies_requested_segment(self) -> None:
        original = b"abcdefghij"

        result = copy_bytes_segment(original, source_index=1, length=3, destination_index=6)

        self.assertEqual(result, b"abcdefbcdj")
        self.assertEqual(original, b"abcdefghij")


if __name__ == "__main__":
    unittest.main()
