"""Evidence for Python bool handling in the canonical toy validator."""

from __future__ import annotations

import unittest

from optimizer import copy_range


class BoolInputEvidenceTests(unittest.TestCase):
    def test_bool_inputs_are_currently_accepted_as_int_subclasses(self) -> None:
        cases = (
            ("src=False", {"src": False, "dst": 2, "length": 1}, b"abad"),
            ("src=True", {"src": True, "dst": 2, "length": 1}, b"abbd"),
            ("dst=False", {"src": 1, "dst": False, "length": 1}, b"bbcd"),
            ("dst=True", {"src": 0, "dst": True, "length": 1}, b"aacd"),
            ("length=False", {"src": 0, "dst": 2, "length": False}, b"abcd"),
            ("length=True", {"src": 0, "dst": 2, "length": True}, b"abad"),
        )

        for label, kwargs, expected in cases:
            with self.subTest(label=label):
                memory = bytearray(b"abcd")
                plan = copy_range(memory, **kwargs)

                self.assertEqual(memory, bytearray(expected))
                self.assertEqual(plan.knowledge_id, "COMP-014")


if __name__ == "__main__":
    unittest.main(verbosity=2)
