#!/usr/bin/env python3
"""Reconcile an approved Git snapshot into a Hindsight Team Bank.

The publisher is deliberately manual: it reads an immutable ``git show``
snapshot, validates it, and only then applies a full snapshot reconcile.  The
state watermark is written after every remote mutation succeeds, so a failed
run is safe to retry and cannot claim success for a partial publish.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Protocol
from urllib.parse import quote

import requests
import yaml

try:  # Direct script invocation and ``python -m scripts.reconcile`` both work.
    from .validate import (
        DEFAULT_SCHEMA,
        ValidationFailure,
        normalize_github_repository_url,
        normalize_source_repository,
        validate_entries,
    )
except ImportError:  # pragma: no cover - exercised by the CLI, not imports.
    from validate import (
        DEFAULT_SCHEMA,
        ValidationFailure,
        normalize_github_repository_url,
        normalize_source_repository,
        validate_entries,
    )


MANAGED_BY = "team-agent-knowledge"
DEFAULT_BANK = "team-compiler"
DEFAULT_SOURCE_REPOSITORY = "5jyan/team-agent-knowledge"
DEFAULT_KNOWLEDGE_PATH = "knowledge"
DEFAULT_STATE_FILE = ".reconcile-state.json"


class ReconcileError(RuntimeError):
    """Raised when a snapshot cannot be published safely."""


class HindsightError(ReconcileError):
    """Raised for a Hindsight API outage or non-success response."""


class HindsightGateway(Protocol):
    def list_documents(self, bank_id: str) -> list[dict[str, Any]]: ...

    def upsert_document(self, bank_id: str, document_id: str, content: str, metadata: dict[str, str]) -> Any: ...

    def delete_document(self, bank_id: str, document_id: str) -> Any: ...


class HindsightClient:
    """Small REST client for the stable Hindsight 1.1 document endpoints."""

    def __init__(self, base_url: str = "http://127.0.0.1:8888", timeout: float = 30.0, session: Any = None):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = self.session.request(method, f"{self.base_url}{path}", timeout=self.timeout, **kwargs)
        except requests.RequestException as exc:
            raise HindsightError(f"Hindsight request failed ({method} {path}): {exc}") from exc
        if not 200 <= response.status_code < 300:
            body = response.text.strip()
            raise HindsightError(f"Hindsight returned HTTP {response.status_code} for {method} {path}: {body[:500]}")
        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError as exc:
            raise HindsightError(f"Hindsight returned invalid JSON for {method} {path}") from exc

    def list_documents(self, bank_id: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        offset = 0
        while True:
            payload = self._request(
                "GET",
                f"/v1/default/banks/{quote(bank_id, safe='')}/documents",
                params={"limit": 100, "offset": offset},
            )
            page = payload.get("items", [])
            if not isinstance(page, list):
                raise HindsightError("Hindsight documents response has a non-list items field")
            items.extend(item for item in page if isinstance(item, dict))
            if len(page) < 100:
                break
            offset += len(page)
        return items

    def upsert_document(self, bank_id: str, document_id: str, content: str, metadata: dict[str, str]) -> Any:
        return self._request(
            "POST",
            f"/v1/default/banks/{quote(bank_id, safe='')}/memories",
            json={
                "items": [
                    {
                        "content": content,
                        "context": "approved team compiler knowledge",
                        "document_id": document_id,
                        "metadata": metadata,
                        "tags": [MANAGED_BY],
                    }
                ],
                "async": False,
            },
        )

    def delete_document(self, bank_id: str, document_id: str) -> Any:
        return self._request(
            "DELETE",
            f"/v1/default/banks/{quote(bank_id, safe='')}/documents/{quote(document_id, safe='')}",
        )


@dataclass(frozen=True)
class Snapshot:
    commit: str
    repository_root: Path
    knowledge_path: str
    records: list[dict[str, Any]]
    source_paths: dict[str, str]


@dataclass(frozen=True)
class PlannedAction:
    action: str
    document_id: str
    reason: str


def _git(repo_root: Path, *args: str, check: bool = True) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            check=check,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", None) or str(exc)
        raise ReconcileError(f"git {' '.join(args)} failed: {detail.strip()}") from exc
    if result.returncode and check:
        raise ReconcileError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def _https_git_env() -> dict[str, str]:
    """Allow Git's HTTPS transport while blocking SSH/file/ext helpers."""
    environment = dict(os.environ)
    environment["GIT_ALLOW_PROTOCOL"] = "https"
    return environment


