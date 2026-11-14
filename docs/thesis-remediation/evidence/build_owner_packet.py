# ruff: noqa: E501
"""Second owner-review packet: the survivors that remain after the behavioral tests, grouped by class.

    python docs/thesis-remediation/evidence/build_owner_packet.py

Reads `l4-campaign-2026-11-13/final-measurement.json` and the survivor dumps in
`l4-campaign-2026-11-13/survivors/<unit>.txt` (written by `mutdiff.py` straight after each unit's run), and writes
`../equivalence/owner_review_candidates_2026-11-14.json` and `../OWNER_EQUIVALENCE_REVIEW_PACKET_2_2026-11-14.md`.

Nothing here is an owner decision. Every entry is PROPOSED and UNAPPROVED; the 43 candidates of the first packet and
`verification/mutation_equivalence.json` are not read or changed. A survivor is put in a class only when its textual
difference matches one of the patterns below; everything else is listed as unclassified, not as an equivalence
candidate. The patterns correspond to the counterexample searches of `tests/test_mutation_equivalence_probes.py`.
"""

import json
import re
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "l4-campaign-2026-11-13"
ROOT = HERE.parents[2]

# class id -> (title, why it should not change behaviour, evidence)
CLASSES = {
    "split-limit": (
        "limit of a split whose first part is read",
        "`text.split(sep, n)[0]` is the part before the first separator for any n >= 1 or no limit.",
        "test_the_first_part_of_a_split_does_not_depend_on_a_limit_of_one_or_more",
    ),
    "falsy-flag": (
        "None for a flag whose value is False",
        "`allow_nan`, `annotate_fields`, `sort`, `index`, `replace`, `check`, `exist_ok`, `parents` read their value as a truth value; None and False act alike.",
        "test_json_with_allow_nan_none_*, test_ast_dump_*, test_a_missing_sort_flag_*, test_a_missing_index_flag_*, test_a_missing_replace_flag_*",
    ),
    "name-case": (
        "case of a name the library reads without case",
        "package names (`version`), time-zone names, sort kinds, time units, HTTP header names and codec names are matched without case.",
        "test_a_package_version_*, test_a_timezone_name_*, test_a_sort_kind_*, test_http_header_names_*, test_a_codec_name_*",
    ),
    "unset-state": (
        "initial value of an attribute that a fit sets before any read",
        "the attribute is assigned in `fit`; every reader first checks the other attribute of the pair or is only reached after `fit`.",
        "per-unit reading of the readers; not mechanised",
    ),
    "default-argument": (
        "argument dropped or set to its default",
        "the callee's default equals the original value, or the argument is overridden afterwards.",
        "per-unit reading; the owner left `astype(None)` and `replace=None` inconclusive on 2026-11-11",
    ),
    "signed-division": (
        "division by -1 for a multiplication by -1",
        "x / -1 and x * -1 give identical floats.",
        "test_a_division_by_minus_one_is_a_multiplication_by_minus_one",
    ),
}


def classify(diff: list[str]) -> str | None:
    """The class of a one-line change, or None when it is not a recognised equivalence pattern."""
    minus = [line[1:].strip() for line in diff if line.startswith("-")]
    plus = [line[1:].strip() for line in diff if line.startswith("+")]
    if len(minus) != 1 or len(plus) != 1:
        return None
    before, after = minus[0], plus[0]
    if re.search(r"\.split\([^)]*\)\[0\]", before) and re.sub(
        r"split\(([^,)]+)(?:, ?-?\d*)?\)", r"split(\1)", before
    ) == re.sub(r"split\(([^,)]+)(?:, ?-?\d*)?\)", r"split(\1)", after):
        return "split-limit"
    if re.search(r'version\("[a-z-]+"\)', before) and before.lower() == after.lower():
        return "name-case"
    if before.replace("False", "None") == after or before.replace("0", "None") == after:
        return (
            "falsy-flag"
            if re.search(
                r"(allow_nan|annotate_fields|sort|index|replace|check|exist_ok|parents)=", after
            )
            else None
        )
    if re.search(r"\b(self\.\w+).*= None$", before) and re.search(r'= ""$', after):
        return "unset-state"
    if re.search(r"tz_localize|to_timedelta|kind=|tz=", before) and before.lower() == after.lower():
        return "name-case"
    if before.replace("* -1", "/ -1") == after:
        return "signed-division"
    if re.search(r"(dtype|astype)\(?.*None", after) and re.sub(
        r"astype\([^)]*\)|dtype=\w+", "X", before
    ) == re.sub(r"astype\(None\)|dtype=None", "X", after):
        return "default-argument"
    return None


def parse(text: str) -> list[dict]:
    items = []
    for block in text.split("## ")[1:]:
        head, *lines = block.splitlines()
        items.append(
            {
                "key": head.replace(" [timeout]", "").split()[0],
                "timeout": "[timeout]" in head,
                "diff": [x for x in lines if x[:1] in "+-"],
            }
        )
    return items


