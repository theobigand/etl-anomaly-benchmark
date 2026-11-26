"""Mechanics of the controlled-fault protocols (P-TAB, P-TS, P-SEQ, P-REL, P-NEST).

Each injector checks its precondition, changes only what its definition names, is deterministic
for a seed and returns the ground truth in the detection unit of its protocol. Nothing here scores a
detector. Protocol text: verification/anomaly_protocols.md.
"""

from __future__ import annotations

import copy
import hashlib
from typing import Any

import numpy as np
import pandas as pd


class ProtocolError(Exception):
    """A precondition of a protocol does not hold for the data."""


def _rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)


def choose_within(candidates: list[Any], k: int, seed: int) -> list[Any]:
    """k distinct candidates, drawn without replacement and returned in candidate order."""
    if k > len(candidates) or k < 0:
        raise ProtocolError(
            f"precondition: {k} faults requested among {len(candidates)} candidates"
        )
    picks = sorted(_rng(seed).choice(len(candidates), size=k, replace=False).tolist())
    return [candidates[i] for i in picks]


def inject_duplicates(df: pd.DataFrame, k: int, seed: int) -> tuple[pd.DataFrame, list[int]]:
    """Append k copies of existing rows; the truth is the positions of the copies."""
    rows = choose_within(list(range(len(df))), k, seed)
    out = pd.concat([df, df.iloc[rows]], ignore_index=True)
    return out, list(range(len(df), len(df) + k))


def inject_scale(
    df: pd.DataFrame,
    column: str,
    k: int,
    factor: float,
    seed: int,
    candidates: list[int] | None = None,
) -> tuple[pd.DataFrame, list[int]]:
    """Multiply k values of a numeric column by ``factor``; the truth is the row positions.

    ``candidates`` limits the rows that may be chosen (for example, the test partition).
    """
    if not pd.api.types.is_numeric_dtype(df[column]):
        raise ProtocolError(f"precondition: column {column!r} is not numeric")
    rows = choose_within(candidates if candidates is not None else list(range(len(df))), k, seed)
    out = df.copy()
    out.loc[out.index[rows], column] = out[column].iloc[rows] * factor
    return out, rows


def inject_level_shift(
    wide: pd.DataFrame, series: str, start: int, length: int, delta: float
) -> tuple[pd.DataFrame, list[tuple[str, int, int]]]:
    """Add ``delta`` to one series over [start, start + length); the truth is that window."""
    if start < 0 or length < 1 or start + length > len(wide) or series not in wide:
        raise ProtocolError("precondition: the window lies outside the series")
    out = wide.copy()
    out.iloc[start : start + length, out.columns.get_loc(series)] += delta
    return out, [(series, start, start + length)]


def swap_adjacent(
    seqs: dict[str, list[str]], name: str, position: int
) -> tuple[dict[str, list[str]], list[tuple[str, int]]]:
    """Swap the events at ``position`` and ``position + 1`` of one sequence."""
    if not 0 <= position < len(seqs[name]) - 1:
        raise ProtocolError("precondition: no adjacent pair at this position")
    out = copy.deepcopy(seqs)
    s = out[name]
    s[position], s[position + 1] = s[position + 1], s[position]
    return out, [(name, position)]


def drop_event(
    seqs: dict[str, list[str]], name: str, position: int
) -> tuple[dict[str, list[str]], list[tuple[str, int]]]:
    """Remove one event; the truth is its position in the original sequence."""
    if not 0 <= position < len(seqs[name]):
        raise ProtocolError("precondition: no event at this position")
    out = copy.deepcopy(seqs)
    del out[name][position]
    return out, [(name, position)]


def break_foreign_key(
    child: pd.DataFrame, column: str, parent_keys: set[Any], k: int, seed: int
) -> tuple[pd.DataFrame, list[int], list[int]]:
    """Point k valid references at a key absent from the parent.

    Natural orphans (and missing keys) are never chosen and never labelled: they are returned as the
    baseline so that the study can tell them from injected faults.
    """
    values = child[column]
    resolvable = [i for i, v in enumerate(values) if pd.notna(v) and v in parent_keys]
    baseline = [i for i, v in enumerate(values) if pd.notna(v) and v not in parent_keys]
    rows = choose_within(resolvable, k, seed)
    numeric = all(isinstance(x, int | np.integer) for x in parent_keys)
    absent = max((int(x) for x in parent_keys), default=0) if numeric else 0
    out = child.copy()
    for n, i in enumerate(rows):
        new = absent + 1_000_000 + n if numeric else f"__absent_{n}__"
        out.iloc[i, out.columns.get_loc(column)] = new
    return out, rows, baseline


