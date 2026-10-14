"""Attach the current coverage and revision to the verification profile."""

from __future__ import annotations

import argparse
import copy
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path


def build_profile(template: dict, coverage: dict, *, revision: str, generated_at: str) -> dict:
    """Build a fresh profile without changing its policy or scope."""
    result = copy.deepcopy(template)
    result["source_revision"] = revision
    result["generated_at"] = generated_at
    totals = coverage["totals"]
    result["coverage"]["line"] = {
        "covered": totals["covered_lines"],
        "coverable": totals["num_statements"],
    }
    result["coverage"]["branch"] = {
        "covered": totals["covered_branches"],
        "coverable": totals["num_branches"],
    }
    result["coverage"]["per_unit"] = [
        {
            "unit": path,
            "line": {
                "covered": values["summary"]["covered_lines"],
                "coverable": values["summary"]["num_statements"],
            },
            "branch": {
                "covered": values["summary"]["covered_branches"],
                "coverable": values["summary"]["num_branches"],
            },
        }
        for path, values in sorted(coverage["files"].items())
    ]
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coverage", type=Path, required=True)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    result = build_profile(
        json.loads(args.template.read_text()),
        json.loads(args.coverage.read_text()),
        revision=revision,
        generated_at=datetime.now(UTC).isoformat(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
