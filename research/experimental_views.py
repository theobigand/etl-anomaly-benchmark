"""Experimental views of acquired data: minimised, pseudonymised and deterministic (T434-T437).

A view keeps what the anomaly protocols need and drops personal or free-text fields. Pseudonyms are
salted hashes: they keep joins working, they do not make the data anonymous. Views are written to
``data/experimental`` (not committed); their checksums and parameters go in a tracked manifest.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

SALT = "etl-benchmark-views-v1"
_FREQ = {
    "hourly": "h",
    "daily": "D",
    "half_hourly": "30min",
    "monthly": "MS",
    "weekly": "W",
    "10_minutes": "10min",
}
#: report-level identifiers dropped from FAERS records
#: log columns kept when present: order, time, severity, native label and the event type
LOG_KEEP = ("LineId", "Label", "Timestamp", "Date", "Time", "Level", "EventId")
FAERS_DROP = ("companynumb", "authoritynumb")


def pseudonym(value: str | None, salt: str = SALT) -> str | None:
    if value is None:
        return None
    return hashlib.sha256(f"{salt}|{value}".encode()).hexdigest()[:16]


def _short(value: str | None) -> str | None:
    return None if value is None else value.rsplit("/", 1)[-1]


def openalex_views(
    works: list[dict[str, Any]],
    authors: list[dict[str, Any]],
    institutions: list[dict[str, Any]],
    sources: list[dict[str, Any]],
    salt: str = SALT,
) -> dict[str, pd.DataFrame]:
    """Five related tables; author ids are pseudonymised, names and ORCID iDs are dropped."""
    work_rows, ship_rows = [], []
    for w in works:
        source = (w.get("primary_location") or {}).get("source") or {}
        wid = _short(w["id"])
        ships = w.get("authorships", [])
        work_rows.append(
            {
                "work_id": wid,
                "year": w.get("publication_year"),
                "type": w.get("type"),
                "cited_by_count": w.get("cited_by_count"),
                "language": w.get("language"),
                "is_oa": (w.get("open_access") or {}).get("is_oa"),
                "source_id": _short(source.get("id")),
                "n_references": len(w.get("referenced_works", [])),
                "n_authors": len(ships),
            }
        )
        for s in ships:
            insts = s.get("institutions") or [{"id": None}]
            for i in insts:
                ship_rows.append(
                    {
                        "work_id": wid,
                        "author_id": pseudonym(_short(s["author"]["id"]), salt),
                        "institution_id": _short(i.get("id")),
                        "position": s.get("author_position"),
                    }
                )
    author_rows = [
        {
            "author_id": pseudonym(_short(a["id"]), salt),
            "works_count": a.get("works_count"),
            "cited_by_count": a.get("cited_by_count"),
        }
        for a in authors
    ]
    inst_rows = [
        {
            "institution_id": _short(i["id"]),
            "country_code": i.get("country_code"),
            "type": i.get("type"),
            "works_count": i.get("works_count"),
        }
        for i in institutions
    ]
    source_rows = [
        {
            "source_id": _short(s["id"]),
            "type": s.get("type"),
            "works_count": s.get("works_count"),
            "is_oa": s.get("is_oa"),
        }
        for s in sources
    ]
    return {
        "works": pd.DataFrame(work_rows),
        "authorships": pd.DataFrame(ship_rows),
        "authors": pd.DataFrame(author_rows),
        "institutions": pd.DataFrame(inst_rows),
        "sources": pd.DataFrame(source_rows),
    }


def tsf_wide(parsed: dict[str, Any]) -> pd.DataFrame:
    """Series as columns on one regular time index built from each start stamp and the frequency."""
    freq = _FREQ[parsed["frequency"]]
    columns = {}
    for s in parsed["series"]:
        start = pd.to_datetime(
            re.sub(r"(\d{4}-\d{2}-\d{2}) (\d{2})-(\d{2})-(\d{2})", r"\1 \2:\3:\4", s["start"])
        )
        index = pd.date_range(start, periods=len(s["values"]), freq=freq)
        columns[s["name"]] = pd.Series(s["values"], index=index, dtype="float64")
    return pd.DataFrame(columns).sort_index()


def faers_view(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Adverse-event reports without company and authority report numbers, in a fixed order."""
    kept = [{k: v for k, v in r.items() if k not in FAERS_DROP} for r in records]
    return sorted(kept, key=lambda r: (r.get("receivedate", ""), r["safetyreportid"]))


