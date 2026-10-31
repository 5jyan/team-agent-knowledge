"""Small standard-library tests used to verify the discovery command."""

import json
import unittest


class JsonRoundTripTests(unittest.TestCase):
    def test_round_trip_preserves_fields(self) -> None:
        payload = {"team": "compiler", "tests": 2}

        encoded = json.dumps(payload, sort_keys=True)

        self.assertEqual(json.loads(encoded), payload)

    def test_sorted_encoding_is_stable(self) -> None:
        payload = {"z": 1, "a": 2}

        self.assertEqual(
            json.dumps(payload, sort_keys=True),
            '{"a": 2, "z": 1}',
        )


if __name__ == "__main__":
    unittest.main()