def _assert_snapshot_is_current(
    repository_root: Path,
    commit: str,
    *,
    expected_source_repository: str | None = None,
    require_origin: bool = True,
) -> None:
    """Require the approved SHA to be current local main and live origin/main.

    Unit tests using a temporary local bare remote may explicitly set
    ``require_origin=False``.  The production default remains fail-closed.
    """
    main_head = _git(repository_root, "rev-parse", "--verify", "refs/heads/main", check=False)
    if main_head and main_head != commit:
        raise ReconcileError(f"snapshot {commit} is not the current local main commit {main_head}")
    remote_head = _git(repository_root, "rev-parse", "--verify", "refs/remotes/origin/main", check=False)
    if remote_head and remote_head != commit:
        raise ReconcileError(f"snapshot {commit} is not the cached origin/main commit {remote_head}")
    origin = _git(repository_root, "remote", "get-url", "origin", check=False)
    if require_origin and not origin:
        raise ReconcileError("Git remote 'origin' is required for a publish")
    normalized_origin = ""
    if origin:
        try:
            normalized_origin = normalize_github_repository_url(origin)
        except ValueError as exc:
            if require_origin:
                raise ReconcileError("Git remote 'origin' must be a credential-free GitHub HTTPS URL") from exc
        if expected_source_repository and normalized_origin:
            try:
                expected = normalize_source_repository(expected_source_repository)
            except ValueError as exc:
                raise ReconcileError("source repository must be owner/repository or a strict GitHub HTTPS URL") from exc
            if normalized_origin != expected:
                raise ReconcileError("Git remote 'origin' does not match --source-repository")
    if origin and (normalized_origin or not require_origin):
        remote_url = f"https://github.com/{normalized_origin}.git" if normalized_origin else origin
        try:
            live = subprocess.run(
                ["git", "ls-remote", remote_url, "refs/heads/main"],
                check=False,
                capture_output=True,
                text=True,
                timeout=20,
                # The CLI always supplies a normalized GitHub URL, so its
                # subprocess is HTTPS-only.  A local bare remote is retained
                # only for explicit unit fixtures using ``require_origin=False``.
                env=_https_git_env() if normalized_origin else None,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ReconcileError("cannot verify live origin/main") from exc
        if live.returncode != 0:
            raise ReconcileError("cannot verify live origin/main")
        live_head = next((line.split()[0] for line in live.stdout.splitlines() if line.split()), "")
        if not live_head:
            raise ReconcileError("origin does not advertise refs/heads/main")
        if live_head != commit:
            raise ReconcileError(f"snapshot {commit} is not the live origin/main commit {live_head}")
    unstaged = subprocess.run(
        ["git", "-C", str(repository_root), "diff", "--quiet"],
        check=False,
        capture_output=True,
    )
    staged = subprocess.run(
        ["git", "-C", str(repository_root), "diff", "--cached", "--quiet"],
        check=False,
        capture_output=True,
    )
    if unstaged.returncode != 0 or staged.returncode != 0:
        raise ReconcileError("working tree has staged or unstaged tracked changes; publish the committed main snapshot")


def resolve_snapshot(
    repository_root: str | Path,
    snapshot_commit: str,
    knowledge_path: str = DEFAULT_KNOWLEDGE_PATH,
    schema_path: str | Path = DEFAULT_SCHEMA,
    *,
    source_repository: str | None = None,
    require_origin: bool = True,
) -> Snapshot:
    """Read and validate YAML files from a committed Git tree only."""
    root = Path(repository_root).resolve()
    if _git(root, "rev-parse", "--is-inside-work-tree") != "true":
        raise ReconcileError(f"{root} is not a Git working tree")
    commit = _git(root, "rev-parse", "--verify", f"{snapshot_commit}^{{commit}}")
    branches = set(_git(root, "branch", "--contains", commit, "--format=%(refname:short)").splitlines())
    if "main" not in branches:
        raise ReconcileError(f"snapshot {commit} is not contained in the main branch")
    prefix = knowledge_path.strip("/")
    if prefix != DEFAULT_KNOWLEDGE_PATH:
        raise ReconcileError(
            f"knowledge path must be the canonical {DEFAULT_KNOWLEDGE_PATH!r} directory; refusing a broader or custom subtree"
        )
    _assert_snapshot_is_current(
        root,
        commit,
        expected_source_repository=source_repository,
        require_origin=require_origin,
    )
    tree_paths = _git(root, "ls-tree", "-r", "--name-only", commit, "--", prefix).splitlines()
    yaml_paths = sorted(path for path in tree_paths if path.endswith((".yaml", ".yml")))
    if not yaml_paths:
        raise ReconcileError(f"snapshot {commit} contains no YAML records under {prefix}/")
    entries: list[tuple[str, dict[str, Any]]] = []
    source_paths: dict[str, str] = {}
    for relative_path in yaml_paths:
        raw = _git(root, "show", f"{commit}:{relative_path}")
        try:
            record = yaml.safe_load(raw)
        except yaml.YAMLError as exc:
            raise ValidationFailure([f"{relative_path}: cannot parse YAML: {exc}"]) from exc
        if not isinstance(record, dict):
            raise ValidationFailure([f"{relative_path}: top-level YAML value must be an object"])
        entries.append((relative_path, record))
        if isinstance(record.get("id"), str):
            source_paths[record["id"]] = relative_path
    records = validate_entries(entries, schema_path=schema_path)
    return Snapshot(commit, root, prefix, records, source_paths)


def _canonical_record(record: Mapping[str, Any]) -> str:
    return json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def record_hash(record: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_record(record).encode("utf-8")).hexdigest()


def _source_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Drop publisher-only bookkeeping before rendering or hashing content."""
    return {key: value for key, value in record.items() if not str(key).startswith("_")}


def render_record(record: Mapping[str, Any]) -> str:
    """Render the canonical YAML into the searchable Hindsight document body."""
    return yaml.safe_dump(_source_record(record), allow_unicode=True, sort_keys=True, default_flow_style=False).strip() + "\n"


def record_metadata(
    record: Mapping[str, Any],
    *,
    source_repository: str,
    snapshot_commit: str,
    source_path: str,
) -> dict[str, str]:
    return {
        "managed_by": MANAGED_BY,
        "source_repository": source_repository,
        "knowledge_id": str(record["id"]),
        "source_path": source_path,
        "source_snapshot": snapshot_commit,
        "knowledge_sha256": record_hash(_source_record(record)),
        "status": str(record["status"]),
    }


def _owned_metadata(item: Mapping[str, Any], source_repository: str) -> bool:
    metadata = item.get("document_metadata")
    if not isinstance(metadata, dict):
        # Older Hindsight responses may expose the retain metadata under this
        # compatibility key.  We still require both ownership fields.
        metadata = item.get("metadata")
    return isinstance(metadata, dict) and metadata.get("managed_by") == MANAGED_BY and metadata.get("source_repository") == source_repository


def _deletable_owned_metadata(item: Mapping[str, Any], source_repository: str) -> bool:
    """Require ownership and our canonical source path before orphan deletion."""
    if not _owned_metadata(item, source_repository):
        return False
    metadata = _metadata(item)
    source_path = metadata.get("source_path")
    return isinstance(source_path, str) and source_path.startswith(f"{DEFAULT_KNOWLEDGE_PATH}/") and ".." not in source_path.split("/")


def _metadata(item: Mapping[str, Any]) -> dict[str, Any]:
    value = item.get("document_metadata")
    if isinstance(value, dict):
        return value
    value = item.get("metadata")
    return value if isinstance(value, dict) else {}


def build_plan(
    records: Iterable[Mapping[str, Any]],
    existing_documents: Iterable[Mapping[str, Any]],
    *,
    source_repository: str,
) -> list[PlannedAction]:
    """Build a full snapshot plan, protecting unrelated Hindsight documents."""
    active = {str(record["id"]): record for record in records if record.get("status") == "active"}
    by_id = {str(item.get("id", item.get("document_id", ""))): item for item in existing_documents}
    actions: list[PlannedAction] = []
    for document_id in sorted(active):
        expected = active[document_id]
        current = by_id.get(document_id)
        expected_hash = record_hash(_source_record(expected))
        expected_snapshot = str(expected.get("_source_snapshot", ""))
        current_meta = _metadata(current) if current else {}
        if current and _owned_metadata(current, source_repository) and current_meta.get("knowledge_sha256") == expected_hash and current_meta.get("source_snapshot") == expected_snapshot:
            actions.append(PlannedAction("skip", document_id, "same record and source snapshot"))
        elif current is None:
            actions.append(PlannedAction("upsert", document_id, "new active record"))
        elif _owned_metadata(current, source_repository):
            actions.append(PlannedAction("upsert", document_id, "owned record changed"))
        else:
            # A same-named unrelated document must never be overwritten.
            raise ReconcileError(f"document id {document_id!r} exists but is not owned by {source_repository!r}")

    for document_id, item in sorted(by_id.items()):
        if not document_id or not _deletable_owned_metadata(item, source_repository):
            continue
        source_record = next((record for record in records if str(record.get("id")) == document_id), None)
        if source_record is None or source_record.get("status") == "retired":
            actions.append(PlannedAction("delete", document_id, "retired or orphaned owned record"))
    return actions


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReconcileError(f"cannot read state file {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ReconcileError(f"state file {path} must contain an object")
    return value


def _write_state(path: Path, state: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        json.dump(state, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
        temporary = Path(stream.name)
    os.replace(temporary, path)


def _lock_path(repository_root: Path, bank_id: str) -> Path:
    safe_bank = "".join(character if character.isalnum() or character in "._-" else "_" for character in bank_id)
    return repository_root / f".reconcile-{safe_bank}.lock"


@contextlib.contextmanager
def _reconcile_lock(repository_root: Path, bank_id: str):
    """Serialize a repository/bank reconcile, including remote mutations."""
    path = _lock_path(repository_root, bank_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+", encoding="utf-8")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ReconcileError(f"another reconcile is already running for repository/bank {bank_id!r}") from exc
        yield
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


def _ensure_newer_snapshot(repository_root: Path, current: str, previous: str | None) -> None:
    if not previous or previous == current:
        return
    # A previous successful watermark must be an ancestor of this run.  This
    # rejects stale/out-of-order retries and diverged histories before writes.
    result = subprocess.run(
        ["git", "-C", str(repository_root), "merge-base", "--is-ancestor", previous, current],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ReconcileError(f"snapshot {current} is older than or unrelated to successful snapshot {previous}")


def reconcile(
    snapshot: Snapshot,
    client: HindsightGateway,
    *,
    bank_id: str = DEFAULT_BANK,
    source_repository: str = DEFAULT_SOURCE_REPOSITORY,
    state_file: str | Path | None = None,
    dry_run: bool = False,
    require_origin: bool = True,
) -> list[PlannedAction]:
    """Apply a validated snapshot and return the action plan."""
    try:
        source_repository = normalize_source_repository(source_repository)
    except ValueError as exc:
        raise ReconcileError("source repository must be owner/repository or a strict GitHub HTTPS URL") from exc
    state_path = Path(state_file) if state_file is not None else snapshot.repository_root / DEFAULT_STATE_FILE
    with _reconcile_lock(snapshot.repository_root, bank_id):
        if _git(snapshot.repository_root, "rev-parse", "--is-inside-work-tree", check=False) == "true":
            _assert_snapshot_is_current(
                snapshot.repository_root,
                snapshot.commit,
                expected_source_repository=source_repository,
                require_origin=require_origin,
            )
        state = _load_state(state_path)
        if state.get("bank_id") not in (None, bank_id):
            raise ReconcileError(f"state file {state_path} belongs to bank {state['bank_id']!r}, not {bank_id!r}")
        if state.get("source_repository") not in (None, source_repository):
            raise ReconcileError(
                f"state file {state_path} belongs to source repository {state['source_repository']!r}, not {source_repository!r}"
            )
        _ensure_newer_snapshot(snapshot.repository_root, snapshot.commit, state.get("last_snapshot_commit"))
        records = []
        for record in snapshot.records:
            item = dict(record)
            item["_source_snapshot"] = snapshot.commit
            records.append(item)
        existing = client.list_documents(bank_id)
        plan = build_plan(records, existing, source_repository=source_repository)
        if dry_run:
            return plan

        for action in plan:
            if action.action == "skip":
                continue
            if action.action == "delete":
                client.delete_document(bank_id, action.document_id)
                continue
            record = next(record for record in records if str(record["id"]) == action.document_id)
            client.upsert_document(
                bank_id,
                action.document_id,
                render_record(record),
                record_metadata(
                    record,
                    source_repository=source_repository,
                    snapshot_commit=snapshot.commit,
                    source_path=snapshot.source_paths[action.document_id],
                ),
            )
        # Re-check the fixed branch just before the watermark.  If main moved
        # while the API calls were in flight, leave the watermark untouched;
        # the next manual run reconciles the newer approved snapshot.
        if _git(snapshot.repository_root, "rev-parse", "--is-inside-work-tree", check=False) == "true":
            _assert_snapshot_is_current(
                snapshot.repository_root,
                snapshot.commit,
                expected_source_repository=source_repository,
                require_origin=require_origin,
            )
        # The watermark is intentionally the final operation.  Any failed write
        # leaves the old state untouched, and the next invocation safely retries.
        _write_state(
            state_path,
            {
                "bank_id": bank_id,
                "source_repository": source_repository,
                "last_snapshot_commit": snapshot.commit,
                "managed_document_ids": sorted(record["id"] for record in records if record["status"] == "active"),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".", help="Git repository containing the approved knowledge")
    parser.add_argument("--snapshot-commit", required=True, help="Exact approved commit on main")
    parser.add_argument("--knowledge-path", default=DEFAULT_KNOWLEDGE_PATH, help="Knowledge directory in the Git tree")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA), help="Schema path for local validation")
    parser.add_argument("--bank-id", default=DEFAULT_BANK)
    parser.add_argument("--source-repository", default=DEFAULT_SOURCE_REPOSITORY)
    parser.add_argument("--api-url", default="http://127.0.0.1:8888")
    parser.add_argument("--state-file", help="Watermark JSON path (default: <repo>/.reconcile-state.json)")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--dry-run", action="store_true", help="List planned actions without mutating Hindsight or state")
    args = parser.parse_args(argv)
    try:
        source_repository = normalize_source_repository(args.source_repository)
        snapshot = resolve_snapshot(
            args.repo_root,
            args.snapshot_commit,
            args.knowledge_path,
            args.schema,
            source_repository=source_repository,
            require_origin=True,
        )
        client = HindsightClient(args.api_url, timeout=args.timeout)
        plan = reconcile(
            snapshot,
            client,
            bank_id=args.bank_id,
            source_repository=source_repository,
            state_file=args.state_file,
            dry_run=args.dry_run,
            require_origin=True,
        )
    except (ReconcileError, ValidationFailure) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps({"snapshot_commit": snapshot.commit, "dry_run": args.dry_run, "actions": [action.__dict__ for action in plan]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
