# Compiler memory demo

This directory is a small, executable toy example for the team-agent knowledge
store. It models a byte buffer copy decision; it is not a real compiler and it
does not claim a performance improvement.

The script simulates the A/B workflow with deterministic Python functions; it
does not call an AI agent or Hindsight. The scenario is deliberately narrow:

1. Agent A verifies `COMP-014 r1`: a forward copy is valid when the source and
   destination ranges do not overlap, and records the test as evidence.
2. Agent B retrieves that team rule and reuses the public `copy_range` entry
   point for another non-overlapping task.
3. A new overlapping-buffer case exposes the limitation of the original
   forward loop. The `r1_naive_copy` function remains as an explicit regression
   fixture so the failure is reproducible.
4. The team updates the rule to `COMP-014 r2`: keep the fast path for
   non-overlap and snapshot source bytes for overlap. `copy_range` uses this
   safe behavior by default, so the broken fixture is never shipped as the
   public behavior.

The expected overlap result for copying four bytes from offset `0` to offset
`2` in `abcdef` is `ababcd` (the usual snapshot/memmove semantics). The naive
fixture produces `ababab`, demonstrating why the applicability condition must
be part of shared knowledge.

Run from the repository root:

```bash
python3 -m unittest discover -s examples/demo-compiler -p 'test_*.py' -v
python3 examples/demo-compiler/run_demo.py
```

To make the provenance explicit in a captured demo, pass the commit you are
reviewing:

```bash
DEMO_SOURCE_COMMIT="$(git rev-parse HEAD)" \
  python3 examples/demo-compiler/run_demo.py
```

The demo prints that source commit along with A's verification, B's reuse, the
r1 regression, and the r2 correction. The tests use only Python's standard
library and deterministic byte arrays, so they can be rerun from a clean clone.
