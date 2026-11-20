# ruff: noqa: E501
"""A small synthetic evidence tree with every outcome the coverage matrix distinguishes."""

import json
from pathlib import Path


def _w(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def _run(problem, rows, features, prevalence, detectors, skipped=()):
    metrics = {"pr_auc": 0.5, "f1": 0.1}
    return {
        "problem": problem,
        "name": problem,
        "rows": rows,
        "features": features,
        "prevalence": prevalence,
        "seeds": [42, 1],
        "skipped": list(skipped),
        "errors": {},
        "runs": {d: [{"metrics": metrics}, {"metrics": {"pr_auc": 0.3}}] for d in detectors},
    }


def _mixed(ident, tier):
    return {
        "id": ident,
        "tier": tier,
        "types": ["missing_value", "duplicate"],
        "recall_pooled": {"knn": {"missing_value": 0.5}, "zscore": {"missing_value": 0.1}},
    }


def build(root: Path) -> Path:
    ids = ["adbench:satellite", "uci:146", "uci:9", "uci:3", "uci:467", "adbench:fraud", "uci:357"]
    ids += ["uci:864", "adbench:glass", "uci:999"]
    _w(root / "dataset_registry/pool_manifest.json", [
        {"id": i, "licence": "CC BY 4.0", "sha256": "ab" + str(n), "url": f"http://x/{n}"}
        for n, i in enumerate(ids)
    ])  # fmt: skip
    label = {"kind": "native_rare"}
    _w(root / "dataset_registry/uci_pool.json", {"rows": [
        {"uci_id": 146, "label": label},
        {"uci_id": 9, "label_refused": "not a classification task"},
        {"uci_id": 3, "label_refused": "fewer than 2 classes"},
        {"uci_id": 467, "label_refused": "fewer than 2 classes"},
        {"uci_id": 357, "label": label},
        {"uci_id": 864, "label": label},
    ]})  # fmt: skip
    _w(root / "dataset_registry/uci_curated.json", {"kept": [
        {"uci_id": 146, "area": "Physics", "feature_types": ["Integer"], "num_instances": 6435,
         "num_features": 36, "has_missing_values": "no"},
        {"uci_id": 9, "area": "Engineering", "feature_types": ["Real", "Categorical"],
         "num_instances": 398, "num_features": 7, "has_missing_values": "yes"},
        {"uci_id": 3, "area": "Other", "feature_types": ["Categorical"],
         "num_instances": 898, "num_features": 38, "has_missing_values": "yes"},
        {"uci_id": 467, "area": "Social Science", "feature_types": ["Categorical", "Integer"],
         "num_instances": 131, "num_features": 22, "has_missing_values": "no"},
        {"uci_id": 357, "area": "Climate", "feature_types": ["Real"],
         "num_instances": 20562, "num_features": 7, "has_missing_values": "no"},
        {"uci_id": 864, "area": "Climate", "feature_types": [],
         "num_instances": 10129, "num_features": 18, "has_missing_values": "no"},
        {"uci_id": 999, "feature_types": ["Integer", "Real"], "num_instances": 777,
         "num_features": 4, "has_missing_values": "yes"},
    ]})  # fmt: skip
    _w(root / "dataset_registry/inventory.json", [
        {"name": "satellite", "decision": "INCLUDE", "rows": 6435, "features": 36, "nan_cells": 0},
        {"name": "fraud", "decision": "INCLUDE", "rows": 284807, "features": 29, "nan_cells": 5},
        {"name": "mnist", "decision": "EXCLUDE", "rows": 7603, "features": 100, "nan_cells": 0},
        {"name": "glass", "decision": "INCLUDE", "rows": 214, "features": 9, "nan_cells": 0},
    ])  # fmt: skip
    eligibility = [
        {"id": "adbench:satellite", "name": "satellite", "eligible": True, "rows": 6000},
        {"id": "uci:146", "name": "Statlog Landsat", "eligible": True, "rows": 6000},
        {"id": "uci:9", "name": "Auto MPG", "eligible": False, "reason": "only 3 continuous columns"},
        {"id": "uci:3", "name": "Annealing", "eligible": False, "reason": "only 0 continuous columns"},
        {"id": "uci:467", "name": "Student Academics", "eligible": False, "reason": "only 0 continuous columns"},
        {"id": "adbench:fraud", "name": "fraud", "eligible": True, "rows": 20000},
        {"id": "uci:357", "name": "Occupancy", "eligible": False, "reason": "only 1 continuous columns"},
        {"id": "uci:864", "name": "Room", "eligible": False, "reason": "only 2 continuous columns"},
        {"id": "adbench:glass", "name": "glass", "eligible": False, "reason": "only 1 continuous columns"},
    ]  # fmt: skip
    _w(root / "pool_extension/typed/eligibility.json", eligibility)
    _w(root / "pool_extension/time_scan.json", [
        {"uci_id": 9, "candidates": [{"column": "model_year", "kind": "numeric"}]},
        {"uci_id": 357, "candidates": [{"column": "date", "kind": "datetime"}]},
        {"uci_id": 864, "candidates": [{"column": "Time", "kind": "datetime"}]},
        {"uci_id": 3, "candidates": []},
    ])  # fmt: skip
    ext = root / "pool_extension"
    for kind in ("classical", "deep"):
        runs = ext / f"pool_full_{kind}/runs"
        det = ["knn", "zscore"] if kind == "classical" else ["vae"]
        _w(
            runs / "adbench_satellite.json",
            _run("adbench:satellite", 6435, 36, 0.3, det, ["ocsvm"]),
        )
        _w(runs / "uci_146.json", _run("uci:146", 6435, 36, 0.3, det))
        _w(runs / "adbench_fraud.json", _run("adbench:fraud", 284807, 29, 0.002, det))
        _w(runs / "uci_357.json", _run("uci:357", 20562, 6, 0.5, det))
        bare = _run("uci:864", 10129, 17, 0.05, det)
        del bare["skipped"], bare["errors"]
        _w(runs / "uci_864.json", bare)
        broken = _run("uci:999", 777, 4, 0.5, det)
        broken["errors"] = {"knn": "boom"}
        broken["runs"]["knn" if kind == "classical" else "vae"][0]["metrics"] = {}
        _w(runs / "uci_999.json", broken)
        _w(ext / f"typed/severity_{kind}/adbench_satellite.json", {})
        _w(ext / f"typed/severity_{kind}/uci_146.json", {})
    _w(ext / "typed/reference_classical/adbench_satellite.json", {})
    _w(ext / "typed/reference_deep/adbench_satellite.json", {})
    fail = {"id": "uci:3", "method": "zscore", "status": "FAIL", "reason": "all-missing"}
    ok = {"status": "OK"}
    _w(ext / "etl/pool_etl.json", [
        {**fail}, {**fail, "method": "isolation_forest"},
        {"id": "uci:9", "method": "zscore", **ok}, {"id": "uci:9", "method": "isolation_forest", **ok},
        {"id": "uci:467", "method": "zscore", **ok},
        {"id": "uci:146", "method": "zscore", **ok}, {"id": "uci:146", "method": "isolation_forest", "status": "FAIL", "reason": "boom"},
        {"id": "uci:357", "method": "zscore", "status": "FAIL", "reason": "text"},
    ])  # fmt: skip
    _w(root / "pool_extension_v2/etl_repair/pool_etl.json", [
        {"id": "uci:3", "method": "zscore", **ok}, {"id": "uci:3", "method": "isolation_forest", **ok},
    ])  # fmt: skip
    chrono = ext / "chrono"
    _w(chrono / "credit_card.json", {"chronological": {"knn": {}}, "skipped": ["lof"]})
    _w(chrono / "occupancy_detection.json", {"chronological": {"knn": {}}, "skipped": []})
    _w(chrono / "room_occupancy_estimation.json", {"chronological": {}, "skipped": []})
    v2 = root / "pool_extension_v2"
    _w(v2 / "typed_mixed/eligibility.json", [
        {"id": "uci:9", "eligible": True},
        {"id": "uci:3", "eligible": False, "reason": "only 131 rows after cleaning"},
        {"id": "uci:467", "eligible": False, "reason": "only 131 rows after cleaning"},
        {"id": "uci:357", "eligible": True},
    ])  # fmt: skip
    for kind in ("classical", "deep"):
        _w(v2 / f"typed_mixed/{kind}/uci_9.json", _mixed("uci:9", "B"))
    _w(v2 / "chrono_injected/deep/uci_357.json", {
        "id": "uci:357", "carrier": {"span": ["2015", "2016"]},
        "arms": {"random": {"fpr": {"vae": 0.3}}},
    })  # fmt: skip
    _w(v2 / "chrono_injected/classical/uci_357.json", {
        "id": "uci:357", "carrier": {"span": ["2015", "2016"]},
        "arms": {"random": {"fpr": {"knn": 0.1, "zscore": 0.2}}},
    })  # fmt: skip
    return root
