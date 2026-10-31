from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.validate import ValidationFailure, validate_entries, verify_remote_evidence


def valid_record(identifier: str = "COMP-001") -> dict:
    return {
        "schema_version": 1,
        "type": "bugfix",
        "id": identifier,
        "status": "active",
        "title": "Safe copy for disjoint buffers",
        "summary": "Use the fast copy path only for disjoint ranges.",
        "problem": {"statement": "Overlap can corrupt a forward copy."},
        "cause": {"statement": "The forward loop reads bytes after writing them."},
        "solution": {"statement": "Guard overlap and snapshot the source bytes."},
        "limitations": [{"condition": "Unknown aliasing", "action": "Use the safe path."}],
        "scope": {
            "applies_when": ["Ranges are disjoint."],
            "does_not_apply_when": ["Aliasing is unknown."],
        },
        "evidence": {
            "repository": "https://github.com/example/repo",
            "commit": "a" * 40,
            "verified_at": "2026-10-31T12:00:00Z",
            "tests": [{"command": "python -m unittest", "result": "passed"}],
            "run": {"command": "python demo.py", "result": "expected output"},
        },
        "maintenance": {
            "owner": "compiler-team",
            "review_after": "2026-12-31",
            "update_trigger": "A new overlap regression.",
        },
        "references": ["https://github.com/example/repo/commit/" + "a" * 40],
    }


class ValidationTests(unittest.TestCase):
    def test_existing_empty_directory_is_valid_initial_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            from scripts.validate import load_records

            self.assertEqual(load_records([Path(directory)]), [])

    def test_valid_record_passes(self) -> None:
        records = validate_entries([("COMP-001.yaml", valid_record())])
        self.assertEqual(records[0]["id"], "COMP-001")

    def test_wrong_id_and_duplicate_are_rejected(self) -> None:
        first = valid_record()
        duplicate = copy.deepcopy(first)
        with self.assertRaises(ValidationFailure) as context:
            validate_entries([("COMP-999.yaml", first), ("COMP-001.yaml", duplicate)])
        message = str(context.exception)
        self.assertIn("filename stem must match id", message)
        self.assertIn("duplicate id", message)

    def test_missing_evidence_is_rejected(self) -> None:
        record = valid_record()
        del record["evidence"]["tests"]
        with self.assertRaises(ValidationFailure) as context:
            validate_entries([("COMP-001.yaml", record)])
        self.assertIn("evidence", str(context.exception))

    def test_secret_like_value_is_rejected(self) -> None:
        record = valid_record()
        record["summary"] = "temporary token sk-test_1234567890123456"
        with self.assertRaises(ValidationFailure) as context:
            validate_entries([("COMP-001.yaml", record)])
        self.assertIn("possible secret detected", str(context.exception))

    def test_retired_record_keeps_evidence(self) -> None:
        record = valid_record()
        record["status"] = "retired"
        del record["evidence"]["tests"]
        with self.assertRaises(ValidationFailure):
            validate_entries([("COMP-001.yaml", record)])

    def test_remote_verification_rejects_non_github_urls_without_running_git(self) -> None:
        malicious_values = [
            "/tmp/remote.git",
            "file:///tmp/remote.git",
            "ssh://git@github.com/example/repo.git",
            "git@github.com:example/repo.git",
            "https://user:password@github.com/example/repo.git",
            "https://github.com/example/repo.git?token=secret",
            "https://github.com/example/repo.git#fragment",
            "https://github.com.example/example/repo.git",
        ]
        with patch("scripts.validate.subprocess.run") as run:
            for repository in malicious_values:
                record = valid_record()
                record["evidence"]["repository"] = repository
                with self.subTest(repository=repository), self.assertRaises(ValidationFailure):
                    verify_remote_evidence([record])
        run.assert_not_called()

    def test_remote_verification_uses_https_for_private_github_repository(self) -> None:
        record = valid_record()
        record["evidence"]["repository"] = "https://github.com/Acme/Private.git"
        successful = SimpleNamespace(returncode=0, stdout="", stderr="")
        with patch("scripts.validate.subprocess.run", return_value=successful) as run:
            verify_remote_evidence([record])

        fetch_call = next(call for call in run.call_args_list if "fetch" in call.args[0])
        command = fetch_call.args[0]
        self.assertIn("https://github.com/acme/private.git", command)
        self.assertEqual(fetch_call.kwargs["env"]["GIT_ALLOW_PROTOCOL"], "https")


if __name__ == "__main__":
    unittest.main()
