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

import difflib
import json
import re
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "l4-campaign-2026-11-13"
ROOT = HERE.parents[2]

# class id -> (title, condition under which it holds, counterexample searches that back it)
CLASSES = {
    "split-limit": (
        "limit of a split whose first part is read",
        "`text.split(sep, n)[0]` is the part before the first separator for any limit n >= 1 or none; the class holds only when the new limit is at least 1 or absent.",
        ["test_the_first_part_of_a_split_does_not_depend_on_a_limit_of_one_or_more"],
    ),
    "falsy-flag": (
        "False replaced by None for a flag read as a truth value",
        "Only `False` -> `None` for allow_nan, annotate_fields, sort, index, replace, check or ignore_index. `True` -> `None` (for example `exist_ok`, `parents`) is not in the class.",
        [
            "test_json_with_allow_nan_none_refuses_non_finite_numbers_like_false",
            "test_ast_dump_without_field_names_is_the_same_for_false_and_none",
            "test_a_missing_sort_flag_in_a_groupby_means_no_sorting_like_false",
            "test_a_missing_index_flag_in_to_csv_writes_no_index_like_false",
            "test_a_missing_replace_flag_in_a_choice_samples_without_replacement_like_false",
            "test_a_missing_check_flag_in_a_subprocess_run_behaves_like_false",
        ],
    ),
    "name-case": (
        "case of a name the library reads without case",
        "Only a quoted name of three letters or more that changes case alone, in `version(...)`, `tz_localize(...)`/`tz=` (utc), `kind=` (stable), `unit=` (min) or `decode(...)`. One-letter units are not in the class (`m` and `M` differ). It says nothing about the dependency range: the owner's reason for `inconclusive` on 2026-11-11 was exactly that.",
        [
            "test_a_package_version_is_looked_up_without_regard_to_case",
            "test_a_timezone_name_is_read_without_case_for_utc",
            "test_a_sort_kind_is_read_without_case",
            "test_the_minute_unit_is_read_without_case",
            "test_a_codec_name_is_read_without_case",
        ],
    ),
    "signed-division": (
        "division by -1 for a multiplication by -1",
        "Holds when the operand is a float array or a float; an integer operand gives float for `/` and integer for `*`. The operand's type is not checked by this builder: it must be read per mutant.",
        ["test_a_division_by_minus_one_is_a_multiplication_by_minus_one_for_floats"],
    ),
}
NOTED = {
    "unset-state": "an initial attribute value changed from None to an empty string; equivalence needs every reader of the attribute read, per unit",
    "default-dtype": "`astype(int)`/`dtype=int` replaced by None gives float64; previously judged inconclusive by the owner for `astype(None)`",
}
FLAGS = {"allow_nan", "annotate_fields", "sort", "index", "replace", "check", "ignore_index"}
CASE_CONTEXT = {
    ("version", "("): {"numpy", "pandas", "torch", "pyod", "scikit-learn", "great-expectations"},
    ("tz_localize", "("): {"utc"},
    ("tz", "="): {"utc"},
    ("kind", "="): {"stable"},
    ("unit", "="): {"min"},
    ("decode", "("): {"utf-8"},
}


def _tokens(line: str) -> list[str]:
    return re.findall(r'"[^"]*"|\'[^\']*\'|\w+|[^\s\w]', line)


def _single_change(before: str, after: str):
    a, b = _tokens(before), _tokens(after)
    ops = [
        op
        for op in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes()
        if op[0] != "equal"
    ]
    return (a, b, *ops[0]) if len(ops) == 1 else None


