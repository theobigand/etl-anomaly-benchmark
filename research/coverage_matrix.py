"""Dataset coverage matrix: which of the retained datasets contributed which measurements.

The matrix is generated from the archived evidence, never from the registry alone. A dataset counts
as evaluated in a protocol only when a result file holds a measurement for it; downloading, parsing
or listing it in a manifest does not count. Missing measurements stay missing (never zero), and
every absent cell carries a status and a reason.

    python research/coverage_matrix.py [--evidence DIR] [--out DIR]
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(HERE), str(ROOT / "src")]

import dataset_registry as dr  # noqa: E402

EVIDENCE = ROOT / "verification" / "evidence"
OUT = EVIDENCE / "coverage"

OK = "executed"
NOT_RUN = "eligible_not_executed"
FAILED = "executed_with_failure"
UNSUITABLE = "scientifically_unsuitable"
LIMITED = "implementation_limitation"
NOT_EVALUATED = "not_evaluated"
STATUSES = (OK, NOT_RUN, FAILED, UNSUITABLE, LIMITED, NOT_EVALUATED)

PROTOCOLS = (
    "labelled_classical",
    "labelled_deep",
    "typed_injection_classical",
    "typed_injection_deep",
    "native_label_comparison_classical",
    "native_label_comparison_deep",
    "etl_pipeline",
    "chronological",
)
_ADBENCH_DOMAIN = {row["name"]: row["domain"] for row in dr.ADBENCH_TABULAR}
# ADBench file stem -> UCI source id, so that twins share one independent source.
_TWIN = {name: uci_id for name, (uci_id, _title) in dr.UCI_SOURCES.items()}
_CHRONO_FILES = {
    "credit_card": "adbench:fraud",
    "bank_marketing": "uci:222",
    "occupancy_detection": "uci:357",
    "online_shoppers_purchasing_intention_dataset": "uci:468",
    "room_occupancy_estimation": "uci:864",
}


def _load(path: Path) -> Any:
    return json.loads(path.read_text())


def _cell(status: str, reason: str | None = None, **extra: Any) -> dict[str, Any]:
    assert status in STATUSES
    cell: dict[str, Any] = {"status": status}
    if reason:
        cell["reason"] = reason
    cell.update(extra)
    return cell


def source_key(dataset_id: str) -> str:
    """Independent underlying source: ADBench tables derived from a UCI set share its key."""
    kind, _, name = dataset_id.partition(":")
    if kind == "adbench" and name in _TWIN:
        return f"uci:{_TWIN[name]}"
    return dataset_id


def _mean_metric(runs: dict[str, list[dict[str, Any]]], key: str) -> dict[str, float]:
    """Mean over seeds of one metric per detector; absent detectors are absent, not zero."""
    out: dict[str, float] = {}
    for detector, seeds in runs.items():
        values = [r["metrics"][key] for r in seeds if r.get("metrics", {}).get(key) is not None]
        if values:
            out[detector] = round(sum(values) / len(values), 6)
    return out


def _labelled(evidence: Path, kind: str) -> dict[str, dict[str, Any]]:
    folder = evidence / "pool_extension" / f"pool_full_{kind}" / "runs"
    out: dict[str, dict[str, Any]] = {}
    for path in sorted(folder.glob("*.json")):
        record = _load(path)
        runs = record["runs"]
        out[record["problem"]] = _cell(
            OK,
            run=str(path.relative_to(evidence)),
            detectors=sorted(runs),
            skipped_detectors=sorted(record.get("skipped", [])),
            errors=record.get("errors") or {},
            pr_auc=_mean_metric(runs, "pr_auc"),
            seeds=record.get("seeds"),
            rows=record.get("rows"),
            features=record.get("features"),
            prevalence=record.get("prevalence"),
        )
    return out


def _typed(evidence: Path, folder: str) -> dict[str, dict[str, Any]]:
    root = evidence / "pool_extension" / "typed" / folder
    out: dict[str, dict[str, Any]] = {}
    for path in sorted(root.glob("*.json")):
        out[path.stem.replace("_", ":", 1)] = _cell(OK, run=str(path.relative_to(evidence)))
    return out


def _etl(evidence: Path) -> dict[str, dict[str, Any]]:
    rows = _load(evidence / "pool_extension" / "etl" / "pool_etl.json")
    by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_id[row["id"]].append(row)
    out: dict[str, dict[str, Any]] = {}
    for dataset_id, entries in by_id.items():
        ok = sorted(e["method"] for e in entries if e["status"] == "OK")
        bad = {e["method"]: e.get("reason", "") for e in entries if e["status"] != "OK"}
        meta = {"run": "pool_extension/etl/pool_etl.json", "methods_ok": ok, "methods_failed": bad}
        out[dataset_id] = _cell(
            OK if ok else FAILED, "; ".join(sorted(set(bad.values()))) or None, **meta
        )
    return out


def _chrono(evidence: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for path in sorted((evidence / "pool_extension" / "chrono").glob("*.json")):
        dataset_id = _CHRONO_FILES[path.stem]
        record = _load(path)
        skipped = sorted(record.get("skipped", []))
        detectors = sorted(record.get("chronological", {}))
        if not detectors:
            out[dataset_id] = _cell(UNSUITABLE, "no test anomalies in the chronological split")
        else:
            out[dataset_id] = _cell(
                OK,
                run=str(path.relative_to(evidence)),
                detectors=detectors,
                skipped_detectors=skipped,
            )
    return out


def build(evidence: Path = EVIDENCE) -> dict[str, Any]:
    pool = _load(evidence / "dataset_registry" / "pool_manifest.json")
    uci = {
        f"uci:{r['uci_id']}": r
        for r in _load(evidence / "dataset_registry" / "uci_pool.json")["rows"]
    }
    curated = {
        f"uci:{r['uci_id']}": r
        for r in _load(evidence / "dataset_registry" / "uci_curated.json")["kept"]
    }
    eligibility = {
        r["id"]: r for r in _load(evidence / "pool_extension" / "typed" / "eligibility.json")
    }
    time_scan = {
        f"uci:{r['uci_id']}": r for r in _load(evidence / "pool_extension" / "time_scan.json")
    }
    results = {
        "labelled_classical": _labelled(evidence, "classical"),
        "labelled_deep": _labelled(evidence, "deep"),
        # The severity sweep folders hold one file per eligible dataset (six types, severity grid).
        "typed_injection_classical": _typed(evidence, "severity_classical"),
        "typed_injection_deep": _typed(evidence, "severity_deep"),
        # Reference folders compare the injected study with the native labels (ADBench tables only).
        "native_label_comparison_classical": _typed(evidence, "reference_classical"),
        "native_label_comparison_deep": _typed(evidence, "reference_deep"),
        "etl_pipeline": _etl(evidence),
        "chronological": _chrono(evidence),
    }
    datasets = []
    for entry in pool:
        dataset_id = entry["id"]
        kind, _, name = dataset_id.partition(":")
        labelled = results["labelled_classical"].get(dataset_id)
        info = uci.get(dataset_id, {})
        label = info.get("label") or {}
        row: dict[str, Any] = {
            "id": dataset_id,
            "source_family": kind,
            "name": eligibility.get(dataset_id, {}).get("name", name),
            "independent_source": source_key(dataset_id),
            "licence": entry.get("licence"),
            "sha256": entry.get("sha256"),
            "url": entry.get("url"),
            "domain": _ADBENCH_DOMAIN.get(name)
            if kind == "adbench"
            else curated.get(dataset_id, {}).get("area"),
            "feature_types": curated.get(dataset_id, {}).get("feature_types"),
            "has_labels": labelled is not None,
            "label_kind": "minority_class_proxy" if labelled else None,
            "label_origin": label.get("kind")
            if label
            else ("adbench_binary" if labelled else None),
            "label_refused": info.get("label_refused"),
            "rows": (labelled or {}).get("rows") or eligibility.get(dataset_id, {}).get("rows"),
            "features": (labelled or {}).get("features"),
            "prevalence": (labelled or {}).get("prevalence"),
            "time_candidates": [
                c["column"] for c in time_scan.get(dataset_id, {}).get("candidates", [])
            ],
        }
        cells: dict[str, dict[str, Any]] = {}
        for protocol in PROTOCOLS:
            cells[protocol] = results[protocol].get(dataset_id) or _absent(
                protocol, row, eligibility.get(dataset_id), info
            )
        row["protocols"] = cells
        row["valid_measurements"] = sorted(p for p, c in cells.items() if c["status"] == OK)
        datasets.append(row)
    return {"datasets": datasets, "summary": summarise(datasets)}


def _absent(
    protocol: str, row: dict[str, Any], elig: dict[str, Any] | None, info: dict[str, Any]
) -> dict[str, Any]:
    if protocol.startswith("labelled"):
        reason = info.get("label_refused") or (
            "no label file in the pool run"
            if row["has_labels"] is False
            else "labelled run missing"
        )
        return _cell(UNSUITABLE if info.get("label_refused") else NOT_EVALUATED, reason)
    if protocol.startswith("native_label"):
        if not row["has_labels"]:
            return _cell(UNSUITABLE, "no native label to compare with")
        return _cell(NOT_EVALUATED, "comparison was only run on the sixteen ADBench tables")
    if protocol.startswith("typed"):
        if elig and not elig["eligible"]:
            return _cell(UNSUITABLE, f"typed injection ineligible: {elig['reason']}")
        return _cell(
            NOT_RUN if elig else NOT_EVALUATED,
            "eligible but no result file" if elig else "no eligibility record",
        )
    if protocol == "chronological":
        if row["time_candidates"] and not row["has_labels"]:
            return _cell(
                NOT_EVALUATED,
                "time column candidate but no labels and no protocol for unlabelled chronology",
            )
        if row["time_candidates"]:
            return _cell(NOT_EVALUATED, "time candidate column is not a verified real chronology")
        return _cell(UNSUITABLE, "no time variable")
    return _cell(NOT_EVALUATED, "no result file")


def summarise(datasets: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(datasets)
    by_protocol = {
        p: dict(Counter(d["protocols"][p]["status"] for d in datasets)) for p in PROTOCOLS
    }
    used = [d for d in datasets if d["valid_measurements"]]
    etl_only = [d for d in used if d["valid_measurements"] == ["etl_pipeline"]]
    sources = {d["independent_source"] for d in datasets}
    used_sources = {d["independent_source"] for d in used}
    scientific = [d for d in datasets if set(d["valid_measurements"]) - {"etl_pipeline"}]
    return {
        "datasets": n,
        "uci": sum(d["source_family"] == "uci" for d in datasets),
        "adbench": sum(d["source_family"] == "adbench" for d in datasets),
        "with_labels": sum(d["has_labels"] for d in datasets),
        "with_any_valid_measurement": len(used),
        "with_detector_quality_measurement": len(scientific),
        "etl_pipeline_only": len(etl_only),
        "etl_pipeline_only_ids": sorted(d["id"] for d in etl_only),
        "without_detector_quality_measurement": sorted(
            d["id"] for d in datasets if d not in scientific
        ),
        "typed_injection_supported": sum(
            d["protocols"]["typed_injection_classical"]["status"] == OK for d in datasets
        ),
        "temporal_evaluated": sum(
            d["protocols"]["chronological"]["status"] == OK for d in datasets
        ),
        "independent_sources": len(sources),
        "independent_sources_with_detector_quality_measurement": len(
            {d["independent_source"] for d in scientific}
        ),
        "independent_sources_used": len(used_sources),
        "by_protocol": by_protocol,
        "twin_groups": {
            k: sorted(d["id"] for d in datasets if d["independent_source"] == k)
            for k, c in Counter(d["independent_source"] for d in datasets).items()
            if c > 1
        },
    }


def report(matrix: dict[str, Any]) -> str:
    s = matrix["summary"]
    lines = [
        "# Dataset coverage matrix",
        "",
        "Generated by `research/coverage_matrix.py` from the archived evidence. A dataset counts",
        "as evaluated only when a result file holds a measurement for it.",
        "",
        "## Headline counts",
        "",
        f"- Datasets in the catalog: {s['datasets']} ({s['uci']} UCI, {s['adbench']} ADBench).",
        f"- Independent underlying sources: {s['independent_sources']} "
        f"({len(s['twin_groups'])} sources back more than one catalog entry).",
        "- Datasets with a valid measurement in at least one protocol: "
        f"{s['with_any_valid_measurement']}.",
        "- Datasets with a detector-quality measurement (any protocol except the ETL timing run): "
        f"{s['with_detector_quality_measurement']}, from "
        f"{s['independent_sources_with_detector_quality_measurement']} independent sources.",
        f"- Datasets measured only by the ETL pipeline run: {s['etl_pipeline_only']}.",
        f"- Datasets with labels (minority-class proxies, not ETL faults): {s['with_labels']}.",
        f"- Datasets that support typed injection: {s['typed_injection_supported']}.",
        f"- Datasets evaluated chronologically: {s['temporal_evaluated']}.",
        "",
        "## Status by protocol",
        "",
        "| Protocol | " + " | ".join(STATUSES) + " |",
        "|---|" + "---:|" * len(STATUSES),
    ]
    for protocol, counts in s["by_protocol"].items():
        lines.append(
            f"| {protocol} | " + " | ".join(str(counts.get(st, 0)) for st in STATUSES) + " |"
        )
    lines += ["", "## Twin sources (one independent source, several catalog entries)", ""]
    for key, ids in sorted(s["twin_groups"].items()):
        lines.append(f"- `{key}`: {', '.join(ids)}")
    lines += ["", "## Datasets without a detector-quality measurement", ""]
    by_id = {d["id"]: d for d in matrix["datasets"]}
    for dataset_id in s["without_detector_quality_measurement"]:
        d = by_id[dataset_id]
        reasons = sorted(
            {c["reason"] for c in d["protocols"].values() if c["status"] != OK and c.get("reason")}
        )
        lines.append(f"- `{dataset_id}` {d['name']}: {'; '.join(reasons[:3])}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--evidence", type=Path, default=EVIDENCE)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    matrix = build(args.evidence)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "coverage_matrix.json").write_text(
        json.dumps(matrix, indent=1, sort_keys=True) + "\n"
    )
    (args.out / "coverage_matrix.md").write_text(report(matrix))
    print(
        json.dumps({k: v for k, v in matrix["summary"].items() if not isinstance(v, (dict, list))})
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
