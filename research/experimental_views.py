"""Experimental views of acquired data: minimised, pseudonymised and deterministic (T434-T437).

A view keeps what the anomaly protocols need and drops personal or free-text fields. Pseudonyms are
salted hashes: they keep joins working, they do not make the data anonymous. Views are written to
``data/experimental`` (not committed); their checksums and parameters go in a tracked manifest.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:  # sibling modules (acquisition, parquet_reader, ...) import by name
    sys.path.insert(0, str(_HERE))

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
    return None if value is None else value.rpartition("/")[2]


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


SPEND_COLUMNS = (
    "organisation",
    "date",
    "expense_type",
    "expense_area",
    "supplier_id",
    "transaction_no",
    "amount",
)
_SPEND_NAMES = {
    "date": ("date",),
    "expense_type": ("expense type",),
    "expense_area": ("expense area",),
    "supplier": ("supplier",),
    "transaction_no": ("transaction no", "transaction number"),
    "amount": ("amount",),
}


class ViewError(Exception):
    pass


def _find(columns: list[str], names: tuple[str, ...]) -> str | None:
    cleaned = {c: re.sub(r"[^a-z ]", "", c.lower()).strip() for c in columns}  # also drops a BOM
    for name in names:
        for original, clean in cleaned.items():
            if name in clean:
                return original
    return None


def _parse_dates(values: pd.Series) -> pd.Series:
    """ISO dates as written, every other format day-first; unreadable values become missing.

    ``dayfirst`` alone would turn an ISO date such as 2024-02-03 into 3 March, so ISO strings are
    parsed separately.
    """
    text = values.astype("string")
    iso = text.str.match(r"^\d{4}-\d{2}-\d{2}").fillna(False).to_numpy(dtype=bool)
    out = pd.Series(pd.NaT, index=values.index, dtype="datetime64[ns]")
    out[iso] = pd.to_datetime(text[iso], errors="coerce", format="ISO8601").to_numpy()
    out[~iso] = pd.to_datetime(
        text[~iso], errors="coerce", dayfirst=True, format="mixed"
    ).to_numpy()
    return out


def spend_view(raw: pd.DataFrame, organisation: str, salt: str = SALT) -> pd.DataFrame:
    """Public-spending transactions on one schema: suppliers pseudonymised, free text dropped."""
    columns = list(raw.columns)
    found = {k: _find(columns, v) for k, v in _SPEND_NAMES.items()}
    if not all(found[k] for k in ("date", "supplier", "amount", "transaction_no")):
        raise ViewError(f"required columns not found in {columns[:6]}")
    amount = pd.to_numeric(
        raw[found["amount"]].astype(str).str.replace(r"[£,\s]", "", regex=True), errors="coerce"
    )
    date = _parse_dates(raw[found["date"]])
    frame = pd.DataFrame(
        {
            "organisation": organisation,
            "date": date,
            "expense_type": raw[found["expense_type"]] if found["expense_type"] else None,
            "expense_area": raw[found["expense_area"]] if found["expense_area"] else None,
            "supplier_id": raw[found["supplier"]].map(
                lambda v: pseudonym(str(v).strip().lower(), salt) if pd.notna(v) else None
            ),
            "transaction_no": raw[found["transaction_no"]].astype(str),
            "amount": amount,
        }
    )
    return frame[amount.notna() & date.notna()].reset_index(drop=True)


def read_spend(blob: bytes) -> pd.DataFrame:
    """A spending CSV whose header is the first line mentioning a supplier (banners are skipped)."""
    import io

    if blob[:2] == b"PK":
        raise ViewError("a spreadsheet saved with a .csv name")
    try:
        text = blob.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = blob.decode("latin-1")
    lines = text.splitlines()
    start = next((i for i, line in enumerate(lines[:15]) if "supplier" in line.lower()), None)
    if start is None:
        raise ViewError("no header line with a supplier column in the first 15 lines")
    return pd.read_csv(io.StringIO("\n".join(lines[start:])), dtype=str, on_bad_lines="skip")


#: contributor keys of Open Food Facts records, dropped at every depth
OFF_DROP = frozenset(
    [
        "creator",
        "last_editor",
        "editors",
        "editors_tags",
        "correctors",
        "correctors_tags",
        "checkers",
        "checkers_tags",
        "photographers",
        "photographers_tags",
        "informers",
        "informers_tags",
        "owner",
        "owners_tags",
        "owner_fields",
        "owner_imported",
        "uploader",
    ]
)


def _strip(value: Any, drop: frozenset[str]) -> Any:
    if isinstance(value, dict):
        return {k: _strip(v, drop) for k, v in value.items() if k not in drop}
    if isinstance(value, list):
        return [_strip(v, drop) for v in value]
    return value


def off_view(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Product records without contributor fields, nested structure kept, in a fixed order."""
    return sorted((_strip(r, OFF_DROP) for r in records), key=lambda r: str(r["_id"]))


_STACK = {
    "Users": ("user_id", ["Id", "Reputation", "CreationDate", "Views", "UpVotes", "DownVotes"]),
    "Posts": (
        "post_id",
        ["Id", "PostTypeId", "ParentId", "AcceptedAnswerId", "CreationDate", "Score", "ViewCount"]
        + ["AnswerCount", "CommentCount", "Tags", "OwnerUserId"],
    ),
    "Comments": ("comment_id", ["Id", "PostId", "UserId", "Score", "CreationDate"]),
    "Votes": ("vote_id", ["Id", "PostId", "VoteTypeId", "CreationDate"]),
    "Badges": ("badge_id", ["Id", "UserId", "Name", "Date", "Class"]),
    "PostLinks": ("link_id", ["Id", "PostId", "RelatedPostId", "LinkTypeId", "CreationDate"]),
}


def _snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def stack_views(
    tables: dict[str, list[dict[str, str]]], salt: str = SALT
) -> dict[str, pd.DataFrame]:
    """Stack Exchange tables without titles, bodies, comment text, names, locations or profiles.

    Every user reference (user ids, post owners, comment authors, badge holders) goes through one
    pseudonym mapping, so links resolve exactly as in the source: a missing user stays missing.
    """
    out = {}
    for table, (key, columns) in _STACK.items():
        rows = []
        for row in tables.get(table, []):
            kept = {}
            for column in columns:
                value = row.get(column)
                user_ref = (table == "Users" and column == "Id") or column in (
                    "OwnerUserId",
                    "UserId",
                )
                kept[_snake(column)] = pseudonym(value, salt) if user_ref else value
            rows.append(kept)
        frame = pd.DataFrame(rows, columns=[_snake(c) for c in columns])
        frame = frame.rename(columns={"id": key})
        out[table] = frame
    return out


AWARD_COLUMNS = (
    "ocid",
    "award_id",
    "date",
    "amount",
    "currency",
    "supplier_id",
    "buyer_id",
    "method",
)
CONTRACT_COLUMNS = ("ocid", "contract_id", "award_id", "date_signed", "amount", "currency")
#: OCDS keys that carry names, contact data or free text, dropped at every depth
OCDS_DROP = frozenset(
    [
        "name",
        "address",
        "contactPoint",
        "description",
        "legalName",
        "identifier",
        "title",
        "documents",
    ]
)


def _ocds_ids(node: Any) -> Any:
    """Drop the identifying keys (names, addresses, free text) at every depth."""
    if isinstance(node, dict):
        return {k: _ocds_ids(v) for k, v in node.items() if k not in OCDS_DROP}
    if isinstance(node, list):
        return [_ocds_ids(v) for v in node]
    return node


def _ocds_party(entry: dict[str, Any], salt: str) -> dict[str, Any]:
    out = dict(entry)
    if out.get("id"):
        out["id"] = pseudonym(str(out["id"]), salt)
    return out


def ocds_view(
    releases: list[dict[str, Any]], salt: str = SALT, keep_modulo: int = 10
) -> tuple[list[dict[str, Any]], pd.DataFrame, pd.DataFrame]:
    """Compiled OCDS releases without names or free text, a flat awards table and a contracts table.

    A contract is kept when a stable hash of its ``ocid`` is 0 modulo ``keep_modulo``, so whole
    contracts stay together; party references use one pseudonym mapping so that links resolve.
    """
    kept, rows, contract_rows = [], [], []
    for release in releases:
        h = int(hashlib.sha256(release["ocid"].encode()).hexdigest()[:8], 16)
        if h % keep_modulo:
            continue
        r = _ocds_ids(release)
        if "buyer" in r:
            r["buyer"] = _ocds_party(r["buyer"], salt)
        r["parties"] = [_ocds_party(p, salt) for p in r.get("parties", [])]
        for a in r.get("awards", []):
            a["suppliers"] = [_ocds_party(x, salt) for x in a.get("suppliers", [])]
        entity = (r.get("tender") or {}).get("procuringEntity")
        if entity:
            r["tender"]["procuringEntity"] = _ocds_party(entity, salt)
        kept.append(r)
        for a in r.get("awards", []):
            value = a.get("value") or {}
            rows.append(
                {
                    "ocid": r["ocid"],
                    "award_id": a.get("id"),
                    "date": a.get("date") or r.get("date"),
                    "amount": value.get("amount"),
                    "currency": value.get("currency"),
                    "supplier_id": (a.get("suppliers") or [{}])[0].get("id"),
                    "buyer_id": (r.get("buyer") or {}).get("id"),
                    "method": (r.get("tender") or {}).get("procurementMethod"),
                }
            )
        for c in r.get("contracts", []):
            value = c.get("value") or {}
            contract_rows.append(
                {
                    "ocid": r["ocid"],
                    "contract_id": c.get("id"),
                    "award_id": c.get("awardID"),
                    "date_signed": c.get("dateSigned"),
                    "amount": value.get("amount"),
                    "currency": value.get("currency"),
                }
            )
    kept.sort(key=lambda r: (r["date"], r["id"]))
    awards = pd.DataFrame(rows, columns=list(AWARD_COLUMNS))
    contracts = pd.DataFrame(contract_rows, columns=list(CONTRACT_COLUMNS))
    return kept, awards, contracts


TRIP_COLUMNS = (
    "ride_id",
    "rideable_type",
    "started_at",
    "ended_at",
    "duration_min",
    "start_station_id",
    "end_station_id",
    "member_casual",
)


def trip_view(raw: pd.DataFrame) -> pd.DataFrame:
    """Bike-share trips without names or coordinates; impossible durations stay visible."""
    needed = ["ride_id", "started_at", "ended_at", "start_station_id", "end_station_id"]
    if not all(c in raw.columns for c in needed):
        raise ViewError(f"trip columns not found in {list(raw.columns)[:6]}")
    start = pd.to_datetime(raw["started_at"], errors="coerce")
    end = pd.to_datetime(raw["ended_at"], errors="coerce")
    frame = pd.DataFrame(
        {
            "ride_id": raw["ride_id"],
            "rideable_type": raw.get("rideable_type"),
            "started_at": start,
            "ended_at": end,
            "duration_min": (end - start).dt.total_seconds() / 60.0,
            "start_station_id": raw["start_station_id"],
            "end_station_id": raw["end_station_id"],
            "member_casual": raw.get("member_casual"),
        }
    )
    return frame[list(TRIP_COLUMNS)]


def csv_members(names: list[str]) -> list[str]:
    """CSV members of an archive, without macOS resource-fork files that carry a .csv name."""
    keep = []
    for name in names:
        parts = name.split("/")
        if name.endswith(".csv") and parts[0] != "__MACOSX" and not parts[-1].startswith("._"):
            keep.append(name)
    return sorted(keep)


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


def _ocds_source(path: Path) -> tuple[list[dict[str, Any]], pd.DataFrame, pd.DataFrame]:
    """Stream one registry export through ``ocds_view`` in batches (whole file never in memory)."""
    import gzip

    nested: list[dict[str, Any]] = []
    awards, contracts = [], []
    batch: list[dict[str, Any]] = []

    def flush() -> None:
        kept, a, c = ocds_view(batch)
        nested.extend(kept)
        awards.append(a)
        contracts.append(c)
        batch.clear()

    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            batch.append(json.loads(line))
            if len(batch) == 20000:
                flush()
    flush()
    nested.sort(key=lambda r: (r["date"], r["id"]))
    order = ["date", "ocid", "award_id"]
    awards_frame = pd.concat(awards).sort_values(order)
    contracts_frame = pd.concat(contracts).sort_values(["ocid", "contract_id"])
    return nested, awards_frame, contracts_frame


SNAPSHOT = "2026-11-21"


def _record(
    manifest: dict[str, Any], view: str, files: dict[str, tuple[Path, int]], **facts: Any
) -> None:
    """Add one view to the manifest: a checksum and a row count per written file, then the facts."""
    manifest[view] = {
        "files": {n: {"sha256": digest(p), "rows": rows} for n, (p, rows) in files.items()},
        **facts,
    }


