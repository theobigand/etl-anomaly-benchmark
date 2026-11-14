# ruff: noqa: E501
"""Bounded, deterministic evidence for the mutants that the native run reports as timeouts.

    python docs/thesis-remediation/evidence/timeout_evidence.py

Nothing here counts a timeout as a kill. For each mutant the script states what the mutated code does
under an explicit iteration budget, so that "the run hit the wall-clock limit" can be classified as a
genuine non-terminating mutant (the result stays a timeout: not killed, not survived) or as excessive work.
"""

import hashlib
import io
import json
import sys
from itertools import islice
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BUDGET = 10_000


def sha256_file_sentinel(sentinel) -> dict:
    """pool_contract.sha256_file mutants 6 (sentinel None) and 14 (sentinel b"XXXX")."""
    stream = io.BytesIO(b"abc")
    reads = iter(lambda: stream.read(1 << 20), sentinel)
    blocks = list(islice(reads, BUDGET))
    return {
        "blocks_read_within_budget": len(blocks),
        "budget": BUDGET,
        "non_empty_blocks": sum(1 for b in blocks if b),
        "terminated": len(blocks) < BUDGET,
        "expected_digest": hashlib.sha256(b"abc").hexdigest(),
    }


def prepare_execution_without_pop() -> dict:
    """mutation_cache.prepare_execution mutant 128: ``graph.get(None, [])`` for ``graph.get(queue.pop(), [])``."""
    graph = {"pkg.a.x_f": ["pkg.b.x_g"]}
    changed = {"pkg.a.x_f"}
    queue = list(changed)
    sizes = []
    for _ in range(BUDGET):
        if not queue:
            break
        for caller in graph.get(None, []):
            if caller not in changed:
                changed.add(caller)
                queue.append(caller)
        sizes.append(len(queue))
    return {
        "iterations": len(sizes),
        "budget": BUDGET,
        "queue_length_first_and_last": [sizes[0], sizes[-1]] if sizes else [],
        "terminated": len(sizes) < BUDGET,
    }


def block_ci_cost() -> dict:
    """temporal_decision._block_ci mutant 25: one precision-recall area on a one-row array per resample."""
    import time

    import numpy as np
    import temporal_decision as td
    from sklearn.metrics import average_precision_score

    rows = {}
    for n in (40, 200, 1000):
        rng = np.random.default_rng(0)
        y = (rng.random(n) < 0.2).astype(int)
        scores = rng.random(n)
        start = time.perf_counter()
        td._block_ci(y, scores)
        original = time.perf_counter() - start
        start = time.perf_counter()
        average_precision_score(y[None], scores[None])
        one_call = time.perf_counter() - start
        rows[str(n)] = {
            "original_block_ci_s": round(original, 3),
            "mutant_one_resample_s": round(one_call, 4),
            "mutant_estimated_total_s": round(one_call * td.RESAMPLES, 1),
            "resamples": td.RESAMPLES,
        }
    return rows


def main() -> None:
    sys.path[:0] = [str(ROOT / "research"), str(ROOT / "src"), str(ROOT)]
    report = {
        "pool_contract.sha256_file__mutmut_6": sha256_file_sentinel(None),
        "pool_contract.sha256_file__mutmut_14": sha256_file_sentinel(b"XXXX"),
        "mutation_cache.prepare_execution__mutmut_128": prepare_execution_without_pop(),
        "temporal_decision._block_ci__mutmut_25 (measured on the machine that ran this script)": block_ci_cost(),
        "classification": {
            "sha256_file mutants 6 and 14": (
                "non-terminating: the end-of-file sentinel can never match, so the read loop runs "
                "forever; status stays timeout (not killed)"
            ),
            "prepare_execution mutant 128": (
                "non-terminating: the queue is never popped; status stays timeout (not killed)"
            ),
            "cost_study.wait_for_quiet mutant 12 (`<` -> `<=` on the deadline)": (
                "non-terminating only under the former test, which froze the clock at the deadline forever; "
                "in use the clock advances. The test now supplies a finite clock, so the mutant raises "
                "StopIteration instead of looping."
            ),
            "temporal_decision._block_ci mutant 25": (
                "not a hang: the mutant returns a result computed on a one-row array per resample, "
                "slower than the original by the factor measured above (it grows with the number of rows). Slow tests ran before the detecting test and "
                "exceeded the limit. Resolved by shortening those tests (RESAMPLES patched), see the tests."
            ),
        },
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