def classify(diff: list[str]) -> str | None:
    """The class of a one-line change that matches a recognised pattern, else None."""
    minus = [line[1:].strip() for line in diff if line.startswith("-")]
    plus = [line[1:].strip() for line in diff if line.startswith("+")]
    if len(minus) != 1 or len(plus) != 1:
        return None
    found = _single_change(minus[0], plus[0])
    if not found:
        return None
    a, b, tag, i1, i2, j1, j2 = found
    old, new = a[i1:i2], b[j1:j2]
    if "split" in a[:i1] and a[-3:] == ["[", "0", "]"]:
        split_at = len(a[:i1]) - 1 - a[:i1][::-1].index("split")
        is_limit = (
            tag == "replace" and len(old) == len(new) == 1 and old[0].isdigit() and new[0].isdigit()
            and int(old[0]) >= 1 and int(new[0]) >= 1 and a[i1 - 1] == "," and split_at < i1
        )  # fmt: skip
        is_dropped = tag == "delete" and (
            (old[0] == "," and len(old) == 2 and old[1].isdigit() and int(old[1]) >= 1)
            or (len(old) == 1 and old[0].isdigit() and int(old[0]) >= 1 and a[i1 - 1] == ",")
        )
        if is_limit or is_dropped:
            return "split-limit"
    if (
        tag == "replace"
        and old == ["False"]
        and new == ["None"]
        and i1 >= 2
        and a[i1 - 1] == "="
        and a[i1 - 2] in FLAGS
    ):
        return "falsy-flag"
    if (
        tag == "replace"
        and len(old) == len(new) == 1
        and old[0].startswith('"')
        and new[0].startswith('"')
        and i1 >= 2
    ):
        before, after = old[0].strip('"'), new[0].strip('"')
        context = CASE_CONTEXT.get((a[i1 - 2], a[i1 - 1]))
        if (
            context
            and before != after
            and before.lower() == after.lower()
            and len(before) >= 3
            and before.lower() in context
        ):
            return "name-case"
    if tag == "replace" and old == ["*"] and new == ["/"] and b[j1 + 1 : j1 + 3] == ["-", "1"]:
        return "signed-division"
    return None


def noted(diff: list[str]) -> str | None:
    """A pattern that is not proposed as a class but worth naming."""
    minus = [line[1:].strip() for line in diff if line.startswith("-")]
    plus = [line[1:].strip() for line in diff if line.startswith("+")]
    if len(minus) == 1 and len(plus) == 1:
        if re.search(r"self\.\w+(: [^=]+)? = None$", minus[0]) and re.search(r'= ""$', plus[0]):
            return "unset-state"
        if re.search(r"(astype\(|dtype=)(int|float|bool)", minus[0]) and re.search(
            r"(astype\(|dtype=)None", plus[0]
        ):
            return "default-dtype"
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


def dotted(path: str) -> str:
    return path.removeprefix("src/").removesuffix(".py").replace("/", ".")


def decided() -> dict[str, dict]:
    """Mutants that already carry an owner verdict, and those of the first packet (read only)."""
    records = json.loads((ROOT / "verification" / "mutation_equivalence.json").read_text())[
        "records"
    ]
    first = json.loads(
        (HERE.parent / "equivalence" / "owner_review_candidates_2026-11-12.json").read_text()
    )
    out = {
        r["id"]: {"owner_verdict": r["verdict"], "decision_date": r.get("decision_date")}
        for r in records
    }
    for r in first.get("records", []):
        out.setdefault(r["id"], {})["first_packet"] = True
    return out


