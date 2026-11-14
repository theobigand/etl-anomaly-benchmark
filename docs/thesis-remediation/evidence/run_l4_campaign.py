# ruff: noqa: E501
"""Resumable per-module native mutation sweep of every L4 unit, with a durable checkpoint after each module.

    OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES python docs/thesis-remediation/evidence/run_l4_campaign.py STATE.json [--only path ...]

One `mutmut run "<module>.*"` per module under a wall-clock limit. mutmut keeps its verdicts in mutants/, so a
module that hit the limit or was interrupted continues where it stopped on the next invocation. After every module
the counts (killed, survived, timeout, incomplete, not_run) and the source digest are written to STATE.json.
`--rerun` measures a module again even when it is recorded complete (mutmut keeps the killed verdicts and
re-tests the others against the current tests). A mutant
with no verdict is `not_run` and is never counted as killed. This script reads and executes; it records no owner
decision and touches no policy file.
"""

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
STATUS = {1: "killed", 0: "survived", -24: "timeout", 255: "incomplete", None: "not_run"}
LIMIT_SECONDS = 2 * 3600
MAX_CHILDREN = "6"


def dotted(path: str) -> str:
    return path.removeprefix("src/").removesuffix(".py").replace("/", ".")


def counts(path: str) -> dict[str, int]:
    meta = ROOT / "mutants" / f"{path}.meta"
    out: dict[str, int] = {}
    if not meta.exists():
        return out
    for code in json.loads(meta.read_text())["exit_code_by_key"].values():
        name = STATUS.get(code, f"exit_{code}")
        out[name] = out.get(name, 0) + 1
    return out


def modules() -> list[str]:
    policy = json.loads((ROOT / "verification/mutation_risk_policy.json").read_text())["units"]
    campaign = json.loads(
        (ROOT / "docs/thesis-remediation/evidence/risk-native-campaign-2026-11-07.json").read_text()
    )["modules"]
    l4 = [p for p, u in policy.items() if u["level"] == "L4"]
    return sorted(l4, key=lambda p: (campaign.get(p, {}).get("eligible", 0), p))


def main() -> None:
    state_path = Path(sys.argv[1])
    rerun = "--rerun" in sys.argv
    args = [a for a in sys.argv[2:] if a != "--rerun"]
    only = args[args.index("--only") + 1 :] if "--only" in args else None
    state = json.loads(state_path.read_text()) if state_path.exists() else {"modules": {}}
    for path in only or modules():
        sha = hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        done = state["modules"].get(path)
        if not rerun and done and done["sha256"] == sha and done["status"] == "complete":
            continue
        began = time.time()
        try:
            run = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "mutmut",
                    "run",
                    f"{dotted(path)}.*",
                    "--max-children",
                    MAX_CHILDREN,
                ],
                cwd=ROOT,
                timeout=LIMIT_SECONDS,
                capture_output=True,
                text=True,
            )
            rc, tail = run.returncode, (run.stdout + run.stderr)[-400:]
        except subprocess.TimeoutExpired:
            rc, tail = "wall_clock_limit", ""
        tally = counts(path)
        total = sum(tally.values())
        finished = bool(total) and not tally.get("not_run") and not tally.get("incomplete")
        state["modules"][path] = {
            "sha256": sha,
            "status": "complete" if finished else "incomplete",
            "returncode": rc,
            "counts": tally,
            "total": total,
            "seconds": round(time.time() - began),
            "tail": tail,
        }
        state_path.write_text(json.dumps(state, indent=2) + "\n")
        print(path, state["modules"][path]["status"], tally, flush=True)


if __name__ == "__main__":
    main()
