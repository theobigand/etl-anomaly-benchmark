"""Naturally labelled chronological study on SKAB and NAB series (issue 78).

Protocol: verification/natural_temporal.md. Series are fetched from a pinned commit into
``data/temporal`` (not redistributed), hashed against a manifest, read with their own timestamps,
labelled by the producer's markup, and evaluated with the chronological decision study of
``temporal_decision.py`` and the 17 detectors of the registry.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

os.environ.setdefault("TQDM_DISABLE", "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(HERE), str(ROOT / "src")]

import pool_chrono as pc  # noqa: E402
import temporal_decision as td  # noqa: E402

from etl_benchmark.registry import DEEP_NAMES, DETECTOR_NAMES  # noqa: E402

SOURCES: dict[str, dict[str, str]] = {
    "skab": {
        "repository": "waico/SKAB",
        "commit": "b2c0d46c2971dcbfe71e26087b6d231998bb91c2",
        "licence": "GPL-3.0 (repository); Kaggle DOI 10.34740/kaggle/dsv/1693952",
        "producer": "Skoltech Anomaly Benchmark testbed",
    },
    "nab": {
        "repository": "numenta/NAB",
        "commit": "ea702d75cc2258d9d7dd35ca8e5e2539d71f3140",
        "licence": "MIT (repository); terms of the third-party producers not stated per file",
        "producer": "Numenta Anomaly Benchmark corpus",
    },
}
DATA_DIR = ROOT / "data" / "temporal"
MANIFEST = ROOT / "verification" / "evidence" / "natural_temporal" / "manifest.json"
MAX_BYTES = 100 * 1024 * 1024
WINDOW = 24
#: alert-rate prior used when the fitting period holds no labelled anomaly (amendment 1)
PI_FLOOR = 0.01
MIN_TEST = pc.MIN_TEST_POSITIVES
SEEDS: tuple[int, ...] = (42, 1, 2, 3, 4, 5, 6, 7, 8, 9)
NAB_FAMILIES = {
    "realAWSCloudwatch": "nab_aws",
    "realAdExchange": "nab_adexchange",
    "realTraffic": "nab_traffic",
    "realTweets": "nab_tweets",
}
NAB_KNOWN_CAUSE = {
    "nyc_taxi": "nab_taxi",
    "machine_temperature_system_failure": "nab_machine",
    "ambient_temperature_system_failure": "nab_ambient",
    "cpu_utilization_asg_misconfiguration": "nab_asg",
    "ec2_request_latency_system_failure": "nab_latency",
    "rogue_agent_key_hold": "nab_rogue",
    "rogue_agent_key_updown": "nab_rogue",
}
SKAB_DIRS = ("valve1", "valve2", "other")


def fetch(dest: Path = DATA_DIR) -> None:
    """Download the pinned snapshot of each source and keep only the files the study reads."""
    for key, src in SOURCES.items():
        url = f"https://codeload.github.com/{src['repository']}/zip/{src['commit']}"
        with urllib.request.urlopen(url, timeout=120) as response:  # noqa: S310 - pinned host
            blob = response.read(MAX_BYTES + 1)
        if len(blob) > MAX_BYTES:
            raise ValueError(f"{key}: snapshot larger than {MAX_BYTES} bytes")
        with zipfile.ZipFile(io.BytesIO(blob)) as archive:
            for member in archive.namelist():
                relative = member.split("/", 1)[1] if "/" in member else ""
                if relative.endswith(".csv") and (
                    relative.startswith("data/") or relative.startswith("labels/")
                ):
                    target = dest / key / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.read(member))
                elif relative in ("labels/combined_windows.json", "LICENSE", "LICENSE.txt"):
                    target = dest / key / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.read(member))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def series_files(root: Path = DATA_DIR) -> list[dict[str, str]]:
    """Every series the study can read, with its source group (fixed by the protocol)."""
    out: list[dict[str, str]] = []
    for sub in SKAB_DIRS:
        for path in sorted((root / "skab" / "data" / sub).glob("*.csv")):
            out.append(
                {
                    "id": f"skab/{sub}/{path.stem}",
                    "source": "skab",
                    "group": "skab",
                    "path": str(path.relative_to(root)),
                }
            )
    for family in [*NAB_FAMILIES, "realKnownCause"]:
        for path in sorted((root / "nab" / "data" / family).glob("*.csv")):
            group = (
                NAB_KNOWN_CAUSE[path.stem] if family == "realKnownCause" else NAB_FAMILIES[family]
            )
            out.append(
                {
                    "id": f"nab/{family}/{path.stem}",
                    "source": "nab",
                    "group": group,
                    "path": str(path.relative_to(root)),
                }
            )
    return out


def build_manifest(root: Path = DATA_DIR) -> dict[str, Any]:
    files = {f["path"]: digest(root / f["path"]) for f in series_files(root)}
    labels = root / "nab" / "labels" / "combined_windows.json"
    files[str(labels.relative_to(root))] = digest(labels)
    return {"sources": SOURCES, "files": dict(sorted(files.items()))}


def check_manifest(root: Path = DATA_DIR, manifest: Path = MANIFEST) -> list[str]:
    """Names of the files that are missing or whose hash differs from the manifest."""
    pinned = json.loads(manifest.read_text())["files"]
    return [
        name
        for name, sha in pinned.items()
        if not (root / name).exists() or digest(root / name) != sha
    ]


def window_labels(times: pd.Series, windows: list[list[str]]) -> np.ndarray:
    """1 for the rows whose time lies in a labelled window (both ends included)."""
    y = np.zeros(len(times), dtype=int)
    stamps = pd.to_datetime(times, utc=True)
    for start, end in windows:
        y[((stamps >= pd.Timestamp(start, tz="UTC")) & (stamps <= pd.Timestamp(end, tz="UTC"))).to_numpy()] = 1
    return y


def causal_features(values: pd.Series, window: int = WINDOW) -> pd.DataFrame:
    """Value, first difference, and deviation and spread over the previous ``window`` values."""
    past = values.shift(1).rolling(window)
    return pd.DataFrame(
        {
            "value": values,
            "diff": values.diff(),
            "deviation": values - past.mean(),
            "spread": past.std(),
        }
    )


def load_series(spec: dict[str, str], root: Path = DATA_DIR) -> dict[str, Any]:
    """Features, labels, times and facts of one series; rows are sorted by their timestamp."""
    path = root / spec["path"]
    if spec["source"] == "skab":
        frame = pd.read_csv(path, sep=";")
        times = pd.to_datetime(frame["datetime"], utc=True)
        y = frame["anomaly"].to_numpy().astype(int)
        frame = frame.drop(columns=["datetime", "anomaly", "changepoint"], errors="ignore")
        dropped = 0
    else:
        frame = pd.read_csv(path)
        times = pd.to_datetime(frame["timestamp"], utc=True)
        windows = json.loads((root / "nab" / "labels" / "combined_windows.json").read_text())
        y = window_labels(times, windows[spec["path"].split("nab/data/", 1)[1]])
        frame = frame[["value"]].astype(float)
        dropped = WINDOW
    in_order = bool(times.is_monotonic_increasing)
    order = np.argsort(times.to_numpy(), kind="stable")
    x, y = frame.iloc[order].reset_index(drop=True), y[order]
    times = times.iloc[order].reset_index(drop=True)
    if spec["source"] == "nab":  # features are causal in time order, so they follow the sort
        x = causal_features(x["value"])
    keep = np.arange(len(y)) >= dropped
    x, y, times = x[keep].reset_index(drop=True), y[keep], times[keep].reset_index(drop=True)
    x = x.loc[:, x.nunique() > 1]
    ok = x.notna().all(axis=1).to_numpy()
    return {
        "x": x[ok].reset_index(drop=True),
        "y": y[ok],
        "times": times[ok].reset_index(drop=True),
        "info": {
            "rows": int(ok.sum()),
            "rows_dropped": int((~ok).sum() + dropped),
            "file_in_time_order": in_order,
            "features": list(x.columns),
            "start": str(times.iloc[0]),
            "end": str(times.iloc[-1]),
        },
    }


def eligible(y: np.ndarray, times: pd.Series) -> tuple[bool, str]:
    """At least ``MIN_TEST`` anomalous and ``MIN_TEST`` normal rows in the last 15 % of the rows."""
    ok, reason = pc.eligible(y, times)
    if not ok:
        return ok, reason
    order = np.argsort(pd.to_datetime(times, utc=True).to_numpy(), kind="stable")
    test = np.asarray(y)[order][int(len(y) * 0.85) :]
    normal = int((test == 0).sum())
    if normal < MIN_TEST:
        return False, f"{normal} normal rows in the test partition (at least {MIN_TEST})"
    return True, ""


def run_series(spec: dict[str, str], root: Path = DATA_DIR) -> dict[str, Any]:
    """The chronological decision study of one series, or the reason it is not evaluated."""
    loaded = load_series(spec, root)
    head = {"id": spec["id"], "group": spec["group"], "source": spec["source"], **loaded["info"]}
    ok, reason = eligible(loaded["y"], loaded["times"])
    if not ok:
        return {**head, "excluded": reason}
    wanted = [*DETECTOR_NAMES, *DEEP_NAMES]
    run, skipped = pc.methods_for(int(len(loaded["y"]) * 0.70), wanted)
    result = td.run_frame(loaded["x"], loaded["y"], loaded["times"], methods=run, seeds=SEEDS, pi_floor=PI_FLOOR)
    return {**head, **result, "skipped": skipped}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DATA_DIR)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("fetch")
    commands.add_parser("manifest")
    commands.add_parser("list")
    one = commands.add_parser("run")
    one.add_argument("--id", required=True)
    one.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "fetch":
        fetch(args.data)
    elif args.command == "manifest":
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(json.dumps(build_manifest(args.data), indent=1, sort_keys=True) + "\n")
    elif args.command == "list":
        print("\n".join(s["id"] for s in series_files(args.data)))
    else:
        from etl_benchmark.atomic import atomic_path

        bad = check_manifest(args.data)
        if bad:
            raise SystemExit(f"files differ from the manifest: {bad[:3]}")
        spec = next(s for s in series_files(args.data) if s["id"] == args.id)
        result = run_series(spec, args.data)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with atomic_path(args.output) as partial:
            partial.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
        print(args.id, result.get("excluded", "ok"), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
