"""Static typing gate: ``verification/`` must be clean, other code may not get worse.

mypy runs over ``src/etl_benchmark``, ``experiments`` and ``verification``.
Errors under ``verification/`` always fail. For the scientific code the known
errors are listed in ``typing_baseline.txt`` (one ``path: message [code]`` per
line, no line numbers): a new error fails, and so does a baseline entry that no
longer occurs, so the list can only shrink. Annotating the scientific code is
deferred because any edit there changes the provenance fingerprint of the
archived runs.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "verification" / "typing_baseline.txt"
TARGETS = ["src/etl_benchmark", "experiments", "verification"]
LINE = re.compile(r"^(?P<path>[^:\s]+):\d+: error: (?P<message>.*)$")


def parse(output: str) -> set[str]:
    """Errors as ``path: message`` keys, without line numbers."""
    keys = set()
    for line in output.splitlines():
        found = LINE.match(line)
        if found:
            keys.add(f"{found['path']}: {found['message']}")
    return keys


def judge(found: set[str], baseline: set[str]) -> list[str]:
    """Reasons the typing gate fails (empty when it passes)."""
    problems = [
        f"error in verification/ cannot be baselined: {key}"
        for key in sorted(found)
        if key.startswith("verification/")
    ]
    problems += [
        f"new typing error: {key}"
        for key in sorted(found - baseline)
        if not key.startswith("verification/")
    ]
    problems += [f"baseline entry no longer occurs: {key}" for key in sorted(baseline - found)]
    return problems


def run_mypy(mypy: list[str]) -> str:
    env = {**os.environ, "MYPYPATH": os.pathsep.join(["src", "experiments", "."])}
    command = [*mypy, "--python-executable", sys.executable, "--ignore-missing-imports"]
    command += ["--explicit-package-bases", "--no-error-summary", *TARGETS]
    done = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, check=False)
    if done.returncode not in (0, 1):
        raise RuntimeError(f"mypy did not run: {done.stderr.strip() or done.stdout.strip()}")
    return done.stdout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mypy", nargs="+", default=["mypy"], help="mypy command")
    parser.add_argument("--baseline", type=Path, default=BASELINE)
    args = parser.parse_args(argv)
    try:
        found = parse(run_mypy(args.mypy))
        baseline = {line for line in args.baseline.read_text().splitlines() if line}
    except (OSError, RuntimeError) as exc:
        print(f"typing: INCOMPLETE ({exc})")
        return 1
    problems = judge(found, baseline)
    for problem in problems:
        print(f"typing: {problem}")
    print(f"typing: {'FAIL' if problems else 'PASS'} ({len(found)} known errors in the baseline)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