def loghub_view(frame: pd.DataFrame) -> pd.DataFrame:
    """Event sequence of a log: no message text or template, which can carry hosts and addresses."""
    keep = [c for c in LOG_KEEP if c in frame.columns]
    return frame[keep].copy()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_manifest(path: Path, entries: dict[str, Any]) -> None:
    from etl_benchmark.atomic import atomic_path

    with atomic_path(path) as partial:
        partial.write_text(json.dumps(entries, indent=1, sort_keys=True) + "\n")


def _results(raw: Path, prefix: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path in sorted(raw.glob(f"{prefix}_*.json")):
        out += json.loads(path.read_text())["results"]
    return out


def build(root: Path, out: Path) -> dict[str, Any]:
    """Write the four views and return their manifest (checksums, rows, dropped fields)."""
    import sys
    import zipfile

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import acquisition_validate as av

    manifest: dict[str, Any] = {}

    def record(view: str, files: dict[str, tuple[Path, int]], **facts: Any) -> None:
        manifest[view] = {
            "files": {n: {"sha256": digest(p), "rows": rows} for n, (p, rows) in files.items()},
            **facts,
        }

    snap = "2026-11-21"
    raw = root / "openalex_works" / snap / "raw"
    tables = openalex_views(
        _results(raw, "works"),
        _results(raw, "authors"),
        _results(raw, "institutions"),
        _results(raw, "sources"),
    )
    folder = out / "openalex"
    folder.mkdir(parents=True, exist_ok=True)
    files = {}
    for name, frame in tables.items():
        path = folder / f"{name}.csv"
        frame.sort_values(list(frame.columns)).to_csv(path, index=False)
        files[f"{name}.csv"] = (path, len(frame))
    record(
        "openalex",
        files,
        dropped=["display_name", "orcid", "observed_orcids", "raw works ids of authors"],
        pseudonymised=["author_id"],
        salt_label=SALT,
        source_snapshot=f"openalex_works/{snap}",
    )

    archive = root / "monash_zenodo" / snap / "raw" / "4656626_pedestrian_counts_dataset.zip"
    with zipfile.ZipFile(archive) as zf:
        member = next(n for n in zf.namelist() if n.endswith(".tsf"))
        wide = tsf_wide(av.read_tsf(zf.read(member).decode("utf-8", "replace")))
    folder = out / "monash_pedestrian"
    folder.mkdir(parents=True, exist_ok=True)
    wide.to_csv(folder / "wide.csv", index_label="timestamp")
    record(
        "monash_pedestrian",
        {"wide.csv": (folder / "wide.csv", len(wide))},
        dropped=[],
        pseudonymised=[],
        source_snapshot=f"monash_zenodo/{snap}",
    )

    pages = sorted((root / "openfda_drug_event" / snap / "raw").glob("event_*.json"))
    records = [r for p in pages for r in json.loads(p.read_text())["results"]]
    view = faers_view(records)
    folder = out / "openfda_drug_event"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "events.jsonl"
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in view))
    record(
        "openfda_drug_event",
        {"events.jsonl": (path, len(view))},
        dropped=list(FAERS_DROP),
        pseudonymised=[],
        source_snapshot=f"openfda_drug_event/{snap}",
    )

    folder = out / "loghub"
    folder.mkdir(parents=True, exist_ok=True)
    files = {}
    for source in sorted((root.parent / "loghub").glob("*.csv")):
        frame = loghub_view(pd.read_csv(source, dtype=str, keep_default_na=False))
        path = folder / source.name
        frame.to_csv(path, index=False)
        files[source.name] = (path, len(frame))
    record(
        "loghub",
        files,
        dropped=["Content", "EventTemplate"],
        pseudonymised=[],
        source_snapshot="loghub@dd61d09",
    )
    return manifest


def main(argv: list[str] | None = None) -> int:
    import argparse

    here = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=here / "data" / "acquired")
    parser.add_argument("--out", type=Path, default=here / "data" / "experimental")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=here / "verification/evidence/dataset_registry_v2/experimental_views.json",
    )
    args = parser.parse_args(argv)
    manifest = build(args.root, args.out)
    write_manifest(args.manifest, manifest)
    print({k: sum(f["rows"] for f in v["files"].values()) for k, v in manifest.items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