def main() -> None:
    record = json.loads((OUT / "final-measurement.json").read_text())
    prior = decided()
    units = {}
    for path, module in sorted(record["modules"].items()):
        if module["status"] not in ("FAIL", "INCOMPLETE"):
            continue
        dump = OUT / "survivors" / (path.replace("/", "__") + ".txt")
        found = parse(dump.read_text()) if dump.exists() else None
        classes: dict[str, list[dict]] = {}
        already: list[dict] = []
        unclassified: list[dict] = []
        noted_patterns: dict[str, int] = {}
        for item in found or []:
            full = f"{dotted(path)}.{item['key']}"
            entry = {
                "mutant": item["key"],
                "id": full,
                "timeout": item["timeout"],
                "change": item["diff"],
            }
            if full in prior:
                already.append({**entry, **prior[full]})
                continue
            kind = classify(item["diff"])
            if kind:
                classes.setdefault(kind, []).append(entry)
                continue
            hint = noted(item["diff"])
            if hint:
                noted_patterns[hint] = noted_patterns.get(hint, 0) + 1
            unclassified.append({**entry, **({"noted_pattern": hint} if hint else {})})
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
            "already_decided_or_in_first_packet": already,
            "unclassified": unclassified,
            "noted_patterns_not_proposed": noted_patterns,
        }
    packet = {
        "status": "PROPOSED - NOT APPROVED",
        "head": record["head"],
        "policy_sha256": record["policy_sha256"],
        "note": "No entry is an owner decision. The 43 candidates of owner_review_candidates_2026-11-12.json and verification/mutation_equivalence.json are read, never changed. A mutant that already has an owner verdict or is in the first packet is listed apart and is not re-proposed.",
        "classes": {
            k: {"title": v[0], "condition": v[1], "probes": v[2]} for k, v in CLASSES.items()
        },
        "noted_patterns": NOTED,
        "units": units,
    }
    (HERE.parent / "equivalence" / "owner_review_candidates_2026-11-14.json").write_text(
        json.dumps(packet, indent=1, sort_keys=True) + "\n"
    )
    rows = []
    for path, unit in units.items():
        candidates = sum(len(v) for v in unit["candidate_classes"].values())
        missing = max(0, unit["needed_for_threshold"] - unit["killed"])
        verdict = "no (timeouts)" if missing == 0 else "no"
        rows.append(
            f"| `{path}` | {unit['level']} | {unit['killed']}/{unit['eligible']} | {missing} | {candidates} | "
            f"{len(unit['already_decided_or_in_first_packet'])} | {len(unit['unclassified'])} | {verdict} | {unit['measured_on'].split(' (')[0]} |"
        )
    class_lines = "\n".join(
        f"- **{k}** ({v[0]}): {v[1]} Searches: {', '.join(f'`{n}`' for n in v[2])}."
        for k, v in CLASSES.items()
    )
    noted_lines = "\n".join(f"- **{k}**: {v}." for k, v in NOTED.items())
    text = f"""# Second owner-review packet, 2026-11-14 (PROPOSED, NOT APPROVED)

Prepared after the behavioral remediation of `L4_CAMPAIGN_REPORT_2026-11-13.md`, as the user's priority 4 asks: tests first, equivalence only for what remains. It approves nothing, adds
nothing to `verification/mutation_equivalence.json` and leaves the 43 candidates of the first packet (`OWNER_EQUIVALENCE_REVIEW_2026-11-12.md`) as they were. The four `lstm_detector`
records stay subject to the repository validator (their `torch 2.15.0+cpu` pin is not met on this machine).

Source: `{record["head"][:7]}`, policy digest `{record["policy_sha256"][:12]}`. Machine-readable form: `equivalence/owner_review_candidates_2026-11-14.json` (exact mutant identities, textual change, source and
catalog digests per unit; survivor dumps in `evidence/l4-campaign-2026-11-13/survivors/`).

## How to read it

For each unit that still fails or is incomplete, survivors are split four ways.

- **Candidate classes**: survivors whose one-line change matches a recognised pattern (below). Each class lists the counterexample searches of `tests/test_mutation_equivalence_probes.py` that back it; they ran on
  one environment and found no input that tells the mutant from the original. That is evidence for the owner, not proof across the supported dependency range.
- **Already decided or in the first packet**: mutants that carry an owner verdict in `verification/mutation_equivalence.json` (accepted or inconclusive, 2026-11-11) or sit in the first packet. They are listed with their
  verdict and not re-proposed here; the packet does not reopen a decision.
- **Unclassified**: no pattern matches. Not proposed as equivalent. Some are equivalent in a way the patterns do not recognise (for example an attribute initialised with an empty string that every reader overwrites),
  others can be killed by a test not written yet; telling them apart is the remaining per-mutant work. Two patterns are named in the JSON (`noted_patterns_not_proposed`) but not proposed, see below.
- Missing kills = the kills still needed to reach the threshold. For most units accepting every candidate class would still leave kills missing (compare the two columns).

| Unit | Level | Killed / eligible | Missing kills | Candidate classes | Decided / first packet | Unclassified | Passes now | Measured on |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
{chr(10).join(rows)}

## Classes

{class_lines}

Noted but not proposed (no probe, needs reading per mutant):

{noted_lines}

## What the owner would be deciding

A class is not an approval of a mutant. If the owner accepts a class, the next step is a record in `verification/mutation_equivalence.json` per mutant, with the exact identity, the source and catalog
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
