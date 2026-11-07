"""Evidence bundles: archives that can carry the named evidence files and nothing else.

A profile job packs the files its ``make`` target wrote and the release job
unpacks them at the repository root. Both directions enforce an allowlist of
exact relative paths, so a bundle cannot smuggle a dataset (or write outside
the checkout): any other member refuses the whole archive before anything is
extracted. The REAL job, which runs where the raw research datasets are, packs
two small JSON reports and cannot pack more.
"""

from __future__ import annotations

import argparse
import json
import re
import tarfile
from pathlib import Path
from typing import IO, cast

ROOT = Path(__file__).resolve().parents[1]
MAX_MEMBER = 5 * 1024 * 1024
MAX_MEMBERS = 512
MAX_TOTAL = 64 * 1024 * 1024
_EVIDENCE = "experiments/results/evidence/"
_RESULTS = "experiments/results/"
KINDS = {
    "fast": (
        "coverage.json",
        _RESULTS + "pytest.xml",
        _RESULTS + "verification_fast.json",
        _EVIDENCE + "fast.json",
    ),
    "static": (
        _RESULTS + "verifier_coverage.json",
        _RESULTS + "types_report.json",
        _EVIDENCE + "tools.json",
        _EVIDENCE + "types.json",
    ),
    "reproduction": (_RESULTS + "reproducibility.json", _EVIDENCE + "reproduction.json"),
    "faults": (_RESULTS + "fault_matrix.json", _EVIDENCE + "faults.json"),
    "deep": (
        "mutants/mutmut-cicd-stats.json",
        "mutants/results.txt",
        _EVIDENCE + "deep.json",
    ),
    "real": (_RESULTS + "real_verification.json", _EVIDENCE + "real.json"),
    # REAL on a hosted runner: the same reports plus the record of the verified download
    "real-hosted": (
        _RESULTS + "real_verification.json",
        _RESULTS + "real_acquisition.json",
        _EVIDENCE + "real.json",
    ),
}


class BundleError(Exception):
    """The bundle would carry, or already carries, something other than evidence."""


def _allowed(kind: str | None) -> set[str]:
    if kind is None:
        return {name for names in KINDS.values() for name in names}
    if kind not in KINDS:
        raise BundleError(f"unknown kind {kind!r}; the kinds are {', '.join(KINDS)}")
    return set(KINDS[kind])


def deep_artifacts(root: Path) -> list[str]:
    """Return the current DEEP envelope's verified raw artifacts.

    The envelope alone is insufficient: its listed campaign must still validate
    against the current policy, source inventory and execution binding before
    the native files are eligible for transfer.
    """
    from verification import mutation_campaign

    evidence = root / _EVIDENCE / "deep.json"
    try:
        document = json.loads(evidence.read_text())
        result = document["result"]
        if document.get("kind") != "deep" or result.get("format_version") != 2:
            raise ValueError("DEEP evidence is not a current campaign")
        paths = mutation_campaign.validate_current(result, root)
        names = set(KINDS["deep"])
        names.update(path.resolve().relative_to(root.resolve()).as_posix() for path in paths)
        return sorted(names)
    except (OSError, KeyError, TypeError, ValueError) as exc:
        raise BundleError(
            f"deep evidence cannot identify its current raw artifacts: {exc}"
        ) from exc


def _deep_member_allowed(name: str, root: Path) -> bool:
    """Allow only raw files belonging to a classified module or canonical attempt."""
    try:
        units = json.loads((root / "verification/mutation_risk_policy.json").read_text())["units"]
    except (OSError, KeyError, TypeError, ValueError):
        return False
    native = {f"mutants/{source}{suffix}" for source in units for suffix in ("", ".meta", ".spans")}
    return name in native or bool(
        re.fullmatch(r"mutants/attempts/[0-9a-f]{32}/(?:execution\.json|native\.log)", name)
    )


def pack(kind: str, root: Path, output: Path, allow_missing: bool = False) -> Path:
    """Archive the evidence files of ``kind`` found under ``root``."""
    names = []
    selected = deep_artifacts(root) if kind == "deep" and not allow_missing else _allowed(kind)
    for name in selected:
        path = root / name
        if not path.is_file():
            if allow_missing:
                continue
            raise BundleError(f"{name} is missing")
        if path.stat().st_size > MAX_MEMBER:
            raise BundleError(f"{name} is larger than {MAX_MEMBER} bytes")
        if name.endswith(".json"):
            try:
                json.loads(path.read_text())
            except ValueError as exc:
                raise BundleError(f"{name} is not JSON: {exc}") from exc
        names.append(name)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(output, "w:gz") as archive:
        for name in names:
            archive.add(root / name, arcname=name)
    return output


def unpack(bundle: Path, root: Path, kind: str | None = None) -> list[str]:
    """Extract an allowed bundle under ``root``; refuse it whole when anything is not allowed."""
    allowed = _allowed(kind)
    try:
        with tarfile.open(bundle) as archive:
            members = archive.getmembers()
            if len(members) > MAX_MEMBERS:
                raise BundleError(f"bundle has more than {MAX_MEMBERS} members")
            if sum(member.size for member in members) > MAX_TOTAL:
                raise BundleError(f"bundle is larger than {MAX_TOTAL} bytes")
            seen: set[str] = set()
            for member in members:
                dynamic_deep = kind in (None, "deep") and _deep_member_allowed(member.name, root)
                if member.name in seen:
                    raise BundleError(f"{member.name!r} occurs more than once")
                seen.add(member.name)
                if member.name not in allowed and not dynamic_deep:
                    raise BundleError(f"{member.name!r} is not an allowed evidence file")
                if not member.isreg():
                    raise BundleError(f"{member.name} is not a regular file")
                if member.size > MAX_MEMBER:
                    raise BundleError(f"{member.name} is larger than {MAX_MEMBER} bytes")
            for member in members:
                target = root / member.name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(cast(IO[bytes], archive.extractfile(member)).read())
    except (tarfile.TarError, OSError, EOFError) as exc:
        raise BundleError(f"{bundle} is not a readable archive: {exc}") from exc
    return [member.name for member in members]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    make = sub.add_parser("pack", help="archive the evidence files of one kind")
    make.add_argument("kind", choices=sorted(KINDS))
    make.add_argument("--root", type=Path, default=ROOT)
    make.add_argument("--output", type=Path, required=True)
    make.add_argument("--allow-missing", action="store_true", help="skip files a failed job lacks")
    take = sub.add_parser("unpack", help="extract an archive that holds only evidence files")
    take.add_argument("bundle", type=Path)
    take.add_argument("--root", type=Path, default=ROOT)
    take.add_argument("--kind", choices=sorted(KINDS))
    args = parser.parse_args(argv)
    try:
        if args.command == "pack":
            pack(args.kind, args.root, args.output, args.allow_missing)
            print(f"packed {args.kind} evidence into {args.output}")
        else:
            for name in unpack(args.bundle, args.root, args.kind):
                print(f"unpacked {name}")
    except BundleError as exc:
        print(f"REFUSED: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
