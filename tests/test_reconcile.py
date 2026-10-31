from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any

from scripts.reconcile import (
    HindsightGateway,
    ReconcileError,
    Snapshot,
    _assert_snapshot_is_current,
    _reconcile_lock,
    build_plan,
    reconcile,
    record_metadata,
    record_hash,
    resolve_snapshot,
)
from tests.test_validate import valid_record


SOURCE_REPOSITORY = "example/team-agent-knowledge"


class FakeHindsight(HindsightGateway):
    def __init__(self, documents: list[dict[str, Any]] | None = None, fail_on: str | None = None):
        self.documents = list(documents or [])
        self.events: list[tuple[str, str]] = []
        self.fail_on = fail_on

    def list_documents(self, bank_id: str) -> list[dict[str, Any]]:
        if self.fail_on == "list":
            raise ReconcileError("simulated outage")
        self.events.append(("list", bank_id))
        return list(self.documents)

    def upsert_document(self, bank_id: str, document_id: str, content: str, metadata: dict[str, str]) -> None:
        if self.fail_on == "upsert":
            raise ReconcileError("simulated outage")
        self.events.append(("upsert", document_id))
        self.documents = [item for item in self.documents if item.get("id") != document_id]
        self.documents.append({"id": document_id, "document_metadata": dict(metadata), "content": content})

    def delete_document(self, bank_id: str, document_id: str) -> None:
        if self.fail_on == "delete":
            raise ReconcileError("simulated outage")
        self.events.append(("delete", document_id))
        self.documents = [item for item in self.documents if item.get("id") != document_id]


def snapshot_for(record: dict[str, Any], root: Path, commit: str = "a" * 40) -> Snapshot:
    return Snapshot(commit, root, "knowledge", [record], {record["id"]: f"knowledge/{record['id']}.yaml"})


