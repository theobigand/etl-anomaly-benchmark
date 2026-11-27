"""Unit-level scoring contract and featurizers for the five protocol-defined units (#136-#139).

Neutral infrastructure validated on the synthetic fixtures of ``unit_runner`` only. Nothing here
reads a benchmark view, and the featurizers are proposals: using one scientifically needs the
S03 amendment of its unit (``verification/unit_amendment_proposals.md``) and an owner decision.

Contract (all five units):

- a featurizer turns the data of a protocol into one numeric row per detection unit, indexed by
  ``str(unit_id)`` exactly as ``unit_runner`` names truth units; it is fitted on training data only
  where it needs a vocabulary (traces, nested paths);
- a detector of ``etl_benchmark.quality`` is fitted on the training features and returns one score
  per unit, higher meaning more anomalous;
- the alert set has ``k = floor(B x N)`` units, the same ``k`` for every detector, ordered by score
  and then by the SHA-256 of the unit identifier; there is no minimum-one-alert exception and a
  missing score is an error, not a low score;
- recall at ``k`` is the share of the injected units among the alerts, at most ``min(1, k / P)``.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable
from typing import Any

import numpy as np
import pandas as pd
import unit_runner as ur

REFERENCE_CHECK_NOTE = (
    "reference_present is a declared-constraint feature: with it a learned detector sees the "
    "foreign-key check itself, so a perfect result on referential faults is by construction"
)


def alert_count(units: int, budget: float) -> int:
    """``floor(budget x units)``, immune to binary rounding (0.29 x 100 is 28.999999999999996)."""
    if not 0 < budget <= 1:
        raise ValueError("the budget must be in (0, 1]")
    return math.floor(round(budget * units, 9))


def tie_key(unit_id: str) -> str:
    return hashlib.sha256(unit_id.encode()).hexdigest()


def select_alerts(scores: pd.Series, k: int) -> list[str]:
    """The ``k`` highest-scored units; ties by the SHA-256 of the unit identifier."""
    if scores.isna().any():
        raise ValueError("a missing score is not a score")
    if scores.index.has_duplicates:
        raise ValueError("unit identifiers must be unique")
    order = sorted(scores.index, key=lambda unit: (-float(scores[unit]), tie_key(str(unit))))
    return [str(unit) for unit in order[: max(0, k)]]


def recall_at_k(alerts: list[str], truth: list[str]) -> float:
    if not truth:
        raise ValueError("recall needs at least one positive unit")
    return len(set(alerts) & set(truth)) / len(set(truth))


def max_recall(k: int, positives: int) -> float:
    return min(1.0, k / positives)


# P-TAB: one row per table row
def tab_features(data: pd.DataFrame) -> pd.DataFrame:
    out = data.select_dtypes(include=np.number).astype(float).copy()
    out.index = [str(i) for i in range(len(data))]
    return out


# P-TS: window statistics, one row per (series, window)
def window_features(wide: pd.DataFrame, window: int = ur.WINDOW) -> pd.DataFrame:
    rows: dict[str, list[float]] = {}
    positions = np.arange(window, dtype=float)
    for name in wide.columns:
        values = wide[name].to_numpy(dtype=float)
        for w in range(len(values) // window):
            chunk = values[w * window : (w + 1) * window]
            slope = float(np.polyfit(positions, chunk, 1)[0])
            rows[str((name, w))] = [
                chunk.mean(),
                chunk.std(),
                chunk.min(),
                chunk.max(),
                slope,
                float(np.abs(np.diff(chunk)).mean()),
            ]
    return pd.DataFrame.from_dict(
        rows, orient="index", columns=["mean", "std", "min", "max", "slope", "mean_abs_diff"]
    )


class SequenceFeaturizer:
    """P-SEQ: length, unseen bigrams and counts of the bigrams seen in training traces."""

    def __init__(self) -> None:
        self.bigrams: list[tuple[str, str]] = []

    def fit(self, traces: dict[str, list[str]]) -> SequenceFeaturizer:
        seen = {
            pair for events in traces.values() for pair in zip(events, events[1:], strict=False)
        }
        self.bigrams = sorted(seen)
        return self

    def transform(self, traces: dict[str, list[str]]) -> pd.DataFrame:
        known = set(self.bigrams)
        rows = {}
        for case, events in sorted(traces.items()):
            pairs = list(zip(events, events[1:], strict=False))
            rows[case] = [
                float(len(events)),
                float(sum(pair not in known for pair in pairs)),
                *[float(pairs.count(pair)) for pair in self.bigrams],
            ]
        columns = ["length", "unseen_bigrams", *[f"{a}>{b}" for a, b in self.bigrams]]
        return pd.DataFrame.from_dict(rows, orient="index", columns=columns)


def relationship_features(
    tables: dict[str, pd.DataFrame], key: str = "parent_id", reference_check: bool = False
) -> pd.DataFrame:
    """P-REL: the numeric columns of the child rows, plus ``reference_present`` if requested."""
    child = tables["child"]
    out = child.select_dtypes(include=np.number).astype(float).copy()
    if reference_check:
        out["reference_present"] = child[key].isin(set(tables["parent"][key])).astype(float)
    out.index = [str(i) for i in range(len(child))]
    return out


def _leaves(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict) and value:
        return {
            path: leaf
            for name, inner in value.items()
            for path, leaf in _leaves(inner, f"{prefix}.{name}" if prefix else str(name)).items()
        }
    return {prefix: value}


_TYPE_CODE = {bool: 1.0, int: 2.0, float: 2.0, str: 3.0, list: 4.0, dict: 5.0}


class PathFeaturizer:
    """P-NEST: presence, type, depth and size of every leaf path seen in training records.

    Nesting is kept: the unit is a (record, path) pair and records are never flattened into a
    single row; a path absent from a record is a unit with ``present = 0``.
    """

    def __init__(self) -> None:
        self.paths: list[str] = []

    def fit(self, records: list[dict[str, Any]]) -> PathFeaturizer:
        self.paths = sorted({path for record in records for path in _leaves(record)})
        return self

    def transform(self, records: list[dict[str, Any]]) -> pd.DataFrame:
        rows = {}
        for index, record in enumerate(records):
            leaves = _leaves(record)
            for path in self.paths:
                if path in leaves:
                    value = leaves[path]
                    number = float(value) if isinstance(value, (int, float)) else 0.0
                    size = float(len(value)) if isinstance(value, (str, list)) else 0.0
                    row = [
                        1.0,
                        _TYPE_CODE.get(type(value), 6.0),
                        float(path.count(".") + 1),
                        number,
                        size,
                    ]
                else:
                    row = [0.0, 0.0, float(path.count(".") + 1), 0.0, 0.0]
                rows[str((index, path))] = row
        return pd.DataFrame.from_dict(
            rows, orient="index", columns=["present", "type", "depth", "number", "size"]
        )


def _featurize(protocol: str, train: Any, test: Any, reference_check: bool):
    if protocol == "P-TAB":
        return tab_features(train), tab_features(test)
    if protocol == "P-TS":
        return window_features(train), window_features(test)
    if protocol == "P-SEQ":
        featurizer = SequenceFeaturizer().fit(train)
        return featurizer.transform(train), featurizer.transform(test)
    if protocol == "P-REL":
        return (
            relationship_features(train, reference_check=reference_check),
            relationship_features(test, reference_check=reference_check),
        )
    if protocol == "P-NEST":
        featurizer = PathFeaturizer().fit(train)
        return featurizer.transform(train), featurizer.transform(test)
    raise ValueError(f"no featurizer for protocol {protocol!r}")


def synthetic_validation(
    protocol: str,
    make_detector: Callable[[], Any],
    seed: int,
    faults: int,
    budget: float,
    reference_check: bool = False,
) -> dict[str, Any]:
    """Fit a detector on a clean synthetic fixture and score an injected one at the budget."""
    import numpy.random as npr

    runner = ur.RUNNERS[protocol]
    train = runner.make(npr.default_rng(seed + 1))
    test = runner.make(npr.default_rng(seed))
    injected, truth = runner.inject(test, faults, seed)
    train_x, test_x = _featurize(protocol, train, injected, reference_check)
    # the runner defines the evaluated units; the P-NEST featurizer covers every leaf path
    test_x = test_x.loc[[str(unit) for unit in runner.units(injected)]]
    detector = make_detector().fit(train_x)
    scores = detector.score(test_x)
    k = alert_count(len(test_x), budget)
    alerts = select_alerts(scores, k)
    positives = sorted(str(t) for t in truth)
    return {
        "protocol": protocol,
        "unit": runner.unit,
        "synthetic": True,
        "units": len(test_x),
        "positives": len(positives),
        "k": k,
        "recall": recall_at_k(alerts, positives),
        "max_recall": max_recall(k, len(positives)),
        "alerts": alerts,
    }
