"""Boundary checks for zero-length copies in both implementations."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

from buffer_copy import copy_range as integrated_copy_range


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
OPTIMIZER_PATH = REPOSITORY_ROOT / "examples" / "demo-compiler" / "optimizer.py"
SPEC = importlib.util.spec_from_file_location("repository_optimizer", OPTIMIZER_PATH)
if SPEC is None or SPEC.loader is None:  # pragma: no cover - import setup failure
    raise ImportError(f"cannot load repository optimizer from {OPTIMIZER_PATH}")
repository_optimizer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = repository_optimizer
SPEC.loader.exec_module(repository_optimizer)


class ZeroLengthBoundaryTests(unittest.TestCase):
    def test_repository_optimizer_accepts_empty_copy_at_buffer_end(self) -> None:
        memory = bytearray(b"abc")

        plan = repository_optimizer.copy_range(memory, src=3, dst=3, length=0)

        self.assertEqual(plan.revision, "r1")
        self.assertEqual(plan.path, "nonoverlap-fast")
        self.assertEqual(memory, bytearray(b"abc"))

    def test_repository_optimizer_rejects_positive_copy_at_buffer_end(self) -> None:
        with self.assertRaises(ValueError):
            repository_optimizer.copy_range(bytearray(b"abc"), src=3, dst=3, length=1)

    def test_integrated_function_matches_zero_length_boundary(self) -> None:
        self.assertEqual(integrated_copy_range(b"abc", src=3, dst=3, length=0), b"abc")

    def test_integrated_function_rejects_positive_copy_at_buffer_end(self) -> None:
        with self.assertRaises(ValueError):
            integrated_copy_range(b"abc", src=3, dst=3, length=1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
