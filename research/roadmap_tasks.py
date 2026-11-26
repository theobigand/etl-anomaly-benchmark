"""Validate the thesis-remediation task list without a fixed total (#200).

A task is a checklist line ``- [ ] T### text`` in one of the numbered files of the roadmap folder.
It is *defined* where it appears without a marker and *referenced* where the line carries
``(promoted, see NN)``, which points to the file ``NN-*.md`` that defines it. The rules:

* an identifier is ``T`` plus three digits, or four and more digits without a leading zero;
* every identifier has exactly one definition; a reference must point to the file that defines it
  and carry the same checked state;
* the historical range of ``tracking.json`` (``task_range``) must be fully defined, so a removed
  task is detected; identifiers above that range must follow it without a gap, so the roadmap can
  grow without any change to this check.

Command: ``python research/roadmap_tasks.py docs/thesis-remediation`` prints ``Verified N tasks``.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

LINE = re.compile(
    r"^- \[(?P<state>[ xX])\] (?P<id>T\d\S*)(?P<ref> \(promoted, see (?P<target>\d{2})\))? ",
    re.MULTILINE,
)
IDENTIFIER = re.compile(r"T(\d{3}|[1-9]\d{3,})")
RANGE = re.compile(r"T(\d+)–T(\d+)")


@dataclass
class Result:
    count: int = 0
    errors: list[str] = field(default_factory=list)


def _range_end(root: Path) -> int:
    value = json.loads((root / "tracking.json").read_bytes()).get("task_range")
    match = RANGE.fullmatch(str(value))
    if not match or int(match.group(1)) != 1:
        raise ValueError(f"tracking.json task_range must look like T001–T415; got {value!r}")
    return int(match.group(2))


def validate(root: Path) -> Result:
    """Check the numbered roadmap files under ``root``; the errors are complete."""
    end = _range_end(root)
    errors: list[str] = []
    defined: dict[int, tuple[str, bool]] = {}
    references: list[tuple[int, str, str, bool]] = []
    for path in sorted(root.glob("[0-9][0-9]-*.md")):
        for match in LINE.finditer(path.read_bytes().decode()):
            name, identifier = path.name, match["id"]
            checked = match["state"] != " "
            if not IDENTIFIER.fullmatch(identifier):
                errors.append(f"{name}: invalid task identifier {identifier!r}")
                continue
            number = int(identifier[1:])
            if match["ref"]:
                references.append((number, name, match["target"], checked))
            elif number in defined:
                errors.append(f"{identifier}: defined in {defined[number][0]} and {name}")
            else:
                defined[number] = (name, checked)
    for number, name, target, checked in references:
        owner = defined.get(number)
        if owner is None or not owner[0].startswith(target + "-"):
            errors.append(
                f"T{number:03d}: {name} points to file {target}, which does not define it"
            )
        elif owner[1] != checked:
            state = "checked" if checked else "unchecked"
            other = "checked" if owner[1] else "unchecked"
            errors.append(
                f"T{number:03d}: {name} is {state} but its definition in {owner[0]} is {other}"
            )
    for number in range(1, end + 1):
        if number not in defined:
            errors.append(
                f"T{number:03d}: required by the historical range T001–T{end:03d} but not defined"
            )
    expected = end + 1
    for number in sorted(n for n in defined if n > end):
        if number != expected:
            errors.append(
                f"T{number:03d}: the identifiers above T{end:03d} must be contiguous; "
                f"T{expected:03d} to T{number - 1:03d} are missing"
            )
            break
        expected += 1
    return Result(count=len(defined), errors=errors)


def main(argv: list[str]) -> int:
    result = validate(Path(argv[1]))
    for error in result.errors:
        print(error, file=sys.stderr)
    if not result.errors:
        print(f"Verified {result.count} tasks")
    return 1 if result.errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
