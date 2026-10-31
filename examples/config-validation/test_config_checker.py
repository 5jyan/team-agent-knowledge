"""Tests for the before/after configuration validation example."""

from __future__ import annotations

import unittest

from config_checker import validate_config, validate_config_before


class ConfigValidationTests(unittest.TestCase):
    def test_missing_model_gets_specific_error_after_the_fix(self) -> None:
        config: dict[str, object] = {}

        self.assertEqual(validate_config_before(config), "설정 오류")
        self.assertEqual(
            validate_config(config),
            "설정 오류: model 항목이 없습니다",
        )

    def test_model_present_is_normal_before_and_after(self) -> None:
        config = {"model": "demo-model"}

        self.assertEqual(validate_config_before(config), "설정 정상")
        self.assertEqual(validate_config(config), "설정 정상")

    def test_missing_model_error_does_not_echo_other_config_values(self) -> None:
        config = {"unrelated": "example-only-value"}

        result = validate_config(config)

        self.assertEqual(result, "설정 오류: model 항목이 없습니다")
        self.assertNotIn("example-only-value", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
