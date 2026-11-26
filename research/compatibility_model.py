"""Compatibility model (#134): category x protocol x unit x operator x detector x metric.

One table, read from the canonical registry evidence (the participations of the utilization ledger,
``anomaly_protocols.json``, ``batch_eligibility.json``) and from the unit definitions of
``registry_units``. A participation's applicable units follow from its protocol and the audit alone;
no identifier of a dataset, view or group appears in this module, so no source has a privileged
path (a test scans the module for registry names). Nothing here runs a detector, injects a fault or
reads a result.

Each unit is labelled by how its loads or windows come about:

* ``natural``: the unit exists in the data as delivered (a row, a case, a declared relation, a
  record path);
* ``replayed``: stored records carrying their own times are replayed in time order as loads;
* ``logical``: the protocol cuts the unit from an order it imposes (consecutive rows, a window),
  because the source records no loads.

A unit that no approved protocol defines is ``provisional`` until the protocol amendment (S03,
issues #152 to #154) approves it; an unregistered unit is never counted as runnable.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pipeline_batch as pb
import registry_units as ru
import utilization_ledger as ul

EVIDENCE = ru.EVIDENCE
OUTPUT = EVIDENCE / "compatibility_model.json"
NATURAL, REPLAYED, LOGICAL = "natural", "replayed", "logical"
PROTOCOL_DEFINED, REGISTERED, PROVISIONAL = "protocol_defined", ru.REGISTERED, "provisional"
#: unit -> (kind, status, basis); the units of the unit-level protocols are named by the protocols
UNITS: dict[str, tuple[str, str, str]] = {
    "row": (NATURAL, PROTOCOL_DEFINED, "a row of a source table"),
    "time_window": (LOGICAL, PROTOCOL_DEFINED, "a window cut from an ordered series"),
    "event_sequence": (NATURAL, PROTOCOL_DEFINED, "a case or trace of an event log"),
    "relationship": (NATURAL, PROTOCOL_DEFINED, "a declared foreign-key relation"),
    "nested_path": (NATURAL, PROTOCOL_DEFINED, "a (record, path) pair of a nested document"),
    "observed_load": (NATURAL, PROVISIONAL, "a load delivered with its own identifier and time"),
    "temporal_batch": (REPLAYED, REGISTERED, "timestamped records replayed in time order as loads"),
    "event_window": (LOGICAL, PROVISIONAL, "consecutive events of a log cut into windows"),
    "relational_load": (LOGICAL, PROVISIONAL, "consecutive child rows in file order"),
    "document_batch": (LOGICAL, PROVISIONAL, "consecutive documents in source order"),
}
BATCH_METRICS = ("recall", "false_alert_rate", "roc_auc", "ap")
MATCH_METRICS = ("tp", "fp", "fn")


def unit_definitions() -> dict[str, dict[str, Any]]:
    """Every unit with its kind, status and basis."""
    return {
        name: {"kind": kind, "status": status, "basis": basis}
        for name, (kind, status, basis) in sorted(UNITS.items())
    }


def protocol_cells(protocol: str, spec: dict[str, Any]) -> list[dict[str, Any]]:
    """Unit x operator x detector x metric rows of one protocol."""
    cells = [
        {
            "unit": spec["detection_unit"],
            "operators": list(spec["mechanisms"]),
            "detectors": [],  # no registry-driven unit-level runner exists yet
            "metrics": list(MATCH_METRICS),
            "executable": False,
        }
    ]
    for unit in ru.PROTOCOL_UNITS[protocol]:
        _status, mechanisms = ru.UNITS[unit]
        runnable = unit in ru.DETECTOR_UNITS
        cells.append(
            {
                "unit": unit,
                "operators": list(mechanisms),
                "detectors": list(pb.DETECTORS) if runnable else [],
                "metrics": list(BATCH_METRICS),
                "executable": runnable,
            }
        )
    return cells


def group_units(protocol: str, entry: dict[str, Any], detection_unit: str) -> list[dict[str, Any]]:
    """Units that apply to one participation: the protocol's own and each candidate batch unit."""
    out = [{"unit": detection_unit, "runnable": False, "reason": "no registry-driven runner"}]
    for item in ru.compatibility(protocol, entry):
        out.append({"unit": item["unit"], "runnable": item["runnable"], "reason": item["reason"]})
    return out


def build(evidence: Path) -> dict[str, Any]:
    audit = json.loads((evidence / "batch_eligibility.json").read_text())["groups"]
    protocols = json.loads((evidence / "anomaly_protocols.json").read_text())["protocols"]
    participations = ul.registry_participations(evidence)
    used = {p for by_category in participations.values() for p in by_category.values()}
    unsupported = sorted(used - set(protocols))
    if unsupported:
        raise ValueError(f"protocols without a definition: {unsupported}")
    groups: dict[str, Any] = {}
    matrix: dict[str, dict[str, dict[str, dict[str, int]]]] = {}
    for group, by_category in sorted(participations.items()):
        rows = []
        for category, protocol in sorted(by_category.items()):
            units = group_units(protocol, audit[group], protocols[protocol]["detection_unit"])
            rows.append({"category": category, "protocol": protocol, "units": units})
            cell = matrix.setdefault(category, {}).setdefault(protocol, {})
            for item in units:
                counts = cell.setdefault(item["unit"], {"groups": 0, "runnable": 0})
                counts["groups"] += 1
                counts["runnable"] += item["runnable"]
        groups[group] = {"participations": rows}
    return {
        "units": unit_definitions(),
        "protocols": {p: protocol_cells(p, spec) for p, spec in sorted(protocols.items())},
        "matrix": matrix,
        "groups": groups,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, default=EVIDENCE)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    text = json.dumps(build(args.evidence), indent=1, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
