"""Print the reproducible A -> B -> regression -> r2 demo."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from optimizer import copy_range, r1_naive_copy


def source_commit() -> str:
    """Read an explicit provenance override or the containing Git revision."""

    if override := os.environ.get("DEMO_SOURCE_COMMIT"):
        return override
    try:
        root = Path(__file__).resolve().parents[2]
        return subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "uncommitted-working-tree"


def show(label: str, memory: bytearray) -> str:
    return f"{label}: {memory.decode('ascii')}"


def main() -> None:
    print("SIMULATION: no AI agent or Hindsight is invoked")
    print(f"source_commit: {source_commit()}")

    # A verifies that r1 is safe only when source/destination ranges do not overlap.
    a_memory = bytearray(b"abcdefgh")
    a_plan = copy_range(a_memory, src=0, dst=4, length=4)
    print(f"A verified nonoverlap ({a_plan.knowledge_id} {a_plan.revision})")
    print(show("  result", a_memory))

    # B reuses the public safe entry point for the same non-overlap task.
    b_memory = bytearray(b"abcdefgh")
    b_plan = copy_range(b_memory, src=0, dst=4, length=4)
    print(f"B reused team rule ({b_plan.knowledge_id} {b_plan.revision})")
    print(show("  result", b_memory))

    # New evidence: the old forward loop fails for overlapping ranges.
    broken = bytearray(b"abcdef")
    r1_naive_copy(broken, src=0, dst=2, length=4)
    print("r1 overlap regression")
    print(show("  r1 result", broken))
    print("  expected: ababcd")

    # The updated team rule adds a safe overlap path and becomes the default.
    corrected = bytearray(b"abcdef")
    r2_plan = copy_range(corrected, src=0, dst=2, length=4)
    print(f"r2 corrected ({r2_plan.knowledge_id} {r2_plan.revision})")
    print(show("  result", corrected))


if __name__ == "__main__":
    main()
