"""Registry-driven synthetic runner of the unit-level protocols (#135, #137, #138, #139).

One ``Runner`` per protocol (P-TAB, P-TS, P-SEQ, P-REL, P-NEST) ties together the unit the
protocol defines, the controlled-fault operator of ``fault_protocols`` and the ground truth in that
unit. ``execute`` generates nothing from real data: it accepts only a ``Fixture``, which is built
from the seeded synthetic generators below, and refuses a scientific run. It injects ``k`` faults,
then checks the contract of the protocol: the truth lies inside the units, exactly the truth units
changed, the input was not modified, the run is deterministic for its seed, and natural baseline
defects are reported apart from the injected faults. No detector is fitted, nothing is scored.

The units are the ones ``compatibility_model.UNITS`` registers for the protocols; their status
there (protocol defined or provisional) is copied into every result. A synthetic run is software
validation. It does not make a group executable in the utilization ledger, does not use a real
view and is never a scientific result; scientific use waits for the unit approval (S03, #154) and
for the end of the experiment freeze. The module names no dataset.
"""

from __future__ import annotations

import argparse
import copy
import json
import logging
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from typing import Any

import compatibility_model as cm
import fault_protocols as fp
import numpy as np
import obs_events
import obs_failures as of
import obs_tracing
import pandas as pd

LOG = logging.getLogger("etl.unit_runner")
WINDOW = 10
FREEZE_REASON = "the experiment freeze is active and the unit is not approved for scientific use"


class Refused(Exception):
    """The request would be a scientific run, which no synthetic runner may perform."""


@dataclass(frozen=True)
class Fixture:
    """Seeded synthetic data for one protocol; the only input ``execute`` accepts."""

    protocol: str
    data: Any
    seed: int
    origin: str = "synthetic"

    def __post_init__(self) -> None:
        if self.origin != "synthetic":
            raise Refused(f"only synthetic fixtures are accepted, not {self.origin!r}")


@dataclass(frozen=True)
class Runner:
    protocol: str
    unit: str
    units: Callable[[Any], list[Any]]
    inject: Callable[[Any, int, int], tuple[Any, list[Any]]]
    changed: Callable[[Any, Any], list[Any]]
    baseline: Callable[[Any], int]
    make: Callable[[np.random.Generator], Any]


@dataclass(frozen=True)
class UnitRun:
    protocol: str
    unit: str
    unit_status: str
    synthetic: bool
    seed: int
    faults: int
    units: int
    truth: list[str]
    baseline: int
    checks: dict[str, bool]


def _ids(values: list[Any]) -> list[str]:
    return sorted(str(v) for v in values)


# P-TAB: the unit is a row; the operator scales one numeric column
def _tab_make(rng: np.random.Generator) -> pd.DataFrame:
    return pd.DataFrame({"amount": rng.uniform(1, 100, 80), "ident": np.arange(80)})


def _tab_inject(data: pd.DataFrame, k: int, seed: int) -> tuple[pd.DataFrame, list[Any]]:
    out, rows = fp.inject_scale(data, "amount", k, 5.0, seed)
    return out, rows


def _tab_changed(before: pd.DataFrame, after: pd.DataFrame) -> list[Any]:
    return [i for i in range(len(before)) if before["amount"].iloc[i] != after["amount"].iloc[i]]


# P-TS: the unit is a window of WINDOW consecutive points of one series; the operator shifts level
def _ts_make(rng: np.random.Generator) -> pd.DataFrame:
    return pd.DataFrame({"s0": rng.normal(0, 1, 12 * WINDOW), "s1": rng.normal(5, 1, 12 * WINDOW)})