def _get(node: dict[str, Any], parts: list[str]) -> bool:
    for p in parts:
        if not isinstance(node, dict) or p not in node:
            return False
        node = node[p]
    return True


def corrupt_path(
    records: list[dict[str, Any]], path: str, mode: str, k: int, seed: int
) -> tuple[list[dict[str, Any]], list[tuple[int, str]]]:
    """Remove a nested field or change its type in k records holding it; truth: (record, path)."""
    parts = path.split(".")
    holders = [i for i, r in enumerate(records) if _get(r, parts)]
    if not holders:
        raise ProtocolError(f"precondition: no record has the path {path!r}")
    rows = choose_within(holders, k, seed)
    out = copy.deepcopy(records)
    for i in rows:
        parent = out[i]
        for p in parts[:-1]:
            parent = parent[p]
        if mode == "remove":
            del parent[parts[-1]]
        elif mode == "type":
            value = parent[parts[-1]]
            parent[parts[-1]] = 0 if isinstance(value, str) else str(value)
        else:
            raise ProtocolError(f"unknown mode {mode!r}")
    return out, [(i, path) for i in rows]


def match_exact(predicted: list[Any], truth: list[Any]) -> dict[str, int]:
    p, t = set(predicted), set(truth)
    return {"tp": len(p & t), "fp": len(p - t), "fn": len(t - p)}


def match_windows(
    predicted: list[tuple[str, int, int]], truth: list[tuple[str, int, int]]
) -> dict[str, int]:
    """A window matches when it is in the same series and overlaps by half of the shorter one."""

    def hit(a: tuple[str, int, int], b: tuple[str, int, int]) -> bool:
        if a[0] != b[0]:
            return False
        overlap = min(a[2], b[2]) - max(a[1], b[1])
        return overlap >= 0.5 * min(a[2] - a[1], b[2] - b[1]) and overlap > 0

    tp = sum(any(hit(p, t) for t in truth) for p in predicted)
    covered = sum(any(hit(p, t) for p in predicted) for t in truth)
    return {"tp": tp, "fp": len(predicted) - tp, "fn": len(truth) - covered}


def hash_partition(keys: list[str], fractions: tuple[float, float, float]) -> dict[str, list[str]]:
    """Reference, validation and test partitions by a stable hash of each key."""
    names = ("reference", "validation", "test")
    cut = (fractions[0], fractions[0] + fractions[1])
    out: dict[str, list[str]] = {n: [] for n in names}
    for key in keys:
        u = int(hashlib.sha256(str(key).encode()).hexdigest()[:12], 16) / 16**12
        out[names[0 if u < cut[0] else 1 if u < cut[1] else 2]].append(key)
    return out


def _without(mapping: dict[str, Any], key: str) -> dict[str, Any]:
    return {k: v for k, v in mapping.items() if k != key}


def _split_rows(n: int) -> tuple[list[int], list[int]]:
    cut = int(n * 0.85)
    return list(range(cut)), list(range(cut, n))


