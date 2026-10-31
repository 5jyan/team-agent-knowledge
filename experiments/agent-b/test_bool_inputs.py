"""Evidence for the comparison implementation's explicit bool exclusion."""

from __future__ import annotations

import unittest

from buffer_copy import copy_range


class BoolInputComparisonTests(unittest.TestCase):
    def test_comparison_implementation_rejects_bool_inputs(self) -> None:
        cases = (
            ("src=False", {"src": False, "dst": 2, "length": 1}),
            ("src=True", {"src": True, "dst": 2, "length": 1}),
            ("dst=False", {"src": 1, "dst": False, "length": 1}),
            ("dst=True", {"src": 0, "dst": True, "length": 1}),
            ("length=False", {"src": 0, "dst": 2, "length": False}),
            ("length=True", {"src": 0, "dst": 2, "length": True}),
        )

        for label, kwargs in cases:
            with self.subTest(label=label):
                with self.assertRaisesRegex(TypeError, "src, dst, and length"):
                    copy_range(b"abcd", **kwargs)


if __name__ == "__main__":
    unittest.main(verbosity=2)
