"""Historical exposure inventory of the dataset registry (#153, design and accounting only).

Which registry groups were the subject of a detector run in an earlier study of this repository? The
inventory reads file names under ``verification/evidence`` only (no result is opened), maps the
UCI identifiers it finds to registry groups and provenance clusters, and counts each group once.

Classes (study-specific; none of them is an approved exclusion rule):

- ``plumbing``: the registry's own ``exposed_groups`` (the pilot that informed Amendment 1);
- ``outcome``: at least one earlier study produced detector outcomes on the dataset;
- ``structure``: only partitions or structural metadata exist, which is not outcome exposure.

That outcomes exist does not show that they influenced a current design decision; the inventory
records the study so the owner can decide the rule (D-02, D-08).
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import pilot_panel_design as ppd

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = ROOT / "verification/evidence"
#: study folder -> kind of evidence its files represent
STUDIES: dict[str, str] = {
    "labelled_pool": "outcome",
    "typed_injection": "outcome",
    "typed_train_only": "outcome",
    "pool_train_only_replay": "outcome",
    "pool_extension": "outcome",
    "pool_extension_v2": "outcome",
    "pool_extension_v3": "outcome",
    "full_registry": "outcome",
    "alert_budgets": "outcome",
    "pipeline_batch": "outcome",
    "natural_temporal": "outcome",
    "pool_partitions": "structure",
}
TOKEN = re.compile(r"(?:^|[^0-9a-z])uci[_:](\d+)|^(\d{1,4})\.json$|(?:^|_)(\d{3})(?:_|\.)")


def uci_ids(names: list[str]) -> set[int]:
    """UCI identifiers in file names such as ``uci_851.json`` or ``601.json``."""
    found: set[int] = set()
    for name in names:
        for match in TOKEN.finditer(name):
            found.add(int(next(g for g in match.groups() if g)))
    return found


def study_ids(evidence: Path, studies: dict[str, str] = STUDIES) -> dict[str, set[int]]:
    out: dict[str, set[int]] = {}
    for study in studies:
        root = evidence / study
        names = [p.name for p in sorted(root.rglob("*")) if p.is_file()] if root.is_dir() else []
        out[study] = uci_ids(names)
    return out


def id_to_group(table: dict[str, Any], facts: dict[str, Any]) -> dict[int, str]:
    """UCI identifier -> registry group: a group named ``uci:N`` or a readiness fact ``uci:N``."""
    mapping: dict[int, str] = {}
    for fact_id, fact in sorted(facts.items()):
        if fact_id.startswith("uci:") and fact_id[4:].isdigit():
            mapping[int(fact_id[4:])] = fact["independent_group"]
    for group in table:
        if group.startswith("uci:") and group[4:].isdigit():
            mapping[int(group[4:])] = group
    return {i: g for i, g in mapping.items() if g in table}


def inventory(
    table: dict[str, Any],
    facts: dict[str, Any],
    ids_by_study: dict[str, set[int]],
    plumbing: list[str],
    studies: dict[str, str] = STUDIES,
) -> dict[str, Any]:
    mapping = id_to_group(table, facts)
    per_group: dict[str, dict[str, Any]] = {}
    for study, ids in sorted(ids_by_study.items()):
        for i in sorted(ids):
            if i in mapping:
                row = per_group.setdefault(mapping[i], {"studies": {}})
                row["studies"].setdefault(studies[study], []).append(study)
    for group in plumbing:
        per_group.setdefault(group, {"studies": {}})["plumbing"] = True
    for group, row in per_group.items():
        row["class"] = (
            "plumbing"
            if row.get("plumbing")
            else "outcome"
            if "outcome" in row["studies"]
            else "structure"
        )
        row["cluster"] = table[group]["cluster"]
    classes = {
        c: sorted(g for g, r in per_group.items() if r["class"] == c)
        for c in ("plumbing", "outcome", "structure")
    }
    outcome_groups = sorted(
        g for g, r in per_group.items() if r["class"] in ("plumbing", "outcome")
    )
    return {
        "unmatched_ids": {
            s: sorted(i for i in ids if i not in mapping) for s, ids in sorted(ids_by_study.items())
        },
        "groups": {g: per_group[g] for g in sorted(per_group)},
        "classes": classes,
        "outcome_exposed_groups": outcome_groups,
        "outcome_exposed_clusters": sorted({table[g]["cluster"] for g in outcome_groups}),
        "overlap_plumbing_and_outcome_studies": sorted(
            g for g in plumbing if per_group[g]["studies"].get("outcome")
        ),
    }


def build(
    panel_file: dict[str, Any],
    facts: dict[str, Any],
    evidence: Path,
    plumbing: list[str],
    seed: int,
    sizes: tuple[int, ...] = (16, 24, 32),
) -> dict[str, Any]:
    table = panel_file["table"]
    inv = inventory(table, facts, study_ids(evidence), plumbing)
    clusters = ppd.cluster_table(table)
    scenarios = {}
    for rule, groups in (
        ("registry_exposed_only", plumbing),
        ("plus_outcome_studies", inv["outcome_exposed_groups"]),
    ):
        marked = ppd.with_exposure(table, groups)
        scenarios[rule] = {
            "exposed_clusters": len({table[g]["cluster"] for g in groups}),
            "balanced": {
                str(n): ppd.panel_profile(marked, ppd.balanced_panel(marked, n, seed)["groups"])
                for n in sizes
            },
        }
    all_met = sum(1 for e in clusters.values() if e["floor"] is True and not e["exposed"])
    any_met = len({r["cluster"] for r in table.values() if r["floor"] is True and not r["exposed"]})
    return {
        "note": "accounting only; file names were read, no result was opened, no detector was run",
        "seed": seed,
        "inventory": inv,
        "floor_met_unexposed_clusters": {"every_member": all_met, "any_member": any_met},
        "scenarios": scenarios,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=EVIDENCE)
    parser.add_argument("--seed", type=int, default=20261121)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    v2 = args.evidence / "dataset_registry_v2"
    panel = json.loads((v2 / "unit_pilot_panel.json").read_text())
    facts = json.loads((v2 / "readiness_facts.json").read_text())["facts"]
    plumbing = sorted(json.loads((v2 / "linked_sets.json").read_text())["exposed_groups"])
    text = (
        json.dumps(
            build(panel, facts, args.evidence, plumbing, args.seed), indent=1, sort_keys=True
        )
        + "\n"
    )
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
