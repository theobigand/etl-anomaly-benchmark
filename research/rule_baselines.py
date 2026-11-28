"""Deterministic constraint baselines for P-SEQ, P-REL and P-NEST (#137, #138, #139).

Three rule baselines, one per unit-level protocol that has no statistical-rule counterpart:

- ``SequenceConstraints`` (P-SEQ, unit ``event_sequence``): a trace violates the constraints
  learned from clean training traces (allowed first event, allowed last event, allowed adjacent
  pairs, length range); the score is the number of violations.
- ``ForeignKeyIntegrity`` (P-REL, unit ``relationship``): a child row violates the declared key
  relation when its key is missing or absent from the parent table; the score is 0 or 1.
- ``SchemaPathRules`` (P-NEST, unit ``nested_path``): for every path of the training schema a
  (record, path) unit violates the rules when a required path is absent or a value has a type
  never seen in training; the score is 0, 1 or 2.

A baseline reads declared or training-derived constraints and the data it scores. It never reads
the injection log, the truth file or the operator, and it learns nothing from the data it scores.
Where a rule detects an injected fault perfectly the result is a ceiling check of the harness, not
evidence of general superiority over a learned detector (see detector_applicability.md).

Neutral infrastructure validated on the synthetic fixtures of ``unit_runner`` only. Using a
baseline scientifically needs the S03 amendment of its unit and an owner decision.

Contract: ``fit(train)`` returns the baseline and raises ``RuleError`` on empty or unusable
training data; ``score(test)`` returns a float ``pd.Series`` indexed by ``str(unit_id)`` exactly as
``unit_scoring`` names units, higher meaning more anomalous. Missing declared information is an
error, never a zero score.
"""

from __future__ import annotations

from itertools import pairwise
from typing import Any

import numpy as np
import pandas as pd
import unit_runner as ur
import unit_scoring as us


class RuleError(Exception):
    """The constraint cannot be learned or applied with the information given."""


class SequenceConstraints:
    """P-SEQ: first and last event, adjacent pairs and length range seen in training traces."""

    first: set[str] | None = None  # None until fitted
    last: set[str]
    pairs: set[tuple[str, str]]
    lengths: tuple[int, int]

    def fit(self, traces: dict[str, list[str]]) -> SequenceConstraints:
        if not traces or any(not events for events in traces.values()):
            raise RuleError("training needs at least one trace and no empty trace")
        self.first = {events[0] for events in traces.values()}
        self.last = {events[-1] for events in traces.values()}
        self.pairs = {pair for events in traces.values() for pair in pairwise(events)}
        sizes = [len(events) for events in traces.values()]
        self.lengths = (min(sizes), max(sizes))
        return self

    def score(self, traces: dict[str, list[str]]) -> pd.Series:
        if self.first is None:
            raise RuleError("the baseline is not fitted")
        out = {}
        for case, events in sorted(traces.items()):
            if not events:
                raise RuleError(f"trace {case!r} is empty")
            violations = sum(pair not in self.pairs for pair in pairwise(events))
            violations += events[0] not in self.first
            violations += events[-1] not in self.last
            violations += not self.lengths[0] <= len(events) <= self.lengths[1]
            out[case] = float(violations)
        return pd.Series(out, dtype=float)


class ForeignKeyIntegrity:
    """P-REL: the child key must exist in the parent key set of the declared relation."""

    def __init__(self, key: str = "parent_id") -> None:
        self.key = key

    def fit(self, tables: dict[str, pd.DataFrame]) -> ForeignKeyIntegrity:
        self._check(tables)
        return self

    def _check(self, tables: dict[str, pd.DataFrame]) -> None:
        for name in ("parent", "child"):
            if name not in tables or self.key not in tables[name].columns:
                raise RuleError(f"the declared relation needs {name}.{self.key}")

    def score(self, tables: dict[str, pd.DataFrame]) -> pd.Series:
        self._check(tables)
        child = tables["child"][self.key]
        present = child.notna() & child.isin(set(tables["parent"][self.key].dropna()))
        return pd.Series(
            (~present).to_numpy(dtype=float), index=[str(i) for i in range(len(child))]
        )


class SchemaPathRules:
    """P-NEST: required paths and the value types seen per path in training records."""

    required: set[str]
    types: dict[str, set[type]] | None = None  # None until fitted

    def fit(self, records: list[dict[str, Any]]) -> SchemaPathRules:
        if not records:
            raise RuleError("training needs at least one record")
        leaves = [us._leaves(record) for record in records]
        types: dict[str, set[type]] = {}
        for record in leaves:
            for path, value in record.items():
                types.setdefault(path, set()).add(type(value))
        self.types = types
        self.required = set.intersection(*(set(record) for record in leaves))
        return self

    def score(self, records: list[dict[str, Any]]) -> pd.Series:
        if self.types is None:
            raise RuleError("the baseline is not fitted")
        out = {}
        for index, record in enumerate(records):
            leaves = us._leaves(record)
            for path in sorted(self.types):
                absent = path not in leaves
                out[str((index, path))] = float(
                    path in self.required if absent else type(leaves[path]) not in self.types[path]
                )
        return pd.Series(out, dtype=float)


BASELINES = {
    "P-SEQ": ("sequence_constraints", SequenceConstraints),
    "P-REL": ("fk_integrity", ForeignKeyIntegrity),
    "P-NEST": ("schema_path_rules", SchemaPathRules),
}


def rule_validation(protocol: str, seed: int, faults: int, budget: float) -> dict[str, Any]:
    """Fit a rule baseline on a clean synthetic fixture and score an injected one at the budget."""
    if protocol not in BASELINES:
        raise ValueError(f"no rule baseline for protocol {protocol!r}")
    name, make = BASELINES[protocol]
    runner = ur.RUNNERS[protocol]
    train = runner.make(np.random.default_rng(seed + 1))
    test = runner.make(np.random.default_rng(seed))
    injected, truth = runner.inject(test, faults, seed)
    scores = make().fit(train).score(injected)
    scores = scores.loc[[str(unit) for unit in runner.units(injected)]]
    k = us.alert_count(len(scores), budget)
    alerts = us.select_alerts(scores, k)
    positives = sorted(str(t) for t in truth)
    return {
        "protocol": protocol,
        "baseline": name,
        "unit": runner.unit,
        "synthetic": True,
        "units": len(scores),
        "positives": len(positives),
        "k": k,
        "recall": us.recall_at_k(alerts, positives),
        "max_recall": us.max_recall(k, len(positives)),
        "alerts": alerts,
    }