def _build_openalex(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    raw = root / "openalex_works" / SNAPSHOT / "raw"
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
    _record(
        manifest,
        "openalex",
        files,
        dropped=["display_name", "orcid", "observed_orcids", "raw works ids of authors"],
        pseudonymised=["author_id"],
        salt_label=SALT,
        source_snapshot=f"openalex_works/{SNAPSHOT}",
    )


def _build_monash(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    import zipfile

    import acquisition_validate as av

    archive = root / "monash_zenodo" / SNAPSHOT / "raw" / "4656626_pedestrian_counts_dataset.zip"
    with zipfile.ZipFile(archive) as zf:
        member = next(n for n in zf.namelist() if n.endswith(".tsf"))
        wide = tsf_wide(av.read_tsf(zf.read(member).decode("utf-8", "replace")))
    folder = out / "monash_pedestrian"
    folder.mkdir(parents=True, exist_ok=True)
    wide.to_csv(folder / "wide.csv", index_label="timestamp")
    _record(
        manifest,
        "monash_pedestrian",
        {"wide.csv": (folder / "wide.csv", len(wide))},
        dropped=[],
        pseudonymised=[],
        source_snapshot=f"monash_zenodo/{SNAPSHOT}",
    )


def _build_faers(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    pages = sorted((root / "openfda_drug_event" / SNAPSHOT / "raw").glob("event_*.json"))
    records = [r for p in pages for r in json.loads(p.read_text())["results"]]
    view = faers_view(records)
    folder = out / "openfda_drug_event"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "events.jsonl"
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in view))
    _record(
        manifest,
        "openfda_drug_event",
        {"events.jsonl": (path, len(view))},
        dropped=list(FAERS_DROP),
        pseudonymised=[],
        source_snapshot=f"openfda_drug_event/{SNAPSHOT}",
    )


def _build_loghub(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    folder = out / "loghub"
    folder.mkdir(parents=True, exist_ok=True)
    files = {}
    for source in sorted((root.parent / "loghub").glob("*.csv")):
        frame = loghub_view(pd.read_csv(source, dtype=str, keep_default_na=False))
        path = folder / source.name
        frame.to_csv(path, index=False)
        files[source.name] = (path, len(frame))
    _record(
        manifest,
        "loghub",
        files,
        dropped=["Content", "EventTemplate"],
        pseudonymised=[],
        source_snapshot="loghub@dd61d09",
    )


def _build_food(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    import gzip

    path = next((root / "openfoodfacts_products" / SNAPSHOT / "raw").glob("*.gz"))
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        products = off_view([json.loads(line) for line in handle if line.strip()])
    folder = out / "openfoodfacts"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "products.jsonl"
    target.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in products))
    _record(
        manifest,
        "openfoodfacts",
        {"products.jsonl": (target, len(products))},
        dropped=sorted(OFF_DROP),
        pseudonymised=[],
        source_snapshot=f"openfoodfacts_products/{SNAPSHOT}",
    )


def _build_stack(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    import subprocess
    import tempfile
    import xml.etree.ElementTree as ET

    files = {}
    for archive in sorted((root / "stackexchange_dump" / SNAPSHOT / "raw").glob("*.7z")):
        site = archive.name.split(".")[0]
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["bsdtar", "-xf", str(archive), "-C", tmp], check=True)  # noqa: S603, S607
            tables = {
                p.stem: [dict(e.attrib) for e in ET.parse(p).getroot()]
                for p in Path(tmp).glob("*.xml")
            }
        folder = out / "stackexchange" / site
        folder.mkdir(parents=True, exist_ok=True)
        for name, frame in stack_views(tables).items():
            target = folder / f"{name}.csv"
            frame.to_csv(target, index=False)
            files[f"{site}/{name}.csv"] = (target, len(frame))
    _record(
        manifest,
        "stackexchange",
        files,
        dropped=[
            "Title",
            "Body",
            "Text",
            "DisplayName",
            "Location",
            "AboutMe",
            "WebsiteUrl",
            "profile fields",
        ],
        pseudonymised=["user_id", "owner_user_id"],
        salt_label=SALT,
        source_snapshot=f"stackexchange_dump/{SNAPSHOT}",
        notes="CC BY-SA: a redistributed derived database needs attribution and the same licence",
    )


def _build_ocds(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    for source in ("ocds_montreal", "ocds_georgia", "ocds_zambia"):
        nested, awards, contracts = _ocds_source(root / source / SNAPSHOT / "raw" / "full.jsonl.gz")
        folder = out / source
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "releases.jsonl").write_text(
            "".join(json.dumps(r, sort_keys=True) + "\n" for r in nested)
        )
        awards.to_csv(folder / "awards.csv", index=False)
        contracts.to_csv(folder / "contracts.csv", index=False)
        _record(
            manifest,
            source,
            {
                "releases.jsonl": (folder / "releases.jsonl", len(nested)),
                "awards.csv": (folder / "awards.csv", len(awards)),
                "contracts.csv": (folder / "contracts.csv", len(contracts)),
            },
            dropped=sorted(OCDS_DROP),
            pseudonymised=["party ids"],
            salt_label=SALT,
            sampling="contracting processes with sha256(ocid) % 10 == 0, whole processes, by date",
            source_snapshot=f"{source}/{SNAPSHOT}",
        )


def _build_bikeshare(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    import io
    import zipfile

    for source in ("bikeshare_capital", "bikeshare_jc"):
        frames = []
        for path in sorted((root / source / SNAPSHOT / "raw").glob("*.zip")):
            with zipfile.ZipFile(path) as zf:
                for member in csv_members(zf.namelist()):
                    raw = pd.read_csv(
                        io.BytesIO(zf.read(member)), dtype=str, encoding_errors="replace"
                    )
                    frames.append(trip_view(raw))
        table = pd.concat(frames).sort_values(["started_at", "ride_id"])
        folder = out / source
        folder.mkdir(parents=True, exist_ok=True)
        table.to_csv(folder / "trips.csv", index=False)
        _record(
            manifest,
            source,
            {"trips.csv": (folder / "trips.csv", len(table))},
            dropped=["station names", "start and end coordinates"],
            pseudonymised=[],
            source_snapshot=f"{source}/{SNAPSHOT}",
        )


def _build_ukspend(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    folder = out / "ukspend"
    folder.mkdir(parents=True, exist_ok=True)
    files, skipped = {}, {}
    for org in ("mhra", "nhsbsa", "charity_commission", "ofsted", "nice"):
        frames = []
        for path in sorted((root / f"ukspend_{org}" / SNAPSHOT / "raw").glob("*.csv")):
            try:
                frames.append(spend_view(read_spend(path.read_bytes()), org))
            except ViewError as error:
                skipped.setdefault(org, []).append(f"{path.name}: {error}")
        if frames:
            table = pd.concat(frames).sort_values(["date", "transaction_no", "supplier_id"])
            target = folder / f"{org}.csv"
            table.to_csv(target, index=False)
            files[f"{org}.csv"] = (target, len(table))
    _record(
        manifest,
        "ukspend",
        files,
        dropped=[
            "Description",
            "post code",
            "supplier type",
            "VAT number",
            "contract and project codes",
        ],
        pseudonymised=["supplier_id"],
        salt_label=SALT,
        source_snapshot=f"ukspend_*/{SNAPSHOT}",
        skipped=skipped,
    )


def nested_view(
    records: list[dict[str, Any]], drop: frozenset[str], key: Any
) -> list[dict[str, Any]]:
    """Records without the named keys at every depth, in a fixed order; the input is untouched."""
    return sorted((_strip(r, drop) for r in records), key=key)


#: person and contact keys of ClinicalTrials.gov study records, dropped at every depth
CT_DROP = frozenset(
    [
        "centralContacts",
        "overallOfficials",
        "pointOfContact",
        "contacts",
        "investigatorFullName",
        "investigatorTitle",
        "investigatorAffiliation",
    ]
)


_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def redact_emails(node: Any) -> Any:
    """The same structure with every e-mail address inside a string replaced by ``[email]``."""
    if isinstance(node, dict):
        return {k: redact_emails(v) for k, v in node.items()}
    if isinstance(node, list):
        return [redact_emails(v) for v in node]
    if isinstance(node, str):
        return _EMAIL.sub("[email]", node)
    return node


def clinical_trials_view(studies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Study records without investigators, officials and contacts; addresses in text redacted."""
    kept = nested_view(
        studies, CT_DROP, lambda s: s["protocolSection"]["identificationModule"]["nctId"]
    )
    return [redact_emails(s) for s in kept]


def crossref_view(works: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One record per DOI, authors (names, ORCID iDs, affiliations) replaced by their number."""
    unique = {}
    for work in works:
        unique.setdefault(work["DOI"], work)
    out = []
    for work in nested_view(list(unique.values()), frozenset(["author"]), lambda w: w["DOI"]):
        out.append({**work, "n_authors": len(unique[work["DOI"]].get("author", []))})
    return out


def _build_clinicaltrials(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    studies: list[dict[str, Any]] = []
    for path in sorted((root / "clinicaltrials_v2" / SNAPSHOT / "raw").glob("studies_*.json")):
        studies += json.loads(path.read_text())["studies"]
    view = clinical_trials_view(studies)
    folder = out / "clinicaltrials_v2"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "studies.jsonl"
    target.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in view))
    _record(
        manifest,
        "clinicaltrials_v2",
        {"studies.jsonl": (target, len(view))},
        dropped=sorted(CT_DROP),
        pseudonymised=[],
        source_snapshot=f"clinicaltrials_v2/{SNAPSHOT}",
    )


def _build_crossref(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    works: list[dict[str, Any]] = []
    for path in sorted((root / "crossref_works" / SNAPSHOT / "raw").glob("sample_*.json")):
        works += json.loads(path.read_text())["message"]["items"]
    view = crossref_view(works)
    folder = out / "crossref_works"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "works.jsonl"
    target.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in view))
    _record(
        manifest,
        "crossref_works",
        {"works.jsonl": (target, len(view))},
        dropped=["author"],
        pseudonymised=[],
        source_snapshot=f"crossref_works/{SNAPSHOT}",
        notes="authors are replaced by their count; one record per DOI",
    )


#: time-series tables of the pools: the file folder, the time column(s) and their exact format
SERIES_SPECS: dict[str, dict[str, Any]] = {
    "uci:357": {"dir": "pool", "time": ["date"], "format": "%Y-%m-%d %H:%M:%S"},
    "uci:360": {"dir": "pool", "time": ["Date", "Time"], "format": "%m/%d/%Y %H:%M:%S"},
    "uci:374": {"dir": "pool", "time": ["date"], "format": "%Y-%m-%d%H:%M:%S"},
    "uci:560": {"dir": "pool", "time": ["Date"], "format": "%d/%m/%Y", "hour": "Hour"},
    "uci:799": {"dir": "pool", "time": ["timestamp"], "format": "ISO8601"},
    "uci:849": {"dir": "pool", "time": ["DateTime"], "format": "%m/%d/%Y %H:%M"},
    "uci:851": {"dir": "pool", "time": ["date"], "format": "%d/%m/%Y %H:%M"},
    "uci:172": {"dir": "uci_wave2", "time": ["Date"], "format": "%m/%d/%Y"},
    "uci:492": {"dir": "uci_wave2", "time": ["date_time"], "format": "%Y-%m-%d %H:%M:%S"},
}


def _stamped(raw: pd.DataFrame, spec: dict[str, Any]) -> tuple[pd.DataFrame, pd.Series, set[str]]:
    """The table with clean column names, its parsed timestamps and the columns they came from."""
    frame = raw.rename(columns=lambda c: str(c).lstrip("\ufeff"))
    if not all(c in frame.columns for c in spec["time"]):
        raise ViewError(f"time column not found in {list(frame.columns)[:6]}")
    joined = frame[spec["time"]].astype(str).agg(" ".join, axis=1)
    stamps = pd.to_datetime(joined, format=spec["format"], errors="coerce")
    hour = spec.get("hour")
    if hour:
        stamps = stamps + pd.to_timedelta(pd.to_numeric(frame[hour], errors="coerce"), unit="h")
    return frame, stamps, {*spec["time"], *([hour] if hour else [])}


def panel_view(raw: pd.DataFrame, spec: dict[str, Any]) -> pd.DataFrame:
    """Many series in one table: a timestamp, the key columns and the numeric columns, ordered by
    key then time. Rows with an unreadable time are dropped and counted, never guessed."""
    frame, stamps, used = _stamped(raw, spec)
    keys = spec["keys"]
    if not all(k in frame.columns for k in keys):
        raise ViewError(f"key column not found in {list(frame.columns)[:6]}")
    numeric = {
        c: pd.to_numeric(frame[c], errors="coerce")
        for c in frame.columns
        if c not in used
        and c not in keys
        and pd.to_numeric(frame[c], errors="coerce").notna().any()  # noqa: E501
    }
    out = pd.DataFrame({"timestamp": stamps, **{k: frame[k] for k in keys}, **numeric})
    kept = out[out["timestamp"].notna()].sort_values([*keys, "timestamp"], kind="stable")
    kept = kept.reset_index(drop=True)
    kept.attrs = {"rows_dropped": int(len(out) - len(kept))}
    return kept


def tables_view(
    tables: dict[str, pd.DataFrame], spec: dict[str, Any]
) -> tuple[dict[str, pd.DataFrame], list[dict[str, Any]]]:
    """Listed columns of each table and, for each declared key relation, its orphan count.

    A relation is (child table, child column, parent table, parent column); missing child keys
    are not counted. A relation may carry ``{"where": [column, value]}`` to check only the child
    rows of one kind (a key that points to different parents by row type). Orphans are reported,
    never removed.
    """
    out = {}
    for name, rule in spec["tables"].items():
        if name not in tables:
            raise ViewError(f"table {name} not found")
        missing = [c for c in rule["keep"] if c not in tables[name].columns]
        if missing:
            raise ViewError(f"column {missing[0]} not found in table {name}")
        out[name] = tables[name][rule["keep"]].copy()
    relations = []
    for child, child_col, parent, parent_col, *options in spec["relations"]:
        rows = out[child]
        where = options[0]["where"] if options else None
        if where:
            rows = rows[rows[where[0]] == where[1]]
        values = rows[child_col].dropna()
        values = values[values != ""]  # a blank key is a missing key, not a dangling one
        known = set(out[parent][parent_col].dropna()) - {""}
        bad = int((~values.isin(known)).sum())
        relations.append(
            {
                "child": f"{child}.{child_col}"
                + (f" where {where[0]}={where[1]}" if where else ""),
                "parent": f"{parent}.{parent_col}",
                "checked": len(values),
                "orphans": bad,
                "share": bad / len(values) if len(values) else 0.0,
            }
        )
    return out, relations


#: panels of series: the raw file of an acquired source and how to read its time and key columns
PANEL_SPECS: dict[str, dict[str, Any]] = {
    "rki_notaufnahme": {
        "source": "zen_rki_notaufnahme",
        "file": "Notaufnahmesurveillance_Zeitreihen_Syndrome.tsv",
        "sep": "\t",
        "time": ["date"],
        "format": "%Y-%m-%d",
        "keys": ["ed_type", "age_group", "syndrome"],
    },
    "rki_hospitalisation": {
        "source": "zen_rki_hospitalisation",
        "file": "Aktuell_Deutschland_COVID-19-Hospitalisierungen.csv",
        "sep": ",",
        "time": ["Datum"],
        "format": "%Y-%m-%d",
        "keys": ["Bundesland", "Altersgruppe"],
    },
}

#: multi-table relational extracts: the columns kept per table and the relations to measure
TABLE_SETS: dict[str, dict[str, Any]] = {
    "zen_3pfl": {
        "dropped": [
            "names, street addresses, phone numbers, free-text descriptions",
            "patent information table (fields derived from PATSTAT)",
        ],
        "tables": {
            "01_patent_contract": {
                "keep": ["patent_contract_id", "piid", "patent", "contract", "grant"]
            },  # noqa: E501
            "02_procurement_information": {
                "keep": [
                    "piid",
                    "maj_agency_cat",
                    "dunsnumber",
                    "typeofcontractpricing",
                    "extentcompeted",
                    "numberofoffersreceived",
                    "first_signed_date",
                ]  # noqa: E501
            },
            "03_procurement_year": {
                "keep": ["piid", "fiscal_year", "total_amount", "nr_of_transactions"]
            },  # noqa: E501
            "04_vendor_information": {
                "keep": ["dunsnumber", "state", "organizational_type", "receive_grants"]
            },
            "05_grant_information": {
                "keep": [
                    "piid",
                    "maj_agency_cat",
                    "duns_no",
                    "assistance_type",
                    "start_date",
                    "end_date",
                    "principal_place_state",
                ],
                "strip": '"; ',
            },
            "06_grant_year": {
                "keep": ["piid", "fiscal_year", "total_amount", "non_federal", "nr_of_transactions"]
            },
            "07_grantee_information": {
                "keep": ["dunsnumber", "recipient_state_code", "recip_cat_type", "receive_contract"]
            },
        },
        "relations": [
            [
                "01_patent_contract",
                "piid",
                "02_procurement_information",
                "piid",
                {"where": ["contract", "1"]},
            ],
            [
                "01_patent_contract",
                "piid",
                "05_grant_information",
                "piid",
                {"where": ["grant", "1"]},
            ],
            ["02_procurement_information", "dunsnumber", "04_vendor_information", "dunsnumber"],
            ["05_grant_information", "duns_no", "07_grantee_information", "dunsnumber"],
            ["06_grant_year", "piid", "05_grant_information", "piid"],
            ["03_procurement_year", "piid", "02_procurement_information", "piid"],
        ],
    },
    "grouplens_movielens": {
        "archive": {"file": "ml-latest-small.zip", "prefix": "ml-latest-small/"},
        "sep": ",",
        "quote_none": False,
        "dropped": [
            "free-text tags",
            "movie titles are kept; users are ids only (no demographics)",
        ],
        "tables": {
            "movies": {"keep": ["movieId", "genres"]},
            "ratings": {"keep": ["userId", "movieId", "rating", "timestamp"]},
            "tags": {"keep": ["userId", "movieId", "timestamp"]},
            "links": {"keep": ["movieId"]},
        },
        "relations": [
            ["ratings", "movieId", "movies", "movieId"],
            ["tags", "movieId", "movies", "movieId"],
            ["links", "movieId", "movies", "movieId"],
            ["tags", "userId", "ratings", "userId"],
        ],
    },
}


#: GTFS timetable feeds of French public transport networks (national access point, open licences)
GTFS_FEEDS: dict[str, str] = {
    "gtfs_fr_citea": "gtfs-nov2026-juin2027-citea.zip",
    "gtfs_fr_palmbus": "palmbus-cannes-fr.zip",
    "gtfs_fr_kiceo": "gtfs-20261121-112920-kiceo.zip",
    "gtfs_fr_diviamobilites": "gtfs-diviamobilites-current.zip",
    "gtfs_fr_sankeo": "gtfssankeo.zip",
    "gtfs_fr_alterneo": "gtfs-cineo-20260825-20270825.zip",
    "gtfs_fr_transvilles": "google-transit.zip",
    "gtfs_fr_tango": "gtfs-production.zip",
    "gtfs_fr_filibus": "gtfs-filibus-20260919-20270702.zip",
    "gtfs_fr_sibra": "gtfs-sibra.zip",
    "gtfs_fr_aravis": "export-gtfs-aravis-hiver-2026-hiver20252026.zip",
    "gtfs_fr_optymo": "gtfs.zip",
}


def _gtfs_spec(archive: str) -> dict[str, Any]:
    """Tables and key relations of a GTFS feed: names, coordinates and fares are not kept."""
    return {
        "archive": {"file": archive, "prefix": "", "ext": ".txt"},
        "sep": ",",
        "quote_none": False,
        "dropped": ["stop and route names", "coordinates", "shapes", "fares", "free text"],
        "tables": {
            "routes": {"keep": ["route_id", "route_type"]},
            "trips": {"keep": ["trip_id", "route_id", "service_id"]},
            "stop_times": {"keep": ["trip_id", "stop_id", "stop_sequence"]},
            "stops": {"keep": ["stop_id"]},
            "calendar_dates": {"keep": ["service_id", "date", "exception_type"], "optional": True},
        },
        "relations": [
            ["trips", "route_id", "routes", "route_id"],
            ["stop_times", "trip_id", "trips", "trip_id"],
            ["stop_times", "stop_id", "stops", "stop_id"],
        ],
    }


TABLE_SETS.update({source: _gtfs_spec(name) for source, name in GTFS_FEEDS.items()})


#: de-identified clinical demo databases from PhysioNet (ODbL): tables kept and key relations
CLINICAL_TABLE_SETS: dict[str, dict[str, Any]] = {
    "physionet_mimic_iv_demo": {
        "ext": ".csv.gz",
        "sep": ",",
        "quote_none": False,
        "dropped": ["free-text comments", "provider ids", "marital status, language, race, insurance"],  # noqa: E501
        "tables": {
            "hosp_patients": {
                "keep": ["subject_id", "gender", "anchor_age", "anchor_year_group"],
                "pseudonymise": ["subject_id"],
            },
            "hosp_admissions": {
                "keep": ["subject_id", "hadm_id", "admittime", "dischtime", "admission_type",
                         "hospital_expire_flag"],
                "pseudonymise": ["subject_id"],
            },
            "hosp_diagnoses_icd": {
                "keep": ["subject_id", "hadm_id", "seq_num", "icd_code", "icd_version"],
                "pseudonymise": ["subject_id"],
            },
            "hosp_labevents": {
                "keep": ["labevent_id", "subject_id", "hadm_id", "itemid", "charttime", "valuenum", "flag"],  # noqa: E501
                "pseudonymise": ["subject_id"],
            },
            "hosp_d_labitems": {"keep": ["itemid", "fluid", "category"]},
            "icu_icustays": {
                "keep": ["subject_id", "hadm_id", "stay_id", "first_careunit", "last_careunit", "intime",  # noqa: E501
                         "outtime", "los"],
                "pseudonymise": ["subject_id"],
            },
        },
        "relations": [
            ["hosp_admissions", "subject_id", "hosp_patients", "subject_id"],
            ["hosp_diagnoses_icd", "hadm_id", "hosp_admissions", "hadm_id"],
            ["hosp_labevents", "hadm_id", "hosp_admissions", "hadm_id"],
            ["hosp_labevents", "itemid", "hosp_d_labitems", "itemid"],
            ["icu_icustays", "hadm_id", "hosp_admissions", "hadm_id"],
            ["icu_icustays", "subject_id", "hosp_patients", "subject_id"],
        ],
    },
    "physionet_eicu_demo": {
        "ext": ".csv.gz",
        "sep": ",",
        "quote_none": False,
        "dropped": ["free-text diagnosis and treatment strings", "ward ids", "admission diagnosis text"],  # noqa: E501
        "tables": {
            "patient": {
                "keep": ["patientunitstayid", "patienthealthsystemstayid", "gender", "age", "hospitalid",  # noqa: E501
                         "unittype", "unitdischargestatus", "hospitaldischargestatus"],
            },
            "hospital": {"keep": ["hospitalid", "numbedscategory", "teachingstatus", "region"]},
            "diagnosis": {"keep": ["diagnosisid", "patientunitstayid", "activeupondischarge",
                                   "diagnosisoffset", "icd9code"]},
            "lab": {"keep": ["labid", "patientunitstayid", "labresultoffset", "labname", "labresult"]},  # noqa: E501
            "medication": {"keep": ["medicationid", "patientunitstayid", "drugstartoffset", "drugname",  # noqa: E501
                                    "routeadmin"]},
            "treatment": {"keep": ["treatmentid", "patientunitstayid", "treatmentoffset"]},
        },
        "relations": [
            ["patient", "hospitalid", "hospital", "hospitalid"],
            ["diagnosis", "patientunitstayid", "patient", "patientunitstayid"],
            ["lab", "patientunitstayid", "patient", "patientunitstayid"],
            ["medication", "patientunitstayid", "patient", "patientunitstayid"],
            ["treatment", "patientunitstayid", "patient", "patientunitstayid"],
        ],
    },
}  # fmt: skip
TABLE_SETS.update(CLINICAL_TABLE_SETS)


def _build_panels(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    folder = out / "panels"
    folder.mkdir(parents=True, exist_ok=True)
    files, dropped = {}, {}
    for name, spec in PANEL_SPECS.items():
        raw = pd.read_csv(
            root / spec["source"] / SNAPSHOT / "raw" / spec["file"],
            sep=spec["sep"],
            dtype=str,
            low_memory=False,
        )
        view = panel_view(raw, spec)
        target = folder / f"{name}.csv"
        view.to_csv(target, index=False)
        files[target.name] = (target, len(view))
        dropped[name] = view.attrs["rows_dropped"]
    _record(
        manifest,
        "panels",
        files,
        dropped=[],
        pseudonymised=[],
        rows_dropped=dropped,
        source_snapshot="zen_rki_* records of 2026-11-21 (the series are revised by the publisher)",
    )


def _build_tables(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    import csv
    import tempfile

    from acquisition import extract_member, zip_members

    for source, spec in TABLE_SETS.items():
        raw = root / source / SNAPSHOT / "raw"
        tables, absent, pseudonymised = {}, [], []
        with tempfile.TemporaryDirectory() as scratch:
            members = (
                {m["name"] for m in zip_members(raw / spec["archive"]["file"])}
                if "archive" in spec
                else set()
            )
            for name in spec["tables"]:
                if "archive" in spec:  # tables are members of a zip archive
                    member = (
                        f"{spec['archive']['prefix']}{name}{spec['archive'].get('ext', '.csv')}"
                    )
                    if member not in members and spec["tables"][name].get("optional"):
                        absent.append(name)
                        continue
                    path = extract_member(
                        raw / spec["archive"]["file"], member, Path(scratch), 1 << 30, 200
                    )["path"]
                else:
                    path = raw / f"{name}{spec.get('ext', '.csv')}"
                frame = pd.read_csv(
                    path,
                    sep=spec.get("sep", "\t"),
                    dtype=str,
                    quoting=csv.QUOTE_NONE if spec.get("quote_none", True) else csv.QUOTE_MINIMAL,
                    on_bad_lines="skip",
                    low_memory=False,
                )
                frame.columns = [c.strip('"') for c in frame.columns]
                chars = spec["tables"][name].get("strip", '"')
                frame = frame.apply(lambda col, chars=chars: col.str.strip(chars))
                for column in spec["tables"][name].get("pseudonymise", []):
                    frame[column] = frame[column].map(
                        lambda v: pseudonym(v) if pd.notna(v) and v != "" else v
                    )
                    pseudonymised.append(f"{name}.{column}")
                tables[name] = frame
        present = {
            "tables": {n: r for n, r in spec["tables"].items() if n not in absent},
            "relations": [
                r for r in spec["relations"] if r[0] not in absent and r[2] not in absent
            ],
        }
        views, relations = tables_view(tables, present)
        folder = out / source
        folder.mkdir(parents=True, exist_ok=True)
        files = {}
        for name, frame in views.items():
            frame.to_csv(folder / f"{name}.csv", index=False)
            files[f"{name}.csv"] = (folder / f"{name}.csv", len(frame))
        notes = "relations are the source's own keys; orphans are natural incompleteness of the published extract"  # noqa: E501
        if absent:
            notes += f"; optional tables absent from the archive: {', '.join(absent)}"
        _record(
            manifest,
            source,
            files,
            dropped=spec["dropped"],
            pseudonymised=sorted(pseudonymised),
            relations=relations,
            notes=notes,
            **({"salt_label": SALT} if pseudonymised else {}),
            source_snapshot=f"{source}/{SNAPSHOT}",
        )


def series_view(raw: pd.DataFrame, spec: dict[str, Any]) -> pd.DataFrame:
    """A table in time order with a parsed ``timestamp`` and its numeric columns.

    The time columns are joined with a space and parsed with the exact declared format; a row whose
    time cannot be read is dropped and counted (``attrs["rows_dropped"]``), never guessed. Other
    columns are read as numbers (unreadable values become missing); text columns are dropped.
    """
    frame, stamps, used = _stamped(raw, spec)
    numeric = {
        c: pd.to_numeric(frame[c], errors="coerce")
        for c in frame.columns
        if c not in used and pd.to_numeric(frame[c], errors="coerce").notna().any()
    }
    out = pd.DataFrame({"timestamp": stamps, **numeric})
    kept = out[out["timestamp"].notna()].sort_values("timestamp", kind="stable")
    kept = kept.reset_index(drop=True)
    kept.attrs = {"rows_dropped": int(len(out) - len(kept))}
    return kept


def _build_series(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    folder = out / "series"
    folder.mkdir(parents=True, exist_ok=True)
    files, dropped = {}, {}
    for identity, spec in SERIES_SPECS.items():
        number = identity.split(":", 1)[1]
        raw = pd.read_csv(root.parent / spec["dir"] / f"{number}.csv", low_memory=False)
        view = series_view(raw, spec)
        target = folder / f"uci_{number}.csv"
        view.to_csv(target, index=False)
        files[target.name] = (target, len(view))
        dropped[identity] = view.attrs["rows_dropped"]
    _record(
        manifest,
        "series",
        files,
        dropped=[],
        pseudonymised=[],
        rows_dropped=dropped,
        source_snapshot="data/pool and data/uci_wave2 tables, pinned by the pool manifests",
    )


BORG_COLLECTION_COLUMNS = (
    "collection_id",
    "time_us",
    "type",
    "collection_type",
    "priority",
    "scheduling_class",
    "scheduler",
    "vertical_scaling",
)
BORG_INSTANCE_COLUMNS = (
    "collection_id",
    "instance_index",
    "time_us",
    "type",
    "collection_type",
    "priority",
    "scheduling_class",
    "machine_id",
    "cpus",
    "memory",
)
#: lines kept from the start of each Borg shard fragment
BORG_MAX_LINES = 300_000


def _json_rows(lines: list[str]) -> list[dict[str, Any]]:
    return [json.loads(line) for line in lines if line.strip()]


def borg_collection_view(lines: list[str]) -> pd.DataFrame:
    """Collection (job) events of a Borg trace: ids, type codes and time, one sequence per id."""
    rows = [
        {
            "collection_id": r["collection_id"],
            "time_us": r["time"],
            "type": r["type"],
            "collection_type": r.get("collection_type"),
            "priority": r.get("priority"),
            "scheduling_class": r.get("scheduling_class"),
            "scheduler": r.get("scheduler"),
            "vertical_scaling": r.get("vertical_scaling"),
        }
        for r in _json_rows(lines)
    ]
    frame = pd.DataFrame(rows, columns=list(BORG_COLLECTION_COLUMNS))
    for column in frame.columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.sort_values(["collection_id", "time_us"], kind="stable").reset_index(drop=True)


def borg_instance_view(lines: list[str]) -> pd.DataFrame:
    """Instance (task) events of a Borg trace with the requested cpus and memory unpacked."""
    rows = []
    for r in _json_rows(lines):
        request = r.get("resource_request") or {}
        rows.append(
            {
                "collection_id": r["collection_id"],
                "instance_index": r["instance_index"],
                "time_us": r["time"],
                "type": r["type"],
                "collection_type": r.get("collection_type"),
                "priority": r.get("priority"),
                "scheduling_class": r.get("scheduling_class"),
                "machine_id": r.get("machine_id"),
                "cpus": request.get("cpus"),
                "memory": request.get("memory"),
            }
        )
    frame = pd.DataFrame(rows, columns=list(BORG_INSTANCE_COLUMNS))
    for column in frame.columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    order = ["collection_id", "instance_index", "time_us"]
    return frame.sort_values(order, kind="stable").reset_index(drop=True)


def _build_borg(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    from acquisition import gzip_prefix_lines

    raw = root / "google_cluster_2019a" / SNAPSHOT / "raw"
    folder = out / "google_cluster_2019a"
    folder.mkdir(parents=True, exist_ok=True)
    files, fragments = {}, {}
    for name, view, table in (
        ("collection_events_head.json.gz", borg_collection_view, "collection_events.csv"),
        ("instance_events_head.json.gz", borg_instance_view, "instance_events.csv"),
    ):
        read = gzip_prefix_lines((raw / name).read_bytes(), max_output=1 << 31)
        lines = read["lines"][:BORG_MAX_LINES]
        frame = view(lines)
        frame.to_csv(folder / table, index=False)
        files[table] = (folder / table, len(frame))
        fragments[name] = {"lines_read": len(read["lines"]), "stream_complete": read["complete"]}
    _record(
        manifest,
        "google_cluster_2019a",
        files,
        dropped=[
            "user",
            "collection_name",
            "collection_logical_name",
            "constraint",
            "alloc fields",
        ],
        pseudonymised=[],
        sampling=f"prefix of one shard in file order (first {BORG_MAX_LINES} lines of each fragment), not random",  # noqa: E501
        fragments=fragments,
        source_snapshot=f"google_cluster_2019a/{SNAPSHOT}",
    )


SURF_COLUMNS = (
    "job_id", "submit_ts", "wait_s", "runtime_s", "nodes", "cores", "node_type", "state",
)  # fmt: skip
#: every k-th row of the SURF Lisa job table is kept (about 200 000 of 1.6 million jobs)
SURF_STRIDE = 8


def surf_slurm_view(raw: pd.DataFrame) -> pd.DataFrame:
    """SURF Lisa job records: submit time, wait and run time in seconds, size, node type, state.

    Host names are dropped. A job that never started has no start or end time, so its wait and
    run time stay missing.
    """
    need = (
        "id",
        "start_date",
        "end_date",
        "submit_date",
        "numnodes",
        "numcores",
        "nodetypes",
        "state",
    )
    absent = [c for c in need if c not in raw.columns]
    if absent:
        raise ViewError(f"column {absent[0]} not found")
    submit = pd.to_datetime(raw["submit_date"])
    start, end = pd.to_datetime(raw["start_date"]), pd.to_datetime(raw["end_date"])
    out = pd.DataFrame(
        {
            "job_id": raw["id"].astype("int64"),
            "submit_ts": submit,
            "wait_s": (start - submit).dt.total_seconds(),
            "runtime_s": (end - start).dt.total_seconds(),
            "nodes": pd.to_numeric(raw["numnodes"], errors="coerce"),
            "cores": pd.to_numeric(raw["numcores"], errors="coerce"),
            "node_type": raw["nodetypes"].str.replace(r"\(.*\)$", "", regex=True),
            "state": raw["state"],
        }
    )
    return out.sort_values(["submit_ts", "job_id"], kind="stable").reset_index(drop=True)


def _build_surf(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    import tempfile

    import parquet_reader as pr
    from acquisition import extract_member, zip_members

    raw = root / "zen_surf_lisa_slurm" / SNAPSHOT / "raw" / "slurm_table_cleaned.zip"
    parts = [
        m for m in zip_members(raw) if m["name"].endswith(".parquet") and "/part-" in m["name"]
    ]
    folder = out / "zen_surf_lisa_slurm"
    folder.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as scratch:
        chosen = None
        for member in parts:
            got = extract_member(
                raw, member["name"], Path(scratch), max_bytes=1 << 30, max_ratio=200
            )
            if pr.inspect(got["path"])["rows"] > 0:
                chosen = (member["name"], got["path"])
                break
        if chosen is None:
            raise ViewError("no non-empty Parquet part in the archive")
        names = [c["name"] for c in pr.inspect(chosen[1])["columns"]]
        frame, record = pr.read_sample(chosen[1], columns=names, max_rows=10**7, stride=SURF_STRIDE)
    view = surf_slurm_view(frame)
    target = folder / "jobs.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "zen_surf_lisa_slurm",
        {"jobs.csv": (target, len(view))},
        dropped=["node host names"],
        pseudonymised=[],
        sampling={
            "method": f"one row in {SURF_STRIDE} of the only non-empty Parquet part, from the first, in file order",  # noqa: E501
            "stride": SURF_STRIDE,
            "rows_read": record["rows_read"],
            "rows_kept": record["rows_kept"],
            "source_rows": record["source_rows"],
            "truncated": record["truncated"],
            "member": chosen[0],
        },
        source_snapshot=f"zen_surf_lisa_slurm/{SNAPSHOT}",
    )


FUGAKU_COLUMNS = (
    "submit_ts", "wait_s", "runtime_s", "cores_req", "cores_alloc", "nodes_req", "nodes_alloc",
    "exit_code", "time_limit_s", "priority", "energy", "avg_power", "max_power", "mem_limit",
    "mem_alloc", "mem_used", "pclass", "state",
)  # fmt: skip


def fugaku_jobs_view(raw: pd.DataFrame) -> pd.DataFrame:
    """Fugaku job records: times, sizes, power, memory and outcome. User, job name, the text
    embedding and the job environment string are dropped (the publisher anonymised them but they
    are not experiment features)."""
    need = ("adt", "sdt", "edt", "cnumr", "cnumat", "nnumr", "nnuma", "ec", "elpl", "pri", "econ",
            "avgpcon", "maxpcon", "mszl", "msza", "mmszu", "pclass", "exit state")  # fmt: skip
    absent = [c for c in need if c not in raw.columns]
    if absent:
        raise ViewError(f"column {absent[0]} not found")
    submit, start, end = (pd.to_datetime(raw[c]) for c in ("adt", "sdt", "edt"))
    out = pd.DataFrame(
        {
            "submit_ts": submit,
            "wait_s": (start - submit).dt.total_seconds(),
            "runtime_s": (end - start).dt.total_seconds(),
            "cores_req": raw["cnumr"], "cores_alloc": raw["cnumat"],
            "nodes_req": raw["nnumr"], "nodes_alloc": raw["nnuma"],
            "exit_code": raw["ec"], "time_limit_s": raw["elpl"], "priority": raw["pri"],
            "energy": raw["econ"], "avg_power": raw["avgpcon"], "max_power": raw["maxpcon"],
            "mem_limit": raw["mszl"], "mem_alloc": raw["msza"], "mem_used": raw["mmszu"],
            "pclass": raw["pclass"], "state": raw["exit state"],
        }
    )  # fmt: skip
    return out.sort_values("submit_ts", kind="stable").reset_index(drop=True)


def csv_prefix(blob: bytes) -> tuple[pd.DataFrame, int]:
    """A CSV from the start of a file: only complete lines are parsed. Returns the table and the
    number of bytes of the torn last line that were left out."""
    import io

    end = blob.rfind(b"\n") + 1
    return pd.read_csv(io.BytesIO(blob[:end])), len(blob) - end


METROPT_GPS = ("gpsLat", "gpsLong", "gpsSpeed", "gpsQuality")


def metropt_view(raw: pd.DataFrame) -> pd.DataFrame:
    """MetroPT2 sensor series in time order; the train's GPS columns are dropped."""
    frame = raw.drop(columns=[c for c in METROPT_GPS if c in raw.columns])
    return series_view(frame, {"time": ["timestamp"], "format": "%Y-%m-%d %H:%M:%S.%f"})


def _build_fugaku(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    import parquet_reader as pr

    source = root / "zen_fdata_fugaku" / SNAPSHOT / "raw" / "21_04.parquet"
    names = [c["name"] for c in pr.inspect(source)["columns"] if c["name"] != "embedding"]
    frame, record = pr.read_sample(source, columns=names, max_rows=10**7)
    view = fugaku_jobs_view(frame)
    folder = out / "zen_fdata_fugaku"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "jobs.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "zen_fdata_fugaku",
        {"jobs.csv": (target, len(view))},
        dropped=["user", "job name", "job id", "text embedding", "job environment string"],
        pseudonymised=[],
        sampling={
            "method": "all rows of one monthly Parquet file (2021-04); the other months were not fetched",  # noqa: E501
            "rows_read": record["rows_read"],
            "source_rows": record["source_rows"],
            "truncated": record["truncated"],
        },
        source_snapshot=f"zen_fdata_fugaku/{SNAPSHOT}",
    )


def _build_metropt(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    blob = (root / "zen_metropt2" / SNAPSHOT / "raw" / "MetroPT2_head.csv").read_bytes()
    frame, cut = csv_prefix(blob)
    view = metropt_view(frame)
    folder = out / "zen_metropt2"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "series.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "zen_metropt2",
        {"series.csv": (target, len(view))},
        dropped=["GPS position, speed and quality columns"],
        pseudonymised=[],
        sampling={
            "method": "time-ordered prefix of the CSV (HTTP range from byte 0), not random",
            "bytes_cut_partial_line": cut,
            "rows_dropped": view.attrs["rows_dropped"],
        },
        source_snapshot=f"zen_metropt2/{SNAPSHOT} (fragment)",
    )


OPENLIBRARY_DROP = frozenset(["notes", "description", "first_sentence", "table_of_contents"])
#: one edition in this many is kept, chosen by a hash of its key
OPENLIBRARY_MODULO = 10


def open_library_view(lines: list[str], modulo: int) -> tuple[list[dict[str, Any]], int]:
    """Complete edition records from dump lines (type, key, revision, time, JSON), by key hash.

    A record is kept when the hash of its key is divisible by ``modulo``; free-text fields are
    dropped at every depth. Lines that are not five tab-separated fields with valid JSON are
    counted as skipped (blank lines are ignored). Records come out ordered by key.
    """
    kept, skipped = [], 0
    for line in lines:
        if not line.strip():
            continue
        fields = line.split("\t")
        try:
            if len(fields) != 5:
                raise ValueError("fields")
            record = json.loads(fields[4])
        except ValueError:
            skipped += 1
            continue
        if int(hashlib.sha256(record["key"].encode()).hexdigest(), 16) % modulo == 0:
            kept.append(record)
    return nested_view(kept, OPENLIBRARY_DROP, lambda r: r["key"]), skipped


def _build_openlibrary(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    from acquisition import gzip_prefix_lines

    blob = (root / "openlibrary_dump" / SNAPSHOT / "raw" / "editions_head.txt.gz").read_bytes()
    read = gzip_prefix_lines(blob, max_output=1 << 31)
    view, skipped = open_library_view(read["lines"], OPENLIBRARY_MODULO)
    folder = out / "openlibrary_dump"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "editions.jsonl"
    target.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in view))
    _record(
        manifest,
        "openlibrary_dump",
        {"editions.jsonl": (target, len(view))},
        dropped=["notes", "description", "first_sentence", "table_of_contents"],
        pseudonymised=[],
        sampling={
            "method": "gzip prefix of the editions dump in key-text order, then one record in "
            f"{OPENLIBRARY_MODULO} by key hash; not a random sample of the catalogue",
            "modulo": OPENLIBRARY_MODULO,
            "lines_read": len(read["lines"]),
            "lines_skipped": skipped,
            "stream_complete": read["complete"],
        },
        source_snapshot=f"openlibrary_dump/{SNAPSHOT} (dump of 2026-10-31, fragment)",
    )


def aegis_obd_view(raw: pd.DataFrame) -> pd.DataFrame:
    """OBD signals of the AEGIS vehicle: mean value per pid and whole second since the trip's
    first reading. Absolute dates, positions and other sensors are not part of the view."""
    need = ("trip_id", "obdPid", "data", "timestamp")
    absent = [c for c in need if c not in raw.columns]
    if absent:
        raise ViewError(f"column {absent[0]} not found")
    stamps = pd.to_datetime(raw["timestamp"])
    frame = pd.DataFrame(
        {
            "trip_id": raw["trip_id"].astype("int64"),
            "pid": "pid_" + raw["obdPid"].astype(str),
            "t_s": ((stamps - stamps.groupby(raw["trip_id"]).transform("min")).dt.total_seconds())
            .floordiv(1)
            .astype("int64"),
            "value": pd.to_numeric(raw["data"], errors="coerce"),
        }
    )
    wide = frame.groupby(["trip_id", "t_s", "pid"])["value"].mean().unstack("pid")
    out = wide.reset_index()
    out.columns.name = None
    return out.sort_values(["trip_id", "t_s"], kind="stable").reset_index(drop=True)


def _build_aegis(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    import tempfile

    from acquisition import extract_member

    archive = (
        root / "zen_aegis_vehicle" / SNAPSHOT / "raw" / "Automotive-ResearchDataSet-VIF-AEGIS.zip"
    )
    with tempfile.TemporaryDirectory() as scratch:
        got = extract_member(
            archive, "obdData.csv", Path(scratch), max_bytes=1 << 30, max_ratio=200
        )
        raw = pd.read_csv(got["path"])
    view = aegis_obd_view(raw)
    folder = out / "zen_aegis_vehicle"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "obd.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "zen_aegis_vehicle",
        {"obd.csv": (target, len(view))},
        dropped=[
            "positions",
            "gyroscopes",
            "accelerations",
            "absolute dates and times",
            "trip dates",
            "vehicle names",
        ],
        pseudonymised=[],
        notes="one driver and one vehicle (35 trips); relative time inside each trip only",
        source_snapshot=f"zen_aegis_vehicle/{SNAPSHOT}",
    )


CLUE_COLUMNS = ("event_id", "time", "user", "type", "role", "is_local_ip")
#: events kept from the start of the CLUE-LDS prefix
CLUE_MAX_EVENTS = 1_000_000
#: decoded bytes read from the prefix (about 1.3 million events)
CLUE_MAX_BYTES = 400 * 1024 * 1024


def clue_events_view(lines: list[str]) -> pd.DataFrame:
    """User events: id, UTC time, salted pseudonym of the user (or IP), type, role, origin flag.

    Event parameters (file paths, groups) and the IP-based location are dropped. Events come out
    in id order, which is the time order of the log.
    """
    rows = []
    for line in lines:
        if not line.strip():
            continue
        r = json.loads(line)
        rows.append(
            {
                "event_id": r["id"],
                "time": r["time"],
                "user": pseudonym(str(r["uid"])),
                "type": r["type"],
                "role": r.get("role"),
                "is_local_ip": r.get("isLocalIP"),
            }
        )
    frame = pd.DataFrame(rows, columns=list(CLUE_COLUMNS))
    frame["time"] = pd.to_datetime(frame["time"], utc=True)
    return frame.sort_values("event_id", kind="stable").reset_index(drop=True)


def _build_clue(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    from acquisition import zip_prefix_lines

    blob = (root / "zen_clue_lds" / SNAPSHOT / "raw" / "clue_head.zip").read_bytes()
    read = zip_prefix_lines(blob, max_output=CLUE_MAX_BYTES)
    view = clue_events_view(read["lines"][:CLUE_MAX_EVENTS])
    folder = out / "zen_clue_lds"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "events.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "zen_clue_lds",
        {"events.csv": (target, len(view))},
        dropped=["params (paths, groups)", "location", "uidType"],
        pseudonymised=["user"],
        sampling={
            "method": "zip prefix of clue.json (HTTP range from byte 0), first events in log order; not random",  # noqa: E501
            "events_read": len(read["lines"]),
            "events_kept": len(view),
            "stream_complete": read["complete"],
        },
        salt_label=SALT,
        source_snapshot=f"zen_clue_lds/{SNAPSHOT} (fragment)",
    )


def xes_view(traces: list[dict[str, Any]], modulo: int, numeric: list[str]) -> pd.DataFrame:
    """One row per event: case, position, UTC time, activity, transition, salted resource, numbers.

    A case is kept when the hash of its name is divisible by ``modulo``; cases are ordered by
    name and events keep their log order.
    """
    rows = []
    for trace in sorted(traces, key=lambda t: str(t["case"])):
        if int(hashlib.sha256(str(trace["case"]).encode()).hexdigest(), 16) % modulo:
            continue
        for position, e in enumerate(trace["events"]):
            resource = e.get("org:resource")
            rows.append(
                {
                    "case_id": trace["case"],
                    "position": position,
                    "time": e.get("time:timestamp"),
                    "activity": e.get("concept:name"),
                    "transition": e.get("lifecycle:transition"),
                    "resource": pseudonym(resource) if resource is not None else None,
                    **{n: e[n] if n in e else trace.get("attributes", {}).get(n) for n in numeric},
                }
            )
    columns = ["case_id", "position", "time", "activity", "transition", "resource", *numeric]
    frame = pd.DataFrame(rows, columns=columns)
    frame["time"] = pd.to_datetime(frame["time"], utc=True, format="ISO8601")
    for n in numeric:
        frame[n] = pd.to_numeric(frame[n], errors="coerce").astype("float64")
    return frame


#: process-mining logs: the raw file, how many cases to keep (one in ``modulo``) and the numeric fields  # noqa: E501
XES_SPECS: dict[str, dict[str, Any]] = {
    "4tu_bpic12": {"file": "BPI_Challenge_2012.xes.gz", "modulo": 1, "numeric": [], "partial": False},  # noqa: E501
    "4tu_bpic13_incidents": {"file": "BPI_Challenge_2013_incidents.xes.gz", "modulo": 1, "numeric": [], "partial": False},  # noqa: E501
    "4tu_bpic15_m5": {"file": "BPIC15_5.xes", "modulo": 1, "numeric": [], "partial": False},
    "4tu_road_fines": {"file": "Road_Traffic_Fine_Management_Process.xes.gz", "modulo": 1, "numeric": ["amount", "paymentAmount", "expense"], "partial": False},  # noqa: E501
    "4tu_bpic20_domestic": {"file": "DomesticDeclarations.xes.gz", "modulo": 1, "numeric": [], "partial": False},  # noqa: E501
    "4tu_bpic20_international": {"file": "InternationalDeclarations.xes.gz", "modulo": 1, "numeric": [], "partial": False},  # noqa: E501
    "4tu_sepsis": {"file": "Sepsis_Cases_-_Event_Log.xes.gz", "modulo": 1, "numeric": [], "partial": False},  # noqa: E501
    "4tu_bpic18": {
        "file": "BPI_Challenge_2018_head.xes.gz",
        "modulo": 1,
        "numeric": ["payment_actual0", "amount_applied0"],
        "partial": True,
        "max_traces": 8000,
    },
    "4tu_bpic19": {"file": "BPI_Challenge_2019_head.xes", "modulo": 1, "numeric": ["Cumulative net worth (EUR)"], "partial": True},  # noqa: E501
}  # fmt: skip


def _build_xes(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    import xes_stream

    for source, spec in XES_SPECS.items():
        path = root / source / SNAPSHOT / "raw" / spec["file"]
        with path.open("rb") as stream:
            read = xes_stream.read_traces(
                stream,
                compressed=path.suffix == ".gz",
                modulo=spec["modulo"],
                max_traces=spec.get("max_traces"),
            )
        view = xes_view(read.traces, 1, spec["numeric"])
        folder = out / source
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / "events.csv"
        view.to_csv(target, index=False)
        _record(
            manifest,
            source,
            {"events.csv": (target, len(view))},
            dropped=[
                "all trace and event attributes except activity, time, transition, resource "
                "and listed numbers"
            ],
            pseudonymised=["resource"],
            sampling={
                "cases_read": read.status["traces_seen"],
                "cases_kept": int(view["case_id"].nunique()),
                "modulo": spec["modulo"],
                "stream_complete": read.status["stream_complete"],
                "stop": read.status["stop"],
                "source_fragment": spec["partial"],
                "selection": "complete traces in log order, then one case in "
                f"{spec['modulo']} by case-name hash; a prefix of the log is not a random sample",
            },
            salt_label=SALT,
            source_snapshot=f"{source}/{SNAPSHOT}",
        )


def csv_event_view(
    frame: pd.DataFrame, spec: dict[str, Any]
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Events from a table where one row is one event, with a declared schema mapping.

    ``spec`` names the case, activity, time (with its exact format), tie-break sequence and
    resource columns. Rows without an activity or with an unreadable time are dropped and counted,
    never guessed; within a case events are ordered by time, then by the source's own sequence
    column. Cases are kept by case-name hash (``modulo``).
    """
    for key in ("case", "activity", "time", "order", "resource"):
        if spec[key] not in frame.columns:
            raise ViewError(f"column {spec[key]!r} not found")
    stamps = pd.to_datetime(frame[spec["time"]], format=spec["format"], errors="coerce", utc=True)
    usable = frame[spec["activity"]].notna() & stamps.notna()
    table = pd.DataFrame(
        {
            "case_id": frame[spec["case"]].astype(str),
            "time": stamps,
            "activity": frame[spec["activity"]],
            "transition": None,
            "resource": frame[spec["resource"]].map(
                lambda v: pseudonym(str(v)) if pd.notna(v) else None
            ),
            "_order": frame[spec["order"]].astype(str),
        }
    )[usable]
    keep = table["case_id"].map(
        lambda c: int(hashlib.sha256(c.encode()).hexdigest(), 16) % spec["modulo"] == 0
    )
    table = table[keep].sort_values(["case_id", "time", "_order"], kind="stable")
    table["position"] = table.groupby("case_id").cumcount()
    view = table[["case_id", "position", "time", "activity", "transition", "resource"]]
    info = {
        "rows": len(frame),
        "rows_without_activity": int(frame[spec["activity"]].isna().sum()),
        "rows_without_time": int((stamps.isna() & frame[spec["activity"]].notna()).sum()),
        "cases": int(frame[spec["case"]].nunique()),
        "cases_kept": int(view["case_id"].nunique()),
    }
    return view.reset_index(drop=True), info


#: event logs published as one CSV row per event: the file and the explicit column mapping
CSV_EVENT_SPECS: dict[str, dict[str, Any]] = {
    "4tu_bpic14": {
        "file": "Detail_Incident_Activity.csv",
        "sep": ";",
        "case": "Incident ID",
        "activity": "IncidentActivity_Type",
        "time": "DateStamp",
        "format": "%d-%m-%Y %H:%M:%S",
        "order": "IncidentActivity_Number",
        "resource": "Assignment Group",
        "modulo": 1,
    }
}


def _build_csv_events(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    for source, spec in CSV_EVENT_SPECS.items():
        raw = pd.read_csv(
            root / source / SNAPSHOT / "raw" / spec["file"], sep=spec["sep"], dtype=str
        )
        view, info = csv_event_view(raw, spec)
        folder = out / source
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / "events.csv"
        view.to_csv(target, index=False)
        _record(
            manifest,
            source,
            {"events.csv": (target, len(view))},
            dropped=["all columns except case, activity, time, sequence and resource"],
            pseudonymised=["resource"],
            sampling={
                **info,
                "modulo": spec["modulo"],
                "mapping": {k: spec[k] for k in ("case", "activity", "time", "order", "resource")},
            },
            salt_label=SALT,
            source_snapshot=f"{source}/{SNAPSHOT}",
        )


MET_DROP = frozenset(["artistDisplayBio", "primaryImage", "primaryImageSmall", "additionalImages"])


def met_objects_view(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Catalogue records without biographies and image links; one record per object id."""
    unique: dict[Any, dict[str, Any]] = {}
    for record in records:
        unique.setdefault(record["objectID"], record)
    return nested_view(list(unique.values()), MET_DROP, lambda r: r["objectID"])


def _build_met(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    raw = root / "met_museum_objects" / SNAPSHOT / "raw"
    files = sorted(raw.glob("obj_*.json"))
    records, unreadable = [], 0
    for path in files:
        try:
            records.append(json.loads(path.read_text()))
        except ValueError:
            unreadable += 1
    view = met_objects_view(records)
    folder = out / "met_museum_objects"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "objects.jsonl"
    target.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in view))
    _record(
        manifest,
        "met_museum_objects",
        {"objects.jsonl": (target, len(view))},
        dropped=["artistDisplayBio", "primaryImage", "primaryImageSmall", "additionalImages"],
        pseudonymised=[],
        sampling={
            "object_files": len(files),
            "unreadable": unreadable,
            "method": "object ids chosen as an even stride over the sorted listing, not random",
        },
        source_snapshot=f"met_museum_objects/{SNAPSHOT}",
    )


#: Environment Agency stations (measure notations) whose daily mean flow readings are fetched
EA_STATIONS: list[str] = [
    "052d0819-2a32-47df-9b99-c243c9c8235b-flow-m-86400-m3s-qualified",
    "284ea1dd-ee32-47ef-8cbf-4b001775f8ed-flow-m-86400-m3s-qualified",
    "3eb60c5b-875e-46e7-b8d9-b1208d023bc4-flow-m-86400-m3s-qualified",
    "48513a18-e485-4317-ae92-93bf4f7f3e54-flow-m-86400-m3s-qualified",
    "588e6dc1-a77f-4961-9085-4b2617acb48e-flow-m-86400-m3s-qualified",
    "6c6c174e-519f-4b02-9e3e-1737f2139417_445508-flow-m-86400-m3s-qualified",
    "7337c648-a4bf-4f8b-80c2-2b17efdba8cd-flow-m-86400-m3s-qualified",
    "8c0977fe-d8fe-4d98-83ab-7916cbd2eb83-flow-m-86400-m3s-qualified",
    "9796dc02-6edf-4392-b727-0d861cbb1edd-flow-m-86400-m3s-qualified",
    "b23821f8-f8e5-4b3d-a821-70913abe37cf-flow-m-86400-m3s-qualified",
    "bf679fd0-8d8f-4815-a569-ec798d81f324-flow-m-86400-m3s-qualified",
    "d42b68be-0da7-4519-ba9a-e24f789d9c10-flow-m-86400-m3s-qualified",
]


def _build_ea(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    raw = root / "ea_hydrology_flow" / SNAPSHOT / "raw"
    parts = []
    for station in EA_STATIONS:
        frame = pd.read_csv(raw / f"flow_{station}.csv", dtype=str)
        frame["station"] = station
        parts.append(frame)
    table = pd.concat(parts, ignore_index=True)
    view = panel_view(table, {"time": ["date"], "format": "%Y-%m-%d", "keys": ["station"]})
    folder = out / "ea_hydrology_flow"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "flow.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "ea_hydrology_flow",
        {"flow.csv": (target, len(view))},
        dropped=["measure URL", "dateTime", "quality code text"],
        pseudonymised=[],
        sampling={
            "stations": len(EA_STATIONS),
            "rows_dropped": view.attrs["rows_dropped"],
            "complete_share": round(float((table["completeness"] == "Complete").mean()), 4),
            "missing_value_share": round(float((table["value"].fillna("") == "").mean()), 4),
            "method": "daily mean flow of stations chosen as an even stride over the sorted measure list",  # noqa: E501
        },
        source_snapshot=f"ea_hydrology_flow/{SNAPSHOT}",
    )


DVF_COLUMNS = (
    "mutation", "date", "nature", "value_eur", "commune", "local_type", "built_area_m2", "rooms",
    "land_area_m2",
)  # fmt: skip


def dvf_view(raw: pd.DataFrame) -> pd.DataFrame:
    """Property transaction rows without address, parcel or position; the mutation id is salted.

    One row is one disposition of a transaction (a transaction can have several rows: lots and
    land). Addresses, parcel ids and coordinates are not kept: with them a sale is a located
    property and, with public registers, a person.
    """
    need = ("id_mutation", "date_mutation", "nature_mutation", "valeur_fonciere", "code_commune",
            "type_local", "surface_reelle_bati", "nombre_pieces_principales", "surface_terrain")  # fmt: skip  # noqa: E501
    for column in need:
        if column not in raw.columns:
            raise ViewError(f"column {column!r} not found")
    out = pd.DataFrame(
        {
            "mutation": raw["id_mutation"].map(lambda v: pseudonym(str(v))),
            "date": raw["date_mutation"],
            "nature": raw["nature_mutation"],
            "value_eur": pd.to_numeric(raw["valeur_fonciere"], errors="coerce"),
            "commune": raw["code_commune"].astype(str),
            "local_type": raw["type_local"],
            "built_area_m2": pd.to_numeric(raw["surface_reelle_bati"], errors="coerce"),
            "rooms": pd.to_numeric(raw["nombre_pieces_principales"], errors="coerce"),
            "land_area_m2": pd.to_numeric(raw["surface_terrain"], errors="coerce"),
        }
    )
    return out.sort_values(["date", "mutation"], kind="stable").reset_index(drop=True)


def _build_dvf(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    raw = pd.read_csv(
        root / "dgfip_dvf" / SNAPSHOT / "raw" / "dvf_69_2024.csv.gz", dtype=str, low_memory=False
    )
    view = dvf_view(raw)
    folder = out / "dgfip_dvf"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "sales.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "dgfip_dvf",
        {"sales.csv": (target, len(view))},
        dropped=["address, street code, parcel ids, volume and lot numbers, coordinates"],
        pseudonymised=["mutation"],
        sampling={
            "scope": "department 69 (Rhone), transactions of 2024 only",
            "rows": len(view),
            "rows_without_value": int(view["value_eur"].isna().sum()),
        },
        salt_label=SALT,
        source_snapshot=f"dgfip_dvf/{SNAPSHOT}",
    )


FLAT_SELECTION = (
    Path(__file__).resolve().parent.parent
    / "verification/evidence/dataset_registry_v2/flat_selection.json"
)


def _build_flat(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    """Views of the represented flat tabular and categorical tables (one manifest entry each)."""
    import flat_readiness
    import uci_loader

    folder = out / "flat"
    folder.mkdir(parents=True, exist_ok=True)
    for view in json.loads(FLAT_SELECTION.read_text())["views"]:
        number = view["source"].split(":", 1)[1]
        path = next(
            p for p in (root.parent / "pool" / f"{number}.csv", root.parent / "uci_wave2" / f"{number}.csv")  # noqa: E501
            if p.exists()
        )  # fmt: skip
        frame, record = flat_readiness.prepare(uci_loader.read_table(path))
        target = folder / f"{view['key']}.csv"
        frame.to_csv(target, index=False)
        _record(
            manifest,
            view["key"],
            {target.name: (target, len(frame))},
            dropped=[*record["dropped_constant"], *record["dropped_missing"]],
            pseudonymised=[],
            sampling={
                "rows_in": record["rows_in"],
                "stride": record["stride"],
                "method": "every stride-th row from the first; the table is read as published",
            },
            table=view["table"],
            stratum=view["stratum"],
            source_snapshot=f"{view['source']} (repository file pinned by checksum)",
        )


PPD_COLUMNS = (
    "transaction", "price_gbp", "date", "postcode_district", "property_type", "new_build",
    "tenure", "county", "ppd_category", "status",
)  # fmt: skip
_PPD_NAMES = (
    "id", "price", "date", "postcode", "type", "new", "tenure", "paon", "saon", "street",
    "locality", "town", "district", "county", "category", "status",
)  # fmt: skip


def csv_prefix_no_header(blob: bytes) -> tuple[pd.DataFrame, int]:
    """Complete lines of a header-less quoted CSV prefix and the byte count of the torn line."""
    import io

    end = blob.rfind(b"\n") + 1
    frame = pd.read_csv(io.BytesIO(blob[:end]), header=None, dtype=str, keep_default_na=False)
    return frame, len(blob) - end


def price_paid_view(raw: pd.DataFrame) -> pd.DataFrame:
    """Property sales: salted transaction id, price, date, postcode district, type, tenure, county.

    Street, house number, flat, locality, town, district and the postcode unit are not kept: with
    the public register they would identify a property and its owner.
    """
    if raw.shape[1] != len(_PPD_NAMES):
        raise ViewError(f"expected {len(_PPD_NAMES)} columns, found {raw.shape[1]}")
    named = raw.set_axis(_PPD_NAMES, axis=1)
    out = pd.DataFrame(
        {
            "transaction": named["id"].map(pseudonym),
            "price_gbp": named["price"].astype("int64"),
            "date": named["date"].str.slice(0, 10),
            "postcode_district": named["postcode"].str.split(" ").str[0],
            "property_type": named["type"],
            "new_build": named["new"],
            "tenure": named["tenure"],
            "county": named["county"],
            "ppd_category": named["category"],
            "status": named["status"],
        }
    )
    return out.sort_values(["date", "transaction"], kind="stable").reset_index(drop=True)


def _build_ppd(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    blob = (root / "hmlr_price_paid" / SNAPSHOT / "raw" / "pp-2024_head.csv").read_bytes()
    frame, cut = csv_prefix_no_header(blob)
    view = price_paid_view(frame)
    folder = out / "hmlr_price_paid"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "sales.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "hmlr_price_paid",
        {"sales.csv": (target, len(view))},
        dropped=["street, house number, flat, locality, town and district", "postcode unit"],
        pseudonymised=["transaction"],
        sampling={
            "method": "first bytes of the 2024 file (HTTP range from byte 0), file order, not random",  # noqa: E501
            "rows": len(view),
            "bytes_cut_partial_line": cut,
        },
        salt_label=SALT,
        source_snapshot=f"hmlr_price_paid/{SNAPSHOT} (fragment)",
    )


def _is_human(entity: dict[str, Any]) -> bool:
    """True when the item states that it is an instance of human (property P31, item Q5)."""
    for claim in entity.get("claims", {}).get("P31", []):
        value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(value, dict) and value.get("id") == "Q5":
            return True
    return False


def wikidata_view(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Wikidata items in identifier order, one per identifier, without items about people.

    Returns the items and the number of people dropped. Everything else, including the language,
    claim, qualifier, reference and sitelink structure, is kept as published.
    """
    unique: dict[str, dict[str, Any]] = {}
    for record in records:
        unique.setdefault(record["id"], record)
    people = [i for i, r in unique.items() if _is_human(r)]
    kept = [r for i, r in unique.items() if i not in people]
    return nested_view(kept, frozenset(), lambda r: int(r["id"][1:])), len(people)


def _build_wikidata(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    raw = root / "wikidata_entities" / SNAPSHOT / "raw"
    files = sorted(raw.glob("entities_*.json"))
    records, absent = [], 0
    for path in files:
        for entity in json.loads(path.read_text())["entities"].values():
            if "missing" in entity:
                absent += 1
            else:
                records.append(entity)
    view, people = wikidata_view(records)
    folder = out / "wikidata_entities"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "items.jsonl"
    target.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in view))
    _record(
        manifest,
        "wikidata_entities",
        {"items.jsonl": (target, len(view))},
        dropped=["items that are instances of human"],
        pseudonymised=[],
        sampling={
            "request_files": len(files),
            "identifiers_absent": absent,
            "people_dropped": people,
            "method": "identifiers Q(1 + k x 52361) spread over the identifier range, not random; items about people are excluded",  # noqa: E501
        },
        source_snapshot=f"wikidata_entities/{SNAPSHOT}",
    )


NVD_SNAPSHOT = "2026-11-22"
NVD_NOTICE = (
    "This product uses data from the NVD API but is not endorsed or certified by the NVD. "
    "CVE content: Copyright The MITRE Corporation, used under the CVE Usage license "
    "(https://www.cve.org/Legal/TermsOfUse)."
)


def nvd_view(pages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """CVE records of NVD API 2.0 pages in identifier order, one per identifier.

    Returns the records and the number of repeated identifiers that were skipped (the first
    occurrence is kept). The records are kept as published, including every optional part.
    """
    unique: dict[str, dict[str, Any]] = {}
    repeated = 0
    for page in pages:
        for item in page["vulnerabilities"]:
            record = item["cve"]
            if record["id"] in unique:
                repeated += 1
            else:
                unique[record["id"]] = record
    return nested_view(list(unique.values()), frozenset(), lambda r: r["id"]), repeated


def _build_nvd(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    raw = root / "nvd_cve" / NVD_SNAPSHOT / "raw"
    files = sorted(raw.glob("cves_*.json"))
    if not files:
        raise ViewError("no NVD page in the snapshot")
    pages = [json.loads(path.read_text()) for path in files]
    view, repeated = nvd_view(pages)
    folder = out / "nvd_cve"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "cves.jsonl"
    target.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in view))
    (folder / "NOTICE.txt").write_text(NVD_NOTICE + "\n")
    _record(
        manifest,
        "nvd_cve",
        {"cves.jsonl": (target, len(view))},
        dropped=[],
        pseudonymised=[],
        sampling={
            "method": "CVEs published in the first fifteen days of March of four years, one API page each",  # noqa: E501
            "pages": [p.name for p in files],
            "total_results": [page["totalResults"] for page in pages],
            "complete_pages": all(
                page["totalResults"] == len(page["vulnerabilities"]) for page in pages
            ),  # noqa: E501
            "repeated_ids": repeated,
        },
        source_snapshot=f"nvd_cve/{NVD_SNAPSHOT}",
    )


CARE_SNAPSHOT = "2026-11-22"
CARE_MAX_BYTES = 256 << 20
CARE_META = ("event_id", "asset_id", "time_stamp", "row_id", "train_test", "status_type")


def zip_local_member(blob: bytes, max_out: int = CARE_MAX_BYTES) -> bytes:
    """The content of one zip member given its local header and stored or deflate data.

    The data may be followed by other bytes (the next header). A deflate stream that does not end
    inside ``blob`` or that exceeds ``max_out`` bytes is an error.
    """
    import struct
    import zlib

    if len(blob) < 30 or blob[:4] != b"PK\x03\x04":
        raise ViewError("not a zip local header")
    method, name_len, extra_len = (
        struct.unpack("<H", blob[8:10])[0],
        *struct.unpack("<HH", blob[26:30]),
    )
    data = blob[30 + name_len + extra_len :]
    if method != 8:
        raise ViewError(f"unsupported zip method {method}")
    stream = zlib.decompressobj(-15)
    content = stream.decompress(data, max_out + 1)
    if len(content) > max_out:
        raise ViewError("member larger than the limit")
    if not stream.eof:
        raise ViewError("deflate stream incomplete")
    return content


def care_series_view(raw: pd.DataFrame, event_id: int) -> pd.DataFrame:
    """Ten-minute average sensor values of one wind turbine dataset with its phase and status.

    The publisher anonymised the timestamps and asset ids. ``train_test`` and the turbine status are
    kept as published; the event label is not part of the series (see ``events.csv``).
    """
    need = ["time_stamp", "asset_id", "id", "train_test", "status_type_id"]
    missing = [c for c in need if c not in raw.columns]
    if missing:
        raise ViewError(f"columns not found: {missing}")
    averages = [c for c in raw.columns if c.endswith("_avg")]
    if not averages:
        raise ViewError("no average sensor columns")
    out = pd.DataFrame(
        {
            "event_id": event_id,
            "asset_id": pd.to_numeric(raw["asset_id"], errors="coerce"),
            "time_stamp": pd.to_datetime(raw["time_stamp"], errors="coerce"),
            "row_id": pd.to_numeric(raw["id"], errors="coerce"),
            "train_test": raw["train_test"].astype("string"),
            "status_type": pd.to_numeric(raw["status_type_id"], errors="coerce"),
        }
    )
    for column in averages:
        out[column] = pd.to_numeric(raw[column], errors="coerce")
    out = out[out["time_stamp"].notna()]
    return out.sort_values("time_stamp", kind="stable").reset_index(drop=True)


def _build_care(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    import io

    raw = root / "zen_care_wind_b" / CARE_SNAPSHOT / "raw"
    info = pd.read_csv(io.BytesIO(zip_local_member((raw / "event_info.csv").read_bytes())), sep=";")
    ids = sorted(int(p.stem) for p in raw.glob("*.csv") if p.stem.isdigit())
    if not ids:
        raise ViewError("no dataset in the snapshot")
    frames = []
    for event_id in ids:
        content = zip_local_member((raw / f"{event_id}.csv").read_bytes())
        frames.append(care_series_view(pd.read_csv(io.BytesIO(content), sep=";"), event_id))
    view = pd.concat(frames)
    info["in_view"] = info["event_id"].isin(ids)
    folder = out / "zen_care_wind_b"
    folder.mkdir(parents=True, exist_ok=True)
    series, events = folder / "series.csv", folder / "events.csv"
    view.to_csv(series, index=False)
    info.sort_values("event_id").to_csv(events, index=False)
    _record(
        manifest,
        "zen_care_wind_b",
        {"series.csv": (series, len(view)), "events.csv": (events, len(info))},
        dropped=["minimum, maximum and standard-deviation columns of every sensor"],
        pseudonymised=[],
        sampling={
            "method": "five of the fifteen datasets of Wind Farm B (three with a labelled anomaly event, two normal); Wind Farm A and C and ten datasets of B were not fetched",  # noqa: E501
            "datasets": ids,
            "anomaly_datasets_in_view": int(
                info.loc[info["in_view"] & (info["event_label"] == "anomaly"), "event_id"].count()
            ),  # noqa: E501
            "rows_in": len(view),
        },
        source_snapshot=f"zen_care_wind_b/{CARE_SNAPSHOT}",
    )


BESS_NUMBERS = {
    "HoursElapsed": "hours_elapsed",
    "DayNumber": "day_number",
    "Power": "power",
    "RequestedPower": "requested_power",
    "ReactivePower": "reactive_power",
    "RequestedReactivePower": "requested_reactive_power",
    "Voltage": "voltage",
    "VoltageMax": "voltage_max",
    "VoltageMin": "voltage_min",
    "VoltageAvg": "voltage_avg",
    "Current": "current",
    "SOC": "soc",
    "TempMax": "temp_max",
    "TempMin": "temp_min",
    "TempAvg": "temp_avg",
    "TempAmbient": "temp_ambient",
}
BESS_COLUMNS = ("system", "meter", *BESS_NUMBERS.values(), "quality_flag", "cycle_index", "use")


def bess_view(raw: pd.DataFrame, system: str) -> pd.DataFrame:
    """Meter readings of one grid-scale battery system in elapsed time.

    Time is the published elapsed time in hours, not a calendar date. Missing values stay missing
    (each meter reports only its own channels); the publisher's quality and use flags are kept.
    """
    need = [*BESS_NUMBERS, "Meter", "QualityFlag", "CycleIndex", "Use"]
    missing = [c for c in need if c not in raw.columns]
    if missing:
        raise ViewError(f"columns not found: {missing}")
    out = pd.DataFrame({"system": system, "meter": raw["Meter"].astype("string")})
    for source, name in BESS_NUMBERS.items():
        out[name] = pd.to_numeric(raw[source], errors="coerce")
    out["quality_flag"] = raw["QualityFlag"].astype(bool)
    out["cycle_index"] = raw["CycleIndex"].astype("string")
    out["use"] = raw["Use"].astype(bool)
    out = out[out["hours_elapsed"].notna()]
    return out.sort_values(["hours_elapsed", "meter"]).reset_index(drop=True)


def _build_bess(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    import pyarrow.feather as feather

    raw = root / "zen_bess" / SNAPSHOT / "raw"
    files = sorted(raw.glob("*.feather"))
    if not files:
        raise ViewError("no feather file in the snapshot")
    frames = [bess_view(feather.read_table(f).to_pandas(), f.stem) for f in files]
    view = pd.concat(frames)
    folder = out / "zen_bess"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "readings.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "zen_bess",
        {"readings.csv": (target, len(view))},
        dropped=[],
        pseudonymised=[],
        sampling={
            "method": "two of the twelve system files of the release (the two smallest utility systems); the others were not fetched",  # noqa: E501
            "systems": [f.stem for f in files],
            "rows_in": len(view),
        },
        source_snapshot=f"zen_bess/{SNAPSHOT}",
    )


KELMARSH_SIGNALS = {
    "Wind speed (m/s)": "wind_speed",
    "Wind direction (°)": "wind_direction",
    "Nacelle position (°)": "nacelle_position",
    "Power (kW)": "power_kw",
    "Reactive power (kvar)": "reactive_power",
    "Front bearing temperature (°C)": "front_bearing_temp",
    "Rear bearing temperature (°C)": "rear_bearing_temp",
    "Nacelle ambient temperature (°C)": "nacelle_ambient_temp",
    "Nacelle temperature (°C)": "nacelle_temp",
    "Gear oil temperature (°C)": "gear_oil_temp",
    "Generator bearing front temperature (°C)": "generator_front_temp",
    "Generator bearing rear temperature (°C)": "generator_rear_temp",
    "Rotor speed (RPM)": "rotor_rpm",
    "Generator RPM (RPM)": "generator_rpm",
    "Voltage L1 / U (V)": "voltage_l1",
    "Current L1 / U (A)": "current_l1",
}
KELMARSH_COLUMNS = ("timestamp", "turbine", *KELMARSH_SIGNALS.values())


def kelmarsh_view(raw: pd.DataFrame, turbine: str) -> pd.DataFrame:
    """Ten-minute SCADA signals of one wind turbine in time order.

    The export marks missing and erroneous values as NaN; they stay missing. Signals that a period
    lacks (the farm began operating in April 2016) are natural gaps and are kept as such.
    """
    need = ["Date and time", *KELMARSH_SIGNALS]
    missing = [c for c in need if c not in raw.columns]
    if missing:
        raise ViewError(f"columns not found: {missing}")
    out = pd.DataFrame({"timestamp": pd.to_datetime(raw["Date and time"], errors="coerce")})
    out["turbine"] = turbine
    for source, name in KELMARSH_SIGNALS.items():
        out[name] = pd.to_numeric(raw[source], errors="coerce")
    out = out[out["timestamp"].notna()]
    return out.sort_values("timestamp", kind="stable").reset_index(drop=True)


def _kelmarsh_header(lines: list[str]) -> tuple[int, list[str]]:
    import csv

    for index, line in enumerate(lines):
        if line.startswith("# Date and time"):
            return index, next(csv.reader([line[2:]]))
    raise ViewError("column header line not found")


def _build_kelmarsh(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    import re
    import tempfile

    from acquisition import extract_member, zip_members

    raw = root / "zen_kelmarsh" / SNAPSHOT / "raw" / "Kelmarsh_SCADA_2016_3082.zip"
    members = sorted(
        m["name"] for m in zip_members(raw) if re.match(r"Turbine_Data_Kelmarsh_\d+_", m["name"])
    )
    if not members:
        raise ViewError("no turbine data file in the archive")
    frames = []
    with tempfile.TemporaryDirectory() as scratch:
        for name in members:
            got = extract_member(raw, name, Path(scratch), max_bytes=1 << 30, max_ratio=200)
            with open(got["path"], "rb") as handle:
                head = [handle.readline().decode("utf-8").rstrip("\n") for _ in range(30)]
            skip, header = _kelmarsh_header(head)
            wanted = ["Date and time", *KELMARSH_SIGNALS]
            frame = pd.read_csv(got["path"], skiprows=skip + 1, names=header, usecols=wanted)
            frames.append(kelmarsh_view(frame, "T" + re.search(r"Kelmarsh_(\d+)_", name).group(1)))
            Path(got["path"]).unlink()
    view = pd.concat(frames)
    folder = out / "zen_kelmarsh"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "series.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "zen_kelmarsh",
        {"series.csv": (target, len(view))},
        dropped=["about 280 other SCADA columns", "status and event files"],
        pseudonymised=[],
        sampling={
            "method": "all ten-minute rows of the 2016 SCADA archive for the six turbines; later years were not fetched",  # noqa: E501
            "turbines": len(members),
            "rows_in": len(view),
        },
        source_snapshot=f"zen_kelmarsh/{SNAPSHOT}",
    )


PBDB_STRIDE = 10
PBDB_TEXT = (
    "accepted_rank", "phylum", "class", "order", "family", "early_interval", "late_interval", "cc",
    "state", "latlng_basis", "geogscale", "formation", "geological_group", "lithology1",
    "lithification1", "environment", "taxon_environment", "motility", "life_habit", "diet",
    "collection_type", "tectonic_setting",
)  # fmt: skip
PBDB_NUMBER = (
    "max_ma", "min_ma", "lng", "lat", "paleolng", "paleolat", "altitude_value", "ref_pubyr",
)  # fmt: skip
PBDB_COLUMNS = ("occurrence_no", *PBDB_TEXT, *PBDB_NUMBER)


def pbdb_occurrence_view(raw: pd.DataFrame) -> pd.DataFrame:
    """Fossil occurrences of the Paleobiology Database: taxonomy, age, place, rock and ecology.

    Categorical columns stay text and numeric columns numbers (unreadable values become missing).
    Names of contributors, free-text comments and identifier columns are not kept. A file that lacks
    one of the columns is an error.
    """
    missing = [c for c in PBDB_COLUMNS if c not in raw.columns]
    if missing:
        raise ViewError(f"columns not found: {missing}")
    out = pd.DataFrame({"occurrence_no": pd.to_numeric(raw["occurrence_no"], errors="coerce")})
    for column in PBDB_TEXT:
        text = raw[column].astype("string").str.strip()
        out[column] = text.mask(text == "")
    for column in PBDB_NUMBER:
        out[column] = pd.to_numeric(raw[column], errors="coerce")
    return out.sort_values("occurrence_no", kind="stable").reset_index(drop=True)


def _build_pbdb(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    import tempfile

    import parquet_reader as pr
    from acquisition import extract_member, zip_members

    raw = root / "zen_pbdb" / SNAPSHOT / "raw" / "pbdb_parquet.zip"
    members = [m for m in zip_members(raw) if m["name"].endswith(".parquet")]
    if len(members) != 1:
        raise ViewError(f"expected one Parquet member, found {len(members)}")
    folder = out / "zen_pbdb"
    folder.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as scratch:
        got = extract_member(
            raw, members[0]["name"], Path(scratch), max_bytes=1 << 30, max_ratio=200
        )
        names = [c["name"] for c in pr.inspect(got["path"])["columns"]]
        absent = [c for c in PBDB_COLUMNS if c not in names]
        if absent:
            raise ViewError(f"columns not found: {absent}")
        frame, record = pr.read_sample(
            got["path"], columns=list(PBDB_COLUMNS), max_rows=10**7, stride=PBDB_STRIDE
        )
    view = pbdb_occurrence_view(frame)
    target = folder / "occurrences.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "zen_pbdb",
        {"occurrences.csv": (target, len(view))},
        dropped=[
            "contributor and enterer names",
            "free-text comments",
            "identifier columns",
            "image and reference text",
        ],
        pseudonymised=[],
        sampling={
            "method": f"one row in {PBDB_STRIDE} of the occurrence table in file order (the order of entry), not random",  # noqa: E501
            "stride": PBDB_STRIDE,
            "rows_read": record["rows_read"],
            "rows_kept": record["rows_kept"],
            "source_rows": record["source_rows"],
            "truncated": record["truncated"],
            "member": members[0]["name"],
        },
        source_snapshot=f"zen_pbdb/{SNAPSHOT}",
    )


RETAIL_COLUMNS = (
    "timestamp", "invoice", "stock_code", "quantity", "unit_price", "line_value", "customer",
    "country", "cancellation",
)  # fmt: skip


def retail_view(raw: pd.DataFrame) -> pd.DataFrame:
    """Invoice lines of an online retailer: time, salted invoice and customer, item, price.

    A cancellation is an invoice whose number starts with C; its negative quantities are kept as
    published. The product description (free text) is not kept. Unreadable numbers become missing.
    """
    for column in (
        "InvoiceNo",
        "StockCode",
        "Quantity",
        "InvoiceDate",
        "UnitPrice",
        "CustomerID",
        "Country",
    ):
        if column not in raw.columns:
            raise ViewError(f"column {column!r} not found")
    quantity = pd.to_numeric(raw["Quantity"], errors="coerce")
    price = pd.to_numeric(raw["UnitPrice"], errors="coerce")
    customer = pd.to_numeric(raw["CustomerID"], errors="coerce").map(
        lambda v: pseudonym(str(int(v))) if pd.notna(v) else None
    )
    out = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                raw["InvoiceDate"], format="%m/%d/%Y %H:%M", errors="coerce"
            ),
            "invoice": raw["InvoiceNo"].astype(str).map(pseudonym),
            "stock_code": raw["StockCode"].astype(str),
            "quantity": quantity,
            "unit_price": price,
            "line_value": quantity * price,
            "customer": customer,
            "country": raw["Country"],
            "cancellation": raw["InvoiceNo"].astype(str).str.startswith("C"),
        }
    )
    return out.sort_values(["timestamp", "invoice"], kind="stable").reset_index(drop=True)


def _build_retail(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    raw = pd.read_csv(root.parent / "uci_wave2" / "352.csv", dtype=str, low_memory=False)
    view = retail_view(raw)
    folder = out / "uci_online_retail"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "lines.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "uci_online_retail",
        {"lines.csv": (target, len(view))},
        dropped=["product description (free text)"],
        pseudonymised=["invoice", "customer"],
        sampling={
            "rows_in": len(raw),
            "cancellations": int(view["cancellation"].sum()),
            "rows_without_customer": int(view["customer"].isna().sum()),
        },
        salt_label=SALT,
        source_snapshot="uci:352 (repository file pinned by checksum)",
    )


SLURM_MODULO = 20
SLURM_COLUMNS = (
    "jobid",
    "state",
    "account",
    "user",
    "partition",
    "submit",
    "start",
    "end",
    "timelimit",
    "elapsed",
    "allocmem",
    "alloccpus",
    "allocgpus",
    "wait_s",
)


def slurm_view(raw: pd.DataFrame, keep_modulo: int | None = None) -> pd.DataFrame:
    """Scheduler job records without host names, sampled by job id, with the waiting time derived.

    User and account names are the producer's own pseudonyms and are kept as published. A job
    that never started has no waiting time. Failed, cancelled and timed-out jobs stay as written.
    """
    modulo = SLURM_MODULO if keep_modulo is None else keep_modulo
    needed = [c for c in SLURM_COLUMNS if c != "wait_s"]
    if not all(c in raw.columns for c in needed):
        raise ViewError(f"job columns not found in {list(raw.columns)[:6]}")
    frame = raw[needed].copy()
    frame = frame[pd.to_numeric(frame["jobid"]) % modulo == 0]
    for column in ("submit", "start", "end", "timelimit", "elapsed", "allocmem", "alloccpus"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["wait_s"] = frame["start"] - frame["submit"]
    frame = frame.sort_values(["submit", "jobid"])
    return frame.reset_index(drop=True)


def _build_slurm(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    import tarfile

    frames = []
    for archive in sorted((root / "slurm_ccin2p3" / SNAPSHOT / "raw").glob("*.tsv.tar.gz")):
        with tarfile.open(archive) as tar:
            member = next(m for m in tar.getmembers() if m.isfile())
            raw = pd.read_csv(tar.extractfile(member), sep="\t", dtype=str)
        frames.append(slurm_view(raw))
    table = pd.concat(frames).sort_values(["submit", "jobid"])
    folder = out / "slurm_ccin2p3"
    folder.mkdir(parents=True, exist_ok=True)
    table.to_csv(folder / "jobs.csv", index=False)
    _record(
        manifest,
        "slurm_ccin2p3",
        {"jobs.csv": (folder / "jobs.csv", len(table))},
        dropped=[
            "hostnames",
            "eligible",
            "maxrss",
            "totalcpu",
            "started",
            "maxdiskwrite",
            "nsteps",
            "el9",
        ],
        pseudonymised=[],
        sampling=f"jobs with job id % {SLURM_MODULO} == 0, by submit time",  # noqa: E501
        source_snapshot=f"slurm_ccin2p3/{SNAPSHOT}",
        notes="user and account names are the producer's pseudonyms",
    )


BUILD_STEPS = (
    _build_openalex,
    _build_monash,
    _build_faers,
    _build_loghub,
    _build_food,
    _build_stack,
    _build_ocds,
    _build_bikeshare,
    _build_slurm,
    _build_clinicaltrials,
    _build_crossref,
    _build_borg,
    _build_panels,
    _build_tables,
    _build_surf,
    _build_fugaku,
    _build_metropt,
    _build_openlibrary,
    _build_aegis,
    _build_clue,
    _build_xes,
    _build_csv_events,
    _build_met,
    _build_ea,
    _build_dvf,
    _build_ppd,
    _build_retail,
    _build_pbdb,
    _build_kelmarsh,
    _build_wikidata,
    _build_bess,
    _build_care,
    _build_nvd,
    _build_flat,
    _build_series,
    _build_ukspend,
)


def build(root: Path, out: Path) -> dict[str, Any]:
    """Write every view and return the manifest (checksums, rows, dropped fields)."""
    manifest: dict[str, Any] = {}
    for step in BUILD_STEPS:
        step(root, out, manifest)
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
