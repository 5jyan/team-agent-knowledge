"""A tiny buffer-copy optimizer used by the team-memory demo.

This is a toy memory model for the exercise, not a production compiler.  The
first revision (``r1_naive_copy``) is intentionally kept as a regression
fixture.  The public ``copy_range`` entry point implements the current team
rule: use the fast forward copy for non-overlapping ranges and take a snapshot
when the ranges overlap.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class CopyPlan:
    """Decision recorded by the toy optimizer for one copy operation."""

    knowledge_id: str
    revision: Literal["r1", "r2"]
    path: Literal["nonoverlap-fast", "overlap-safe"]


def _validate(memory: bytearray, src: int, dst: int, length: int) -> None:
    if not isinstance(memory, bytearray):
        raise TypeError("memory must be a bytearray")
    if any(not isinstance(value, int) for value in (src, dst, length)):
        raise TypeError("src, dst, and length must be integers")
    if src < 0 or dst < 0 or length < 0:
        raise ValueError("src, dst, and length must be non-negative")
    if src + length > len(memory) or dst + length > len(memory):
        raise ValueError("copy range is outside the toy buffer")


def _overlaps(src: int, dst: int, length: int) -> bool:
    return length > 0 and src < dst + length and dst < src + length


def plan_copy(memory: bytearray, src: int, dst: int, length: int) -> CopyPlan:
    """Return the rule/revision used for a copy without mutating ``memory``."""

    _validate(memory, src, dst, length)
    if _overlaps(src, dst, length):
        return CopyPlan("COMP-014", "r2", "overlap-safe")
    return CopyPlan("COMP-014", "r1", "nonoverlap-fast")


def r1_naive_copy(memory: bytearray, src: int, dst: int, length: int) -> None:
    """Revision r1 fixture: a forward loop that is unsafe for overlap."""

    _validate(memory, src, dst, length)
    for offset in range(length):
        memory[dst + offset] = memory[src + offset]


def copy_range(memory: bytearray, src: int, dst: int, length: int) -> CopyPlan:
    """Apply the current safe rule and return the selected knowledge plan.

    The overlap branch snapshots source bytes before writing.  That keeps the
    intentionally broken r1 fixture available for the regression test while
    ensuring callers use r2 by default.
    """

    plan = plan_copy(memory, src, dst, length)
    if plan.path == "nonoverlap-fast":
        r1_naive_copy(memory, src, dst, length)
    else:
        snapshot = memory[src : src + length]
        for offset, value in enumerate(snapshot):
            memory[dst + offset] = value
    return plan