def _ts_units(wide: pd.DataFrame) -> list[Any]:
    return [(name, w) for name in wide.columns for w in range(len(wide) // WINDOW)]


def _ts_inject(wide: pd.DataFrame, k: int, seed: int) -> tuple[pd.DataFrame, list[Any]]:
    windows = fp.choose_within(list(range(len(wide) // WINDOW)), k, seed)
    out = wide
    for w in windows:
        out, _ = fp.inject_level_shift(out, "s0", w * WINDOW, WINDOW, 4.0)
    return out, [("s0", w) for w in windows]


def _ts_changed(before: pd.DataFrame, after: pd.DataFrame) -> list[Any]:
    return [
        (name, w)
        for name, w in _ts_units(before)
        if not before[name]
        .iloc[w * WINDOW : (w + 1) * WINDOW]
        .equals(after[name].iloc[w * WINDOW : (w + 1) * WINDOW])
    ]


# P-SEQ: the unit is a trace; the operator swaps two adjacent events of a trace
def _seq_make(rng: np.random.Generator) -> dict[str, list[str]]:
    order = ["create", "validate", "load", "verify", "publish"]
    return {f"case-{i:02d}": [*order, f"close-{i % 3}"] for i in range(int(rng.integers(20, 30)))}


def _seq_inject(
    data: dict[str, list[str]], k: int, seed: int
) -> tuple[dict[str, list[str]], list[Any]]:
    names = fp.choose_within(sorted(data), k, seed)
    out = data
    for name in names:
        out, _ = fp.swap_adjacent(out, name, seed % (len(data[name]) - 1))
    return out, names


def _seq_changed(before: dict[str, list[str]], after: dict[str, list[str]]) -> list[Any]:
    return [name for name in before if before[name] != after[name]]


# P-REL: the unit is a child row holding a declared reference; the operator breaks references
def _rel_make(rng: np.random.Generator) -> dict[str, pd.DataFrame]:
    parent = pd.DataFrame({"parent_id": np.arange(1, 21)})
    refs = rng.integers(1, 21, 60)
    refs[:2] = [900, 901]  # natural orphans: part of the baseline, never labelled
    return {"parent": parent, "child": pd.DataFrame({"parent_id": refs})}


def _rel_units(tables: dict[str, pd.DataFrame]) -> list[Any]:
    return list(range(len(tables["child"])))


def _rel_inject(
    tables: dict[str, pd.DataFrame], k: int, seed: int
) -> tuple[dict[str, pd.DataFrame], list[Any]]:
    child, rows, _ = fp.break_foreign_key(
        tables["child"], "parent_id", set(tables["parent"]["parent_id"]), k, seed
    )
    return {**tables, "child": child}, rows


def _rel_changed(before: dict[str, pd.DataFrame], after: dict[str, pd.DataFrame]) -> list[Any]:
    old, new = before["child"]["parent_id"], after["child"]["parent_id"]
    return [i for i in range(len(old)) if old.iloc[i] != new.iloc[i]]


def _rel_baseline(tables: dict[str, pd.DataFrame]) -> int:
    keys = set(tables["parent"]["parent_id"])
    return int((~tables["child"]["parent_id"].isin(keys)).sum())


# P-NEST: the unit is a (record, path) pair; the operator removes a nested field
PATH = "meta.owner.name"


def _nest_make(rng: np.random.Generator) -> list[dict[str, Any]]:
    return [
        {"id": i, "meta": {"owner": {"name": f"o{i}", "tags": [1, 2]}, "n": int(rng.integers(9))}}
        for i in range(40)
    ]


def _nest_inject(
    data: list[dict[str, Any]], k: int, seed: int
) -> tuple[list[dict[str, Any]], list[Any]]:
    return fp.corrupt_path(data, PATH, "remove", k, seed)


def _nest_changed(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> list[Any]:
    return [(i, PATH) for i in range(len(before)) if before[i] != after[i]]


RUNNERS: dict[str, Runner] = {
    "P-TAB": Runner(
        "P-TAB",
        "row",
        lambda d: list(range(len(d))),
        _tab_inject,
        _tab_changed,
        lambda d: 0,
        _tab_make,
    ),
    "P-TS": Runner(
        "P-TS", "time_window", _ts_units, _ts_inject, _ts_changed, lambda d: 0, _ts_make
    ),
    "P-SEQ": Runner(
        "P-SEQ",
        "event_sequence",
        lambda d: sorted(d),
        _seq_inject,
        _seq_changed,
        lambda d: 0,
        _seq_make,
    ),
    "P-REL": Runner(
        "P-REL", "relationship", _rel_units, _rel_inject, _rel_changed, _rel_baseline, _rel_make
    ),
    "P-NEST": Runner(
        "P-NEST",
        "nested_path",
        lambda d: [(i, PATH) for i in range(len(d))],
        _nest_inject,
        _nest_changed,
        lambda d: 0,
        _nest_make,
    ),
}


def fixture(protocol: str, seed: int) -> Fixture:
    """The seeded synthetic data of a protocol."""
    if protocol not in RUNNERS:
        raise of.InapplicableFailure(f"no runner for protocol {protocol!r}")
    return Fixture(protocol, RUNNERS[protocol].make(np.random.default_rng(seed)), seed)


def coverage(protocols: Mapping[str, Mapping[str, Any]]) -> dict[str, str]:
    """For each registry protocol: ``runner`` when a runner implements its detection unit."""
    out = {}
    for name, spec in sorted(protocols.items()):
        runner = RUNNERS.get(name)
        if runner is None:
            out[name] = "no runner"
        elif runner.unit != spec["detection_unit"]:
            out[name] = f"unit mismatch: runner {runner.unit}, registry {spec['detection_unit']}"
        else:
            out[name] = "runner"
    return out


def execute(item: Fixture, faults: int, seed: int, *, scientific: bool = False) -> UnitRun:
    """Inject ``faults`` faults into a synthetic fixture and check the protocol's contract."""
    if scientific:
        raise Refused(FREEZE_REASON)
    if not isinstance(item, Fixture) or item.protocol not in RUNNERS:
        raise of.InapplicableFailure(f"no runner for fixture {item!r}")
    runner = RUNNERS[item.protocol]
    if faults < 1:
        raise of.DataQualityFailure("at least one fault must be injected")
    with obs_tracing.span("unit_runner.execute", protocol=runner.protocol, faults=faults):
        obs_events.emit(LOG, "stage.started", stage=f"unit_runner.{runner.protocol}")
        before = copy.deepcopy(item.data)
        with obs_tracing.span("unit_runner.inject", faults=faults):
            try:
                after, truth = runner.inject(item.data, faults, seed)
                again, repeat = runner.inject(item.data, faults, seed)
            except fp.ProtocolError as error:
                raise of.InapplicableFailure(str(error)) from None
        units = runner.units(item.data)
        with obs_tracing.span("unit_runner.check", units=len(units)):
            checks = {
                "truth_inside_units": set(truth) <= set(units),
                "exactly_the_truth_changed": sorted(runner.changed(item.data, after), key=str)
                == sorted(truth, key=str),
                "input_unmodified": _same(before, item.data),
                "deterministic": repeat == truth and _same(after, again),
                "fault_count": len(truth) == faults,
            }
        result = UnitRun(
            protocol=runner.protocol,
            unit=runner.unit,
            unit_status=cm.UNITS[runner.unit][1],
            synthetic=True,
            seed=seed,
            faults=faults,
            units=len(units),
            truth=_ids(truth),
            baseline=runner.baseline(item.data),
            checks=checks,
        )
        if not all(checks.values()):
            failed = [name for name, ok in checks.items() if not ok]
            raise of.ProcessingFailure(f"{runner.protocol} contract broken: {', '.join(failed)}")
        obs_events.emit(
            LOG, "stage.completed", stage=f"unit_runner.{runner.protocol}", rows=len(units)
        )
    return result


def _same(left: Any, right: Any) -> bool:
    if isinstance(left, pd.DataFrame):
        return left.equals(right)
    if isinstance(left, dict) and left and isinstance(next(iter(left.values())), pd.DataFrame):
        return left.keys() == right.keys() and all(left[k].equals(right[k]) for k in left)
    return bool(left == right)


def report(seed: int, faults: int) -> dict[str, Any]:
    """Every runner executed once on its synthetic fixture."""
    return {
        "synthetic": True,
        "runs": [asdict(execute(fixture(p, seed), faults, seed)) for p in sorted(RUNNERS)],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--faults", type=int, default=3)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(json.dumps(report(args.seed, args.faults), indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