def main() -> None:
    record = json.loads((OUT / "final-measurement.json").read_text())
    units = {}
    for path, module in sorted(record["modules"].items()):
        if module["status"] not in ("FAIL", "INCOMPLETE"):
            continue
        dump = OUT / "survivors" / (path.replace("/", "__") + ".txt")
        found = parse(dump.read_text()) if dump.exists() else None
        classes: dict[str, list[dict]] = {}
        open_gap: list[dict] = []
        for item in found or []:
            kind = classify(item["diff"])
            entry = {"mutant": item["key"], "timeout": item["timeout"], "change": item["diff"]}
            (classes.setdefault(kind, []) if kind else open_gap).append(entry)
        units[path] = {
            "level": module["level"],
            "threshold": module["threshold"],
            "source_sha256": module["source_sha256"],
            "catalog_sha256": module["catalog_sha256"],
            "eligible": module["eligible"],
            "killed": module["killed"],
            "needed_for_threshold": module["needed_for_threshold"],
            "measured_on": module["measured_on"],
            "survivor_dump": dump.relative_to(HERE).as_posix() if dump.exists() else None,
            "candidate_classes": classes,
            "unclassified": open_gap,
        }
    packet = {
        "status": "PROPOSED - NOT APPROVED",
        "head": record["head"],
        "policy_sha256": record["policy_sha256"],
        "note": "No entry is an owner decision. The 43 candidates of owner_review_candidates_2026-11-12.json and verification/mutation_equivalence.json are untouched.",
        "classes": {
            k: {"title": v[0], "reasoning": v[1], "probe": v[2]} for k, v in CLASSES.items()
        },
        "units": units,
    }
    (HERE.parent / "equivalence" / "owner_review_candidates_2026-11-14.json").write_text(
        json.dumps(packet, indent=1, sort_keys=True) + "\n"
    )
    rows = []
    for path, unit in units.items():
        candidates = sum(len(v) for v in unit["candidate_classes"].values())
        gap = len(unit["unclassified"])
        missing = max(0, unit["needed_for_threshold"] - unit["killed"])
        rows.append(
            f"| `{path}` | {unit['level']} | {unit['killed']}/{unit['eligible']} | {missing} | {candidates} | {gap} | {unit['measured_on'].split(' (')[0]} |"
        )
    text = f"""# Second owner-review packet, 2026-11-14 (PROPOSED, NOT APPROVED)

Prepared after the behavioral remediation of `L4_CAMPAIGN_REPORT_2026-11-13.md`, as the user's priority 4 asks: tests first, equivalence only for what remains. It approves nothing, adds
nothing to `verification/mutation_equivalence.json` and leaves the 43 candidates of the first packet (`OWNER_EQUIVALENCE_REVIEW_2026-11-12.md`) as they were. The four `lstm_detector`
records stay subject to the repository validator (their `torch 2.15.0+cpu` pin is not met on this machine).

Source: `{record["head"][:7]}`, policy digest `{record["policy_sha256"][:12]}`. Machine-readable form: `equivalence/owner_review_candidates_2026-11-14.json` (exact mutant keys, textual change, source and
catalog digests per unit; survivor dumps in `evidence/l4-campaign-2026-11-13/survivors/`).

## How to read it

For each unit that still fails or is incomplete, survivors are split in two. **Candidate classes** are survivors whose one-line change matches a recognised pattern (below); each class cites a counterexample search in
`tests/test_mutation_equivalence_probes.py`, which passed: no input was found that tells the mutant from the original. **Unclassified** survivors match no pattern: they are not proposed as equivalent. Some of them are equivalent in a way the
patterns do not recognise, others can be killed by a test not written yet; telling them apart is the remaining per-mutant work. Missing kills = the kills still needed to reach the threshold.

| Unit | Level | Killed / eligible | Missing kills | In candidate classes | Unclassified | Measured on |
| --- | --- | --- | --- | --- | --- | --- |
{chr(10).join(rows)}

## Classes

{chr(10).join(f"- **{k}** ({v[0]}): {v[1]} Search: {v[2]}." for k, v in CLASSES.items())}

## What the owner would be deciding

A class is not an approval of a mutant. If the owner accepts a class, the next step is a record in `verification/mutation_equivalence.json` per mutant, with the exact key, the source and catalog
digests listed in the JSON, the environment, and the review fields the validator requires. Not before. Where a unit's missing kills exceed its candidate-class survivors, accepting every class still would not
make it pass: those units need tests or a change of level, which is not proposed here.
"""
    (HERE.parent / "OWNER_EQUIVALENCE_REVIEW_PACKET_2_2026-11-14.md").write_text(text)
    print(
        len(units),
        "units;",
        sum(len(u["unclassified"]) for u in units.values()),
        "unclassified survivors",
    )


if __name__ == "__main__":
    main()