class ReconcileTests(unittest.TestCase):
    def test_idempotence_and_watermark(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / "state.json"
            client = FakeHindsight()
            snapshot = snapshot_for(valid_record(), root)
            first = reconcile(snapshot, client, source_repository=SOURCE_REPOSITORY, state_file=state)
            second = reconcile(snapshot, client, source_repository=SOURCE_REPOSITORY, state_file=state)

            self.assertEqual([action.action for action in first], ["upsert"])
            self.assertEqual([action.action for action in second], ["skip"])
            self.assertEqual([event for event in client.events if event[0] == "upsert"], [("upsert", "COMP-001")])
            self.assertEqual(json.loads(state.read_text())["last_snapshot_commit"], "a" * 40)

    def test_failure_does_not_write_success_watermark(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / "state.json"
            client = FakeHindsight(fail_on="upsert")
            with self.assertRaises(ReconcileError):
                reconcile(snapshot_for(valid_record(), root), client, source_repository=SOURCE_REPOSITORY, state_file=state)
            self.assertFalse(state.exists())

    def test_unrelated_same_id_is_never_overwritten(self) -> None:
        record = valid_record()
        unrelated = {"id": "COMP-001", "document_metadata": {"managed_by": "someone-else", "source_repository": SOURCE_REPOSITORY}}
        with self.assertRaises(ReconcileError):
            build_plan([record], [unrelated], source_repository=SOURCE_REPOSITORY)

    def test_unrelated_documents_are_never_deleted(self) -> None:
        record = valid_record()
        unrelated = {"id": "other", "document_metadata": {"managed_by": "someone-else", "source_repository": SOURCE_REPOSITORY}}
        plan = build_plan([record], [unrelated], source_repository=SOURCE_REPOSITORY)
        self.assertEqual([action.action for action in plan], ["upsert"])

    def test_owned_orphan_and_retired_records_are_deleted(self) -> None:
        retired = valid_record("COMP-002")
        retired["status"] = "retired"
        owned_retired = {
            "id": "COMP-002",
            "document_metadata": {
                "managed_by": "team-agent-knowledge",
                "source_repository": SOURCE_REPOSITORY,
                "source_path": "knowledge/COMP-002.yaml",
            },
        }
        orphan = {
            "id": "COMP-999",
            "document_metadata": {
                "managed_by": "team-agent-knowledge",
                "source_repository": SOURCE_REPOSITORY,
                "source_path": "knowledge/COMP-999.yaml",
            },
        }
        plan = build_plan([retired], [owned_retired, orphan], source_repository=SOURCE_REPOSITORY)
        self.assertEqual({(action.action, action.document_id) for action in plan}, {("delete", "COMP-002"), ("delete", "COMP-999")})

    def test_stale_snapshot_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "-C", str(root), "init", "-b", "main"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.com"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
            marker = root / "marker"
            marker.write_text("a")
            subprocess.run(["git", "-C", str(root), "add", "marker"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-m", "first"], check=True, capture_output=True)
            first = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
            marker.write_text("b")
            subprocess.run(["git", "-C", str(root), "add", "marker"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-m", "second"], check=True, capture_output=True)
            second = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
            state = root / "state.json"
            state.write_text(json.dumps({"last_snapshot_commit": second}))
            with self.assertRaises(ReconcileError):
                reconcile(
                    snapshot_for(valid_record(), root, first),
                    FakeHindsight(),
                    source_repository=SOURCE_REPOSITORY,
                    state_file=state,
                    require_origin=False,
                )

    def test_concurrent_reconcile_is_rejected_before_remote_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            client = FakeHindsight()
            snapshot = snapshot_for(valid_record(), root)
            with _reconcile_lock(root, "team-compiler"):
                with self.assertRaises(ReconcileError):
                    reconcile(snapshot, client, source_repository=SOURCE_REPOSITORY, state_file=root / "state.json")
            self.assertEqual(client.events, [])

    def test_snapshot_must_be_current_main_and_canonical_knowledge_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "-C", str(root), "init", "-q", "-b", "main"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.com"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
            knowledge = root / "knowledge"
            knowledge.mkdir()
            import yaml

            (knowledge / "COMP-001.yaml").write_text(yaml.safe_dump(valid_record(), sort_keys=False))
            subprocess.run(["git", "-C", str(root), "add", "knowledge"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "knowledge"], check=True)
            commit = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
            remote = root.parent / f"{root.name}-origin.git"
            subprocess.run(["git", "clone", "-q", "--bare", str(root), str(remote)], check=True)
            subprocess.run(["git", "-C", str(root), "remote", "add", "origin", str(remote)], check=True)
            snapshot = resolve_snapshot(root, commit, require_origin=False)
            self.assertEqual(snapshot.commit, commit)
            with self.assertRaises(ReconcileError):
                resolve_snapshot(root, commit, knowledge_path="examples/demo-compiler")

    def test_publish_requires_an_origin_remote(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "-C", str(root), "init", "-q", "-b", "main"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.com"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
            (root / "marker").write_text("a")
            subprocess.run(["git", "-C", str(root), "add", "marker"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "first"], check=True)
            commit = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()

            with self.assertRaisesRegex(ReconcileError, "origin.*required"):
                _assert_snapshot_is_current(
                    root,
                    commit,
                    expected_source_repository="5jyan/team-agent-knowledge",
                    require_origin=True,
                )

    def test_publish_rejects_origin_for_a_different_repository(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "-C", str(root), "init", "-q", "-b", "main"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.com"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
            (root / "marker").write_text("a")
            subprocess.run(["git", "-C", str(root), "add", "marker"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "first"], check=True)
            commit = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
            subprocess.run(
                ["git", "-C", str(root), "remote", "add", "origin", "https://github.com/wrong/repository.git"],
                check=True,
            )

            with self.assertRaisesRegex(ReconcileError, "does not match"):
                _assert_snapshot_is_current(
                    root,
                    commit,
                    expected_source_repository="5jyan/team-agent-knowledge",
                    require_origin=True,
                )


if __name__ == "__main__":
    unittest.main()
