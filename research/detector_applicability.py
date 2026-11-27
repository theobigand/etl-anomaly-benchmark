"""Detector applicability of the five protocol-defined units and potential contrast eligibility.

Issues #136 to #139.

A detector is not applicable to a unit merely because it can accept an input. Every cell of the
matrix states two separate things:

- ``technical``: ``existing_adapter`` (the detector already takes the unit's representation),
  ``adapter_implemented`` (a featurizer in ``unit_scoring`` makes it run, validated on synthetic
  fixtures only), ``requires_implementation`` or ``not_applicable``;
- ``scientific``: ``pending_unit_approval`` (the S03 amendment of the unit is not recorded, D-13),
  ``pending_representation_approval`` (the featurizer is a proposal, not an approved method) or
  ``inappropriate`` (using the detector would answer no meaningful question).

``status`` combines them. Nothing here reads a dataset or runs a detector on benchmark data.
Eligibility
counts are structural upper bounds from registry metadata: potential eligibility, not verified
eligibility and not paired observations.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pilot_panel_design as ppd

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = ROOT / "verification/evidence/dataset_registry_v2"
UNITS = {
    "P-TAB": "row",
    "P-TS": "time_window",
    "P-SEQ": "event_sequence",
    "P-REL": "relationship",
    "P-NEST": "nested_path",
}
RULES = ("zscore", "iqr", "great_expectations")
CLASSICAL = ("isolation_forest", "lof", "ocsvm", "ecod", "copod", "hbos", "knn", "pca")
NEURAL = ("autoencoder", "vae", "deep_svdd", "dif", "ae1svm", "lunar")
#: unit-specific deterministic rule baselines that do not exist yet
CONSTRAINT_RULES = {
    "sequence_constraints": "P-SEQ",
    "fk_integrity": "P-REL",
    "schema_path_rules": "P-NEST",
}
FAMILY = {
    **{d: "rule" for d in (*RULES, *CONSTRAINT_RULES)},
    **{d: "classical" for d in CLASSICAL},
    **{d: "neural" for d in NEURAL},
}
KIND = {
    "zscore": "statistical_rule",
    "iqr": "statistical_rule",
    "great_expectations": "declarative_rule",
    **{d: "constraint_rule_deterministic" for d in CONSTRAINT_RULES},
    **{d: "learned" for d in (*CLASSICAL, *NEURAL)},
}
FEATURIZER = {
    "P-TAB": "numeric columns of the row",
    "P-TS": "unit_scoring.window_features (mean, std, min, max, slope, mean absolute difference)",
    "P-SEQ": "unit_scoring.SequenceFeaturizer (length, unseen bigrams, train bigram counts)",
    "P-REL": "unit_scoring.relationship_features (child numeric columns)",
    "P-NEST": "unit_scoring.PathFeaturizer (presence, type, depth, number, size of each leaf path)",
}
LIMITS = {
    (
        "zscore",
        "P-SEQ",
    ): "training traces with constant counts have zero deviation: the score degenerates",
    (
        "iqr",
        "P-SEQ",
    ): "training traces with constant counts have zero deviation: the score degenerates",
}
INAPPROPRIATE = {
    (
        "great_expectations",
        "P-SEQ",
    ): "an expectation suite on bigram counts is not a sequence constraint",
    (
        "great_expectations",
        "P-REL",
    ): "an expectation suite on child attributes does not check references; use fk_integrity",
    (
        "great_expectations",
        "P-NEST",
    ): "the wrapper checks tabular columns, not paths; use schema_path_rules",
}
#: operator -> how the unit's representation exposes it (``visible``, ``limited`` or ``invisible``)
MECHANISMS: dict[str, dict[str, tuple[str, str]]] = {
    "P-TAB": {
        "univariate_outlier": ("visible", "a numeric column leaves its training range"),
        "multivariate_outlier": ("visible", "joint position in the numeric space"),
        "invalid_category_code": (
            "invisible",
            "categorical columns are dropped by the numeric featurizer",
        ),
        "missing_values": ("invisible", "train-only median imputation hides the gap"),
        "duplicate_rows": ("invisible", "a duplicate row equals a normal row"),
        "cross_field_violation": (
            "limited",
            "visible only if the violation moves the joint position",
        ),
        "abnormal_entity_behaviour": ("invisible", "needs an entity key and per-entity features"),
    },
    "P-TS": {
        "point_outlier": ("limited", "a single point moves max and min of its window"),
        "contextual_anomaly": ("limited", "needs the seasonal context, not the window values"),
        "collective_anomaly": ("visible", "window statistics change"),
        "level_shift": ("visible", "window mean changes"),
        "gradual_drift": ("limited", "slope changes only inside the window"),
        "seasonal_deviation": ("invisible", "needs the position in the season"),
        "missing_interval": ("invisible", "the featurizer assumes complete windows"),
        "delayed_arrival": ("invisible", "needs arrival times, not values"),
    },
    "P-SEQ": {
        "order_violation": ("visible", "unseen bigrams"),
        "missing_event": ("visible", "length and unseen bigrams"),
        "unexpected_sequence": ("visible", "unseen bigrams"),
        "duplicate_event": ("visible", "length and bigram counts"),
        "abnormal_transition": ("visible", "unseen or rare bigrams"),
    },
    "P-REL": {
        "referential_violation": (
            "visible",
            "only with reference_present, which is the constraint itself",
        ),
        "invalid_relationship": ("limited", "depends on the relationship semantics"),
        "duplicate_entity": ("invisible", "needs entity keys across child rows"),
        "inconsistent_aggregate": (
            "invisible",
            "needs parent-child aggregates, not child attributes",
        ),
    },
    "P-NEST": {
        "missing_required_field": ("visible", "presence of the path"),
        "invalid_nested_type": ("visible", "type code of the path"),
        "unexpected_array_or_object": ("visible", "type code of the path"),
        "broken_hierarchy": ("limited", "depth and presence of the path"),
        "structural_inconsistency": ("limited", "depends on the inconsistency"),
    },
}


def cell(detector: str, protocol: str) -> dict[str, Any]:
    unit = UNITS[protocol]
    base = {"detector": detector, "protocol": protocol, "unit": unit, "family": FAMILY[detector]}
    base["kind"] = KIND[detector]
    if detector in CONSTRAINT_RULES:
        if CONSTRAINT_RULES[detector] != protocol:
            return {
                **base,
                "technical": "not_applicable",
                "scientific": "not_applicable",
                "status": "not_applicable",
                "note": "defined for another unit",
            }
        return {
            **base,
            "technical": "requires_implementation",
            "scientific": "pending_unit_approval",
            "status": "requires_implementation",
            "note": "deterministic baseline from the declared schema, keys or order",
        }
    if (detector, protocol) in INAPPROPRIATE:
        return {
            **base,
            "technical": "requires_implementation",
            "scientific": "inappropriate",
            "status": "scientifically_inappropriate",
            "note": INAPPROPRIATE[(detector, protocol)],
        }
    technical = "existing_adapter" if protocol == "P-TAB" else "adapter_implemented"
    scientific = (
        "pending_unit_approval" if protocol == "P-TAB" else "pending_representation_approval"
    )
    return {
        **base,
        "technical": technical,
        "scientific": scientific,
        "status": "supported_existing_adapter"
        if protocol == "P-TAB"
        else "adapter_implemented_pending_approval",
        "representation": FEATURIZER[protocol],
        "note": LIMITS.get((detector, protocol), ""),
    }


def matrix() -> list[dict[str, Any]]:
    """Every detector-unit cell that is defined (constraint rules exist for one unit only)."""
    cells = [cell(d, p) for p in UNITS for d in FAMILY]
    return [c for c in cells if c["status"] != "not_applicable"]


def _usable(status: str) -> bool:
    return status in ("supported_existing_adapter", "adapter_implemented_pending_approval")


def _possible(status: str) -> bool:
    return status not in ("scientifically_inappropriate", "not_applicable")


def _is_baseline(cell_: dict[str, Any]) -> bool:
    """A rule only counts as the rule-based side where it is a meaningful baseline: statistical
    rules on a featurized window or row, but for sequences, relationships and nested paths only
    the deterministic constraint rule of the unit (a z-score of bigram counts is not one)."""
    if cell_["family"] != "rule" or cell_["protocol"] in ("P-TAB", "P-TS"):
        return True
    return cell_["kind"] == "constraint_rule_deterministic"


CONTRASTS = {
    "F1a rule vs classical": ("rule", "classical"),
    "F1b classical vs neural": ("classical", "neural"),
    "F1c rule vs neural": ("rule", "neural"),
}


def protocols_for_contrast(cells: list[dict[str, Any]], contrast: str, test) -> list[str]:
    """Protocols in which both sides of the contrast have at least one detector passing ``test``."""
    left, right = CONTRASTS[contrast]
    out = []
    for protocol in UNITS:
        families = {
            c["family"]
            for c in cells
            if c["protocol"] == protocol and test(c["status"]) and _is_baseline(c)
        }
        if left in families and right in families:
            out.append(protocol)
    return out


def cluster_protocols(compat_groups: dict[str, Any], table: dict[str, Any]) -> dict[str, set[str]]:
    """Protocols each provenance cluster takes part in, from the compatibility model."""
    out: dict[str, set[str]] = {}
    for group, info in compat_groups.items():
        if group in table:
            out.setdefault(table[group]["cluster"], set()).update(
                p["protocol"] for p in info["participations"]
            )
    return out


def potential_eligibility(
    table: dict[str, Any],
    compat_groups: dict[str, Any],
    pilot_clusters: set[str],
    exposed_groups: list[str],
) -> dict[str, Any]:
    """Unexposed, floor-meeting, non-pilot clusters per protocol and per contrast.

    The count for a contrast is the union of the clusters of the protocols in which the contrast
    can be run, an upper bound before mechanism, size and paired-outcome conditions."""
    marked = ppd.with_exposure(table, exposed_groups)
    clusters = ppd.cluster_table(marked)
    pool = {c for c in ppd.eligible_clusters(clusters) if c not in pilot_clusters}
    by_protocol = cluster_protocols(compat_groups, marked)
    cells = matrix()
    per_protocol = {p: sorted(c for c in pool if p in by_protocol.get(c, set())) for p in UNITS}
    contrasts = {}
    for name in CONTRASTS:
        row = {}
        for label, test in (("now", _usable), ("after_implementation", _possible)):
            protocols = protocols_for_contrast(cells, name, test)
            members = {c for p in protocols for c in per_protocol[p]}
            row[label] = {"protocols": protocols, "clusters": len(members)}
        contrasts[name] = row
    return {
        "pool_clusters": len(pool),
        "per_protocol": {p: len(v) for p, v in per_protocol.items()},
        "contrasts": contrasts,
    }


def build(seed: int = 20261121, pilot_size: int = 24) -> dict[str, Any]:
    panel = json.loads((EVIDENCE / "unit_pilot_panel.json").read_text())
    compat = json.loads((EVIDENCE / "compatibility_model.json").read_text())["groups"]
    inventory = json.loads((EVIDENCE / "exposure_inventory.json").read_text())["inventory"]
    plumbing = inventory["classes"]["plumbing"]
    table = panel["table"]
    scenarios = {}
    for rule, groups in (
        ("registry_exposed_only", plumbing),
        ("plus_outcome_studies", inventory["outcome_exposed_groups"]),
    ):
        marked = ppd.with_exposure(table, groups)
        pilot = set(ppd.balanced_panel(marked, pilot_size, seed)["clusters"])
        scenarios[rule] = potential_eligibility(table, compat, pilot, groups)
    return {
        "note": "design and metadata only: no dataset was read, no detector was run; potential "
        "eligibility is "
        "a structural upper bound, not verified eligibility and not paired observations",
        "seed": seed,
        "pilot_size": pilot_size,
        "matrix": matrix(),
        "mechanisms": {
            p: {op: {"representation": v, "note": n} for op, (v, n) in ops.items()}
            for p, ops in MECHANISMS.items()
        },
        "eligibility": scenarios,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    text = json.dumps(build(), indent=1, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