def conformance(data: dict[str, Any], seed: int) -> dict[str, dict[str, Any]]:
    """Invariants of every protocol on given data; no detector is involved and nothing is scored."""
    report: dict[str, dict[str, Any]] = {}

    child, parent = data["authorships"], data["authors"]
    out, truth, base = break_foreign_key(child, "author_id", set(parent["author_id"]), 20, seed)
    again = break_foreign_key(child, "author_id", set(parent["author_id"]), 20, seed)
    votes, posts = data["votes"], data["posts"]
    v_out, v_truth, v_base = break_foreign_key(votes, "post_id", set(posts["post_id"]), 20, seed)
    report["P-REL"] = {
        "deterministic": out.equals(again[0]) and truth == again[1],
        "unaffected_rows_unchanged": child.drop(index=truth).equals(out.drop(index=truth)),
        "truth_rows_now_orphans": all(
            out.loc[i, "author_id"] not in set(parent["author_id"]) for i in truth
        ),
        "baseline_orphans_reported_not_labelled": not (set(v_truth) & set(v_base)),
        "baseline_orphan_count": len(v_base),
        "baseline_unchanged": all(
            v_out.loc[i, "post_id"] == votes.loc[i, "post_id"] for i in v_base
        ),
    }

    if "contracts" in data:
        contracts, awards = data["contracts"], data["awards"]
        c_out, c_truth, c_base = break_foreign_key(
            contracts, "award_id", set(awards["award_id"]), 20, seed
        )
        report["P-REL"].update(
            ocds_baseline_orphans=len(c_base),
            ocds_baseline_not_labelled=not (set(c_truth) & set(c_base)),
            ocds_unaffected_rows_unchanged=contracts.drop(index=c_truth).equals(
                c_out.drop(index=c_truth)
            ),
        )

    events = data["events"]
    corrupted, e_truth = corrupt_path(events, "patient.sex", "remove", 30, seed)
    changed = [i for i, (a, b) in enumerate(zip(events, corrupted, strict=True)) if a != b]
    report["P-NEST"] = {
        "only_truth_records_changed": changed == sorted(i for i, _ in e_truth),
        "only_named_path_changed": all(
            corrupted[i] == {**events[i], "patient": _without(events[i]["patient"], "sex")}
            for i in changed
        ),
        "input_unmodified": all("sex" in e["patient"] for e in events),
    }

    ledger = data["ledger"]
    ref, test = _split_rows(len(ledger))
    scaled, s_truth = inject_scale(ledger, "amount", 10, 5.0, seed, candidates=test)
    dup, d_truth = inject_duplicates(ledger.iloc[test].reset_index(drop=True), 10, seed)
    changed_rows = scaled.index[(scaled["amount"] != ledger["amount"]).to_numpy()].tolist()
    report["P-TAB"] = {
        "faults_only_in_test_partition": set(s_truth) <= set(test),
        "reference_untouched": scaled.iloc[ref].equals(ledger.iloc[ref]),
        "scale_changes_only_truth": changed_rows == sorted(s_truth),
        "duplicates_appended_after_originals": min(d_truth) == len(test)
        and len(dup) == len(test) + 10,
    }

    seq = {"log": data["sequence"]}
    swapped, q_truth = swap_adjacent(seq, "log", 100)
    dropped, _ = drop_event(seq, "log", 100)
    report["P-SEQ"] = {
        "swap_keeps_length_and_multiset": sorted(swapped["log"]) == sorted(seq["log"]),
        "swap_changes_two_positions_only": sum(
            a != b for a, b in zip(swapped["log"], seq["log"], strict=True)
        )
        <= 2,
        "drop_shortens_by_one": len(dropped["log"]) == len(seq["log"]) - 1,
        "truth_is_the_position": q_truth == [("log", 100)],
    }

    wide = data["series"]
    first, second = wide.columns[:2]
    shifted, w_truth = inject_level_shift(wide, first, 200, 20, 3.0)
    report["P-TS"] = {
        "other_series_untouched": shifted[second].equals(wide[second]),
        "outside_window_untouched": shifted[first].iloc[:200].equals(wide[first].iloc[:200])
        and shifted[first].iloc[220:].equals(wide[first].iloc[220:]),
        "time_index_monotonic_and_unchanged": shifted.index.equals(wide.index)
        and bool(shifted.index.is_monotonic_increasing),
        "window_is_the_truth": w_truth == [(first, 200, 220)],
    }
    return report


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json
    from pathlib import Path

    here = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--views", type=Path, default=here / "data" / "experimental")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--out",
        type=Path,
        default=here / "verification/evidence/dataset_registry_v2/protocol_conformance.json",
    )
    args = parser.parse_args(argv)
    v = args.views
    records = [
        json.loads(line)
        for line in (v / "openfda_drug_event/events.jsonl").read_text().splitlines()
    ]
    records = [r for r in records if "patient" in r and "patientsex" in r["patient"]][:2000]
    for r in records:
        r["patient"]["sex"] = r["patient"].pop("patientsex")
    ledger = pd.read_csv(v / "ukspend/nhsbsa.csv", parse_dates=["date"]).sort_values("date")
    events = pd.read_csv(v / "loghub/Apache.csv", dtype=str)["EventId"].tolist()
    data = {
        "authorships": pd.read_csv(v / "openalex/authorships.csv"),
        "authors": pd.read_csv(v / "openalex/authors.csv"),
        "votes": pd.read_csv(v / "stackexchange/coffee/Votes.csv", dtype=str),
        "posts": pd.read_csv(v / "stackexchange/coffee/Posts.csv", dtype=str),
        "events": records,
        "ledger": ledger.reset_index(drop=True),
        "sequence": events,
        "series": pd.read_csv(
            v / "monash_pedestrian/wide.csv", index_col="timestamp", parse_dates=True
        )
        .iloc[:5000, :3]
        .ffill()
        .fillna(0.0),
    }
    if (v / "ocds_zambia/contracts.csv").exists():
        data["contracts"] = pd.read_csv(v / "ocds_zambia/contracts.csv", dtype=str)
        data["awards"] = pd.read_csv(v / "ocds_zambia/awards.csv", dtype=str)
    report = conformance(data, args.seed)
    args.out.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    print({k: all(x for x in c.values() if isinstance(x, bool)) for k, c in report.items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
