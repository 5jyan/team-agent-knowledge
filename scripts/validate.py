#!/usr/bin/env python3
"""Validate canonical team knowledge records.

The default check is local and deterministic.  Remote Git evidence is checked
only when ``--verify-remote`` is explicitly passed; a local pass never implies
that a remote commit was fetched or that a test command was executed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

import jsonschema
import yaml


DEFAULT_SCHEMA = Path(__file__).resolve().parents[1] / "schemas" / "knowledge.schema.yaml"
DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "knowledge"
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
    re.compile(r"\b(?:sk|rk)-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{16,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
)


class ValidationFailure(ValueError):
    """Raised when one or more records do not meet the trust-boundary checks."""

    def __init__(self, errors: list[str]):
        self.errors = sorted(errors)
        super().__init__("\n".join(self.errors))


_GITHUB_SEGMENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
_COMMIT = re.compile(r"^[0-9a-fA-F]{40}$")


def normalize_github_repository_url(value: str) -> str:
    """Return ``owner/repository`` for a credential-free GitHub HTTPS URL."""
    if not isinstance(value, str):
        raise ValueError("repository must be a string")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("repository must be a strict GitHub HTTPS URL") from exc
    if (
        parsed.scheme.lower() != "https"
        or parsed.netloc.lower() != "github.com"
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or parsed.query
        or parsed.fragment
        or "%" in parsed.path
    ):
        raise ValueError("repository must be a strict GitHub HTTPS URL")
    parts = parsed.path.split("/")
    if len(parts) != 3 or not all(_GITHUB_SEGMENT.fullmatch(part) for part in parts[1:]):
        raise ValueError("repository must be a strict GitHub HTTPS URL")
    repository = parts[2]
    if repository.endswith(".git"):
        repository = repository[:-4]
    if not repository or repository == ".git" or not _GITHUB_SEGMENT.fullmatch(repository):
        raise ValueError("repository must be a strict GitHub HTTPS URL")
    return f"{parts[1].lower()}/{repository.lower()}"


def normalize_source_repository(value: str) -> str:
    """Normalize the CLI source repository without accepting credentials/protocols."""
    if not isinstance(value, str):
        raise ValueError("source repository must be owner/repository or a strict GitHub HTTPS URL")
    if value.lower().startswith("https://"):
        return normalize_github_repository_url(value)
    parts = value.split("/")
    if len(parts) == 2 and all(_GITHUB_SEGMENT.fullmatch(part) for part in parts):
        repository = parts[1][:-4] if parts[1].endswith(".git") else parts[1]
        if repository and _GITHUB_SEGMENT.fullmatch(repository):
            return f"{parts[0].lower()}/{repository.lower()}"
    raise ValueError("source repository must be owner/repository or a strict GitHub HTTPS URL")


def _iter_scalars(value: Any, path: str = "") -> Iterable[tuple[str, str]]:
    if isinstance(value, dict):
        for key, item in value.items():
            key_path = f"{path}.{key}" if path else str(key)
            yield from _iter_scalars(item, key_path)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _iter_scalars(item, f"{path}[{index}]")
    elif isinstance(value, str):
        yield path, value


def _secret_errors(record: Any, source: str) -> list[str]:
    errors: list[str] = []
    for path, scalar in _iter_scalars(record):
        if any(pattern.search(scalar) for pattern in SECRET_PATTERNS):
            errors.append(f"{source}:{path}: possible secret detected")
    return errors


def discover_files(paths: Iterable[str | Path]) -> list[Path]:
    """Expand files/directories and return stable YAML file order."""
    candidates: list[Path] = []
    for raw_path in paths:
        path = Path(raw_path)
        if path.is_dir():
            candidates.extend(path.rglob("*.yaml"))
            candidates.extend(path.rglob("*.yml"))
        elif path.is_file():
            candidates.append(path)
        else:
            raise ValidationFailure([f"{path}: file or directory does not exist"])
    result = sorted({item.resolve() for item in candidates})
    # An empty, existing knowledge directory is a valid initial repository
    # state.  The publisher still refuses to reconcile an empty Git snapshot so
    # a missing checkout can never become a destructive delete-all operation.
    return result


def load_schema(schema_path: str | Path = DEFAULT_SCHEMA) -> dict[str, Any]:
    with Path(schema_path).open(encoding="utf-8") as stream:
        schema = yaml.safe_load(stream)
    if not isinstance(schema, dict):
        raise ValidationFailure([f"{schema_path}: schema must be a YAML object"])
    return schema


def load_records(paths: Iterable[str | Path], schema_path: str | Path = DEFAULT_SCHEMA) -> list[dict[str, Any]]:
    """Load and validate records, returning them in path order.

    ``jsonschema`` performs shape/type checks; the surrounding checks enforce
    repository conventions that a generic schema cannot express (file/id
    agreement, duplicates, secrets, and retired-record evidence).
    """
    schema = load_schema(schema_path)
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    files = discover_files(paths)
    entries: list[tuple[str, dict[str, Any]]] = []
    errors: list[str] = []

    for path in files:
        source = str(path)
        try:
            with path.open(encoding="utf-8") as stream:
                record = yaml.safe_load(stream)
        except (OSError, yaml.YAMLError) as exc:
            errors.append(f"{source}: cannot parse YAML: {exc}")
            continue
        if not isinstance(record, dict):
            errors.append(f"{source}: top-level YAML value must be an object")
            continue
        entries.append((source, record))

    errors.extend(_validate_entries(entries, validator))

    if errors:
        raise ValidationFailure(errors)
    return [record for _, record in entries]


def _validate_entries(
    entries: Iterable[tuple[str, dict[str, Any]]],
    validator: jsonschema.Draft202012Validator,
) -> list[str]:
    """Validate already parsed records, preserving source names in errors."""
    errors: list[str] = []
    seen_ids: dict[str, str] = {}
    for source, record in entries:
        for issue in sorted(validator.iter_errors(record), key=lambda error: list(error.path)):
            location = ".".join(str(part) for part in issue.absolute_path) or "<root>"
            errors.append(f"{source}:{location}: {issue.message}")
        errors.extend(_secret_errors(record, source))
        evidence = record.get("evidence")
        if isinstance(evidence, dict) and isinstance(evidence.get("repository"), str):
            try:
                normalize_github_repository_url(evidence["repository"])
            except ValueError:
                errors.append(f"{source}:evidence.repository: must be a strict https://github.com/owner/repository[.git] URL")
        record_id = record.get("id")
        if isinstance(record_id, str):
            stem = Path(source).stem
            if stem != record_id:
                errors.append(f"{source}: filename stem must match id {record_id!r}")
            previous = seen_ids.get(record_id)
            if previous is not None:
                errors.append(f"{source}: duplicate id {record_id!r}; first seen in {previous}")
            else:
                seen_ids[record_id] = source
        if record.get("status") == "retired":
            evidence = record.get("evidence")
            if not isinstance(evidence, dict) or not evidence.get("tests"):
                errors.append(f"{source}: retired record must preserve evidence.tests")
    return errors


def validate_entries(
    entries: Iterable[tuple[str, dict[str, Any]]],
    schema_path: str | Path = DEFAULT_SCHEMA,
) -> list[dict[str, Any]]:
    """Validate records read from a Git snapshot or another immutable source."""
    schema = load_schema(schema_path)
    validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
    materialized = list(entries)
    errors = _validate_entries(materialized, validator)
    if errors:
        raise ValidationFailure(errors)
    return [record for _, record in materialized]


def verify_remote_evidence(records: Iterable[dict[str, Any]], timeout: int = 20) -> None:
    """Verify each record's cited commit can be fetched from its Git remote.

    ``git ls-remote <sha>`` only matches advertised refs; a valid historical
    commit is not itself a ref.  A shallow, blobless fetch into a temporary
    bare repository checks the object while using the user's configured Git
    credentials for private repositories and never printing them.
    """
    errors: list[str] = []
    for record in records:
        evidence = record["evidence"]
        try:
            repository = normalize_github_repository_url(str(evidence["repository"]))
        except ValueError:
            errors.append(f"{record['id']}: evidence.repository is not a strict GitHub HTTPS URL")
            continue
        commit = str(evidence["commit"])
        if not _COMMIT.fullmatch(commit):
            errors.append(f"{record['id']}: evidence.commit must be a 40-character hexadecimal SHA")
            continue
        repository_url = f"https://github.com/{repository}.git"
        git_env = dict(os.environ)
        git_env["GIT_ALLOW_PROTOCOL"] = "https"
        with tempfile.TemporaryDirectory(prefix="team-knowledge-remote-") as directory:
            bare = Path(directory) / "remote.git"
            try:
                initialized = subprocess.run(
                    ["git", "init", "--bare", str(bare)],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    env=git_env,
                )
                fetched = subprocess.run(
                    [
                        "git",
                        "-C",
                        str(bare),
                        "fetch",
                        "--quiet",
                        "--no-tags",
                        "--filter=blob:none",
                        "--depth=1",
                        repository_url,
                        commit,
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    env=git_env,
                )
                checked = subprocess.run(
                    ["git", "-C", str(bare), "cat-file", "-e", f"{commit}^{{commit}}"],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    env=git_env,
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                errors.append(f"{record['id']}: remote evidence check failed")
                continue
        if initialized.returncode != 0 or fetched.returncode != 0 or checked.returncode != 0:
            errors.append(f"{record['id']}: cited GitHub commit could not be fetched or verified")
    if errors:
        raise ValidationFailure(errors)


def validate(paths: Iterable[str | Path], *, schema_path: str | Path = DEFAULT_SCHEMA, verify_remote: bool = False) -> list[dict[str, Any]]:
    records = load_records(paths, schema_path=schema_path)
    if verify_remote:
        verify_remote_evidence(records)
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="YAML record files or directories")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA), help="JSON Schema YAML path")
    parser.add_argument("--verify-remote", action="store_true", help="Explicitly fetch and verify evidence commits")
    args = parser.parse_args(argv)
    try:
        records = validate(args.paths or [DEFAULT_ROOT], schema_path=args.schema, verify_remote=args.verify_remote)
    except ValidationFailure as exc:
        print(str(exc), file=sys.stderr)
        return 1
    suffix = " (remote commits verified)" if args.verify_remote else " (local checks only)"
    print(f"validated {len(records)} knowledge record(s){suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
