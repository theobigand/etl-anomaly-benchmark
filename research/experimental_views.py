"""Experimental views of acquired data: minimised, pseudonymised and deterministic (T434-T437).

A view keeps what the anomaly protocols need and drops personal or free-text fields. Pseudonyms are
salted hashes: they keep joins working, they do not make the data anonymous. Views are written to
``data/experimental`` (not committed); their checksums and parameters go in a tracked manifest.
"""

from __future__ import annotations

import hashlib
import io
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

#: Formula One race database (Jolpica, CC BY-NC-SA 4.0): public persons are reduced to identifiers
JOLPICA_TABLE_SETS: dict[str, dict[str, Any]] = {
    "jolpica_f1": {
        "snapshot": "2026-11-22",
        "archive": {"file": "jolpica-f1-csv.zip", "prefix": ""},
        "sep": ",",
        "quote_none": False,
        "dropped": ["driver names, birth dates, nationalities and wikipedia links", "wikipedia links and api identifiers of every table"],  # noqa: E501
        "tables": {
            "formula_one_driver": {"keep": ["id", "permanent_car_number"]},
            "formula_one_circuit": {"keep": ["id", "altitude", "country_code", "latitude", "longitude"]},  # noqa: E501
            "formula_one_season": {"keep": ["id", "championship_system_id", "year"]},
            "formula_one_round": {"keep": ["id", "circuit_id", "date", "is_cancelled", "number", "race_number", "season_id"]},  # noqa: E501
            "formula_one_session": {"keep": ["id", "completed_laps", "has_time_data", "is_cancelled", "number", "point_system_id", "round_id", "scheduled_laps", "timestamp", "type"]},  # noqa: E501
            "formula_one_team": {"keep": ["id", "base_team_id", "country_code", "name", "nationality"]},  # noqa: E501
            "formula_one_teamdriver": {"keep": ["id", "driver_id", "role", "season_id", "team_id"]},
            "formula_one_roundentry": {"keep": ["id", "car_number", "round_id", "team_driver_id"]},
            "formula_one_sessionentry": {"keep": ["id", "detail", "fastest_lap_rank", "grid", "is_classified", "is_eligible_for_points", "laps_completed", "points", "position", "round_entry_id", "session_id", "status", "time"]},  # noqa: E501
            "formula_one_lap": {"keep": ["id", "average_speed", "is_deleted", "is_entry_fastest_lap", "number", "position", "session_entry_id", "time"]},  # noqa: E501
            "formula_one_pitstop": {"keep": ["id", "duration", "lap_id", "local_timestamp", "number", "session_entry_id"]},  # noqa: E501
        },
        "relations": [
            ["formula_one_round", "season_id", "formula_one_season", "id"],
            ["formula_one_round", "circuit_id", "formula_one_circuit", "id"],
            ["formula_one_session", "round_id", "formula_one_round", "id"],
            ["formula_one_teamdriver", "driver_id", "formula_one_driver", "id"],
            ["formula_one_teamdriver", "team_id", "formula_one_team", "id"],
            ["formula_one_teamdriver", "season_id", "formula_one_season", "id"],
            ["formula_one_roundentry", "round_id", "formula_one_round", "id"],
            ["formula_one_roundentry", "team_driver_id", "formula_one_teamdriver", "id"],
            ["formula_one_sessionentry", "session_id", "formula_one_session", "id"],
            ["formula_one_sessionentry", "round_entry_id", "formula_one_roundentry", "id"],
            ["formula_one_lap", "session_entry_id", "formula_one_sessionentry", "id"],
            ["formula_one_pitstop", "session_entry_id", "formula_one_sessionentry", "id"],
            ["formula_one_pitstop", "lap_id", "formula_one_lap", "id"],
        ],
    },
}  # fmt: skip
TABLE_SETS.update(JOLPICA_TABLE_SETS)

#: USDA FoodData Central SR Legacy (CC0): laboratory food composition tables
USDA_TABLE_SETS: dict[str, dict[str, Any]] = {
    "usda_fdc_sr_legacy": {
        "snapshot": "2026-11-22",
        "archive": {"file": "sr_legacy_food_csv_2018-04.zip", "prefix": "FoodData_Central_sr_legacy_food_csv_2018-04/"},  # noqa: E501
        "sep": ",",
        "quote_none": False,
        "dropped": ["update logs, conversion factors and attribute tables", "footnotes and acquisition years"],  # noqa: E501
        "tables": {
            "food": {"keep": ["fdc_id", "data_type", "description", "food_category_id", "publication_date"]},  # noqa: E501
            "food_category": {"keep": ["id", "code", "description"]},
            "food_nutrient": {"keep": ["id", "fdc_id", "nutrient_id", "amount", "data_points", "derivation_id", "min", "max", "median"]},  # noqa: E501
            "nutrient": {"keep": ["id", "name", "unit_name", "nutrient_nbr", "rank"]},
            "food_nutrient_derivation": {"keep": ["id", "code", "description"]},
            "food_portion": {"keep": ["id", "fdc_id", "seq_num", "amount", "measure_unit_id", "gram_weight", "data_points"]},  # noqa: E501
            "measure_unit": {"keep": ["id", "name"]},
        },
        "relations": [
            ["food", "food_category_id", "food_category", "id"],
            ["food_nutrient", "fdc_id", "food", "fdc_id"],
            ["food_nutrient", "nutrient_id", "nutrient", "id"],
            ["food_nutrient", "derivation_id", "food_nutrient_derivation", "id"],
            ["food_portion", "fdc_id", "food", "fdc_id"],
            ["food_portion", "measure_unit_id", "measure_unit", "id"],
        ],
    },
}  # fmt: skip
TABLE_SETS.update(USDA_TABLE_SETS)

#: UK DfT STATS19 road safety open data of 2023 (OGL v3.0): coded categorical records
STATS19_TABLE_SETS: dict[str, dict[str, Any]] = {
    "dft_stats19_2023": {
        "snapshot": "2026-11-22",
        "sep": ",",
        "quote_none": False,
        "dropped": ["police collision reference numbers", "home-area codes (LSOA) of drivers and casualties"],  # noqa: E501
        "tables": {
            "collision": {"keep": ["collision_index", "collision_year", "location_easting_osgr", "location_northing_osgr", "longitude", "latitude", "police_force", "collision_severity", "number_of_vehicles", "number_of_casualties", "date", "day_of_week", "time", "local_authority_district", "local_authority_ons_district", "local_authority_highway", "local_authority_highway_current", "first_road_class", "first_road_number", "road_type", "speed_limit", "junction_detail_historic", "junction_detail", "junction_control", "second_road_class", "second_road_number", "pedestrian_crossing_human_control_historic", "pedestrian_crossing_physical_facilities_historic", "pedestrian_crossing", "light_conditions", "weather_conditions", "road_surface_conditions", "special_conditions_at_site", "carriageway_hazards_historic", "carriageway_hazards", "urban_or_rural_area", "did_police_officer_attend_scene_of_accident", "trunk_road_flag", "lsoa_of_accident_location", "enhanced_severity_collision", "collision_injury_based", "collision_adjusted_severity_serious", "collision_adjusted_severity_slight"]},  # noqa: E501
            "vehicle": {"keep": ["collision_index", "collision_year", "vehicle_reference", "vehicle_type", "towing_and_articulation", "vehicle_manoeuvre_historic", "vehicle_manoeuvre", "vehicle_direction_from", "vehicle_direction_to", "vehicle_location_restricted_lane_historic", "vehicle_location_restricted_lane", "junction_location", "skidding_and_overturning", "hit_object_in_carriageway", "vehicle_leaving_carriageway", "hit_object_off_carriageway", "first_point_of_impact", "vehicle_left_hand_drive", "journey_purpose_of_driver_historic", "journey_purpose_of_driver", "sex_of_driver", "age_of_driver", "age_band_of_driver", "engine_capacity_cc", "propulsion_code", "age_of_vehicle", "generic_make_model", "driver_imd_decile", "escooter_flag", "driver_distance_banding"]},  # noqa: E501
            "casualty": {"keep": ["collision_index", "collision_year", "vehicle_reference", "casualty_reference", "casualty_class", "sex_of_casualty", "age_of_casualty", "age_band_of_casualty", "casualty_severity", "pedestrian_location", "pedestrian_movement", "car_passenger", "bus_or_coach_passenger", "pedestrian_road_maintenance_worker", "casualty_type", "casualty_imd_decile", "enhanced_casualty_severity", "casualty_injury_based", "casualty_adjusted_severity_serious", "casualty_adjusted_severity_slight", "casualty_distance_banding", "escooter_flag"]},  # noqa: E501
        },
        "relations": [
            ["vehicle", "collision_index", "collision", "collision_index"],
            ["casualty", "collision_index", "collision", "collision_index"],
        ],
    },
}  # fmt: skip
TABLE_SETS.update(STATS19_TABLE_SETS)


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
        snapshot = spec.get("snapshot", SNAPSHOT)
        raw = root / source / snapshot / "raw"
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
            source_snapshot=f"{source}/{snapshot}",
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


BACKBLAZE_SNAPSHOT = "2026-11-22"
BACKBLAZE_DAYS = 60
BACKBLAZE_MODULO = 8
BACKBLAZE_ID = ("date", "serial_number", "model", "capacity_bytes", "failure")


def backblaze_view(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Daily SMART snapshots of a deterministic subset of drives, one row per drive and day.

    A drive is kept for every day if the salted hash of its serial number falls in the sample
    (one in ``BACKBLAZE_MODULO``), so each kept drive keeps its whole series. The serial number is
    replaced by its pseudonym. ``failure`` is the publisher's flag that the drive failed that day.
    Attributes that a drive does not report stay missing.
    """
    frame = pd.concat(frames, ignore_index=True)
    missing = [c for c in BACKBLAZE_ID if c not in frame.columns]
    if missing:
        raise ViewError(f"columns not found: {missing}")
    frame = frame.assign(drive=frame["serial_number"].astype(str).map(pseudonym))
    frame = frame[frame["drive"].map(lambda d: int(d, 16) % BACKBLAZE_MODULO == 0)]
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame = frame[frame["date"].notna()]
    smart = sorted(c for c in frame.columns if c.startswith("smart_"))
    for column in ("capacity_bytes", "failure", *smart):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    ordered = frame[["date", "drive", "model", "capacity_bytes", "failure", *smart]]
    return ordered.sort_values(["drive", "date"]).reset_index(drop=True)


def _build_backblaze(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    import re
    import tempfile

    from acquisition import extract_member, zip_members

    raw = root / "backblaze_drive_stats" / BACKBLAZE_SNAPSHOT / "raw" / "data_2014.zip"
    days = sorted(
        m["name"]
        for m in zip_members(raw)
        if re.fullmatch(r"\d{4}/\d{4}-\d\d-\d\d\.csv", m["name"])
    )
    if not days:
        raise ViewError("no daily file in the archive")
    chosen = days[:BACKBLAZE_DAYS]
    frames = []
    with tempfile.TemporaryDirectory() as scratch:
        for name in chosen:
            got = extract_member(raw, name, Path(scratch), max_bytes=1 << 28, max_ratio=100)
            frames.append(pd.read_csv(got["path"], dtype=str))
            Path(got["path"]).unlink()
    view = backblaze_view(frames)
    folder = out / "backblaze_drive_stats"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "drive_days.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "backblaze_drive_stats",
        {"drive_days.csv": (target, len(view))},
        dropped=["serial numbers (replaced by a salted pseudonym)"],
        pseudonymised=["drive"],
        sampling={
            "method": f"the first {BACKBLAZE_DAYS} daily files of the 2014 archive, one drive in {BACKBLAZE_MODULO} chosen by the salted hash of the serial number, whole series kept",  # noqa: E501
            "days": [chosen[0], chosen[-1]],
            "day_files": len(chosen),
            "drives": int(view["drive"].nunique()),
            "failures": int(view["failure"].sum()),
        },
        salt_label=SALT,
        source_snapshot=f"backblaze_drive_stats/{BACKBLAZE_SNAPSHOT}",
    )


TLC_SNAPSHOT = "2026-11-22"
TLC_COLUMNS = (
    "vendorid", "tpep_pickup_datetime", "tpep_dropoff_datetime", "passenger_count", "trip_distance",
    "ratecodeid", "store_and_fwd_flag", "pulocationid", "dolocationid", "payment_type",
    "fare_amount", "extra", "mta_tax", "tip_amount", "tolls_amount", "improvement_surcharge",
    "total_amount", "congestion_surcharge", "airport_fee",
)  # fmt: skip
TLC_CODES = ("vendorid", "ratecodeid", "payment_type", "pulocationid", "dolocationid")


def taxi_trip_view(pages: list[pd.DataFrame]) -> pd.DataFrame:
    """Yellow taxi trips with their fare components in pickup order, every trip kept as published.

    Zero, negative and disputed fares, trips without passengers and unusual payment codes are
    baseline properties of the source and are not removed. Codes stay integers, amounts stay
    numbers, and unreadable values become missing. Rows with an unreadable pickup time are dropped.
    """
    frame = pd.concat(pages)
    missing = [c for c in TLC_COLUMNS if c not in frame.columns]
    if missing:
        raise ViewError(f"columns not found: {missing}")
    out = frame[list(TLC_COLUMNS)].copy()
    for column in ("tpep_pickup_datetime", "tpep_dropoff_datetime"):
        out[column] = pd.to_datetime(out[column], errors="coerce")
    out = out[out["tpep_pickup_datetime"].notna()]
    for column in TLC_CODES:
        out[column] = pd.to_numeric(out[column], errors="coerce").astype("Int64")
    numeric = [
        c
        for c in TLC_COLUMNS
        if c
        not in (*TLC_CODES, "tpep_pickup_datetime", "tpep_dropoff_datetime", "store_and_fwd_flag")
    ]
    for column in numeric:
        out[column] = pd.to_numeric(out[column], errors="coerce").astype("float64")
    out["store_and_fwd_flag"] = out["store_and_fwd_flag"].astype("string")
    return out.sort_values("tpep_pickup_datetime", kind="stable").reset_index(drop=True)


def _build_tlc(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    raw = root / "nyc_tlc_yellow" / TLC_SNAPSHOT / "raw"
    files = sorted(raw.glob("yellow_*.csv"))
    if not files:
        raise ViewError("no trip page in the snapshot")
    pages = [pd.read_csv(path, dtype=str) for path in files]
    view = taxi_trip_view(pages)
    days = view["tpep_pickup_datetime"].dt.date.astype(str).value_counts().sort_index()
    folder = out / "nyc_tlc_yellow"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "trips.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "nyc_tlc_yellow",
        {"trips.csv": (target, len(view))},
        dropped=[],
        pseudonymised=[],
        sampling={
            "method": "three complete pickup days (a Tuesday, a Saturday and a Sunday of March 2023) in stable row-id order, paged",  # noqa: E501
            "pages": [p.name for p in files],
            "rows_by_day": {d: int(n) for d, n in days.items()},
            "rows_read": int(sum(len(p) for p in pages)),
            "rows_without_pickup_time": int(sum(len(p) for p in pages) - len(view)),
            "zero_or_negative_totals": int((view["total_amount"] <= 0).sum()),
        },
        source_snapshot=f"nyc_tlc_yellow/{TLC_SNAPSHOT}",
    )


MAUDE_SNAPSHOT = "2026-11-22"
MAUDE_DROP_PREFIX = "manufacturer_contact_"
MAUDE_DROP = frozenset({"mdr_text"})


def _keys(node: Any) -> set[str]:
    """Every dictionary key at any depth of a nested record."""
    if isinstance(node, dict):
        return set(node) | {k for v in node.values() for k in _keys(v)}
    if isinstance(node, list):
        return {k for v in node for k in _keys(v)}
    return set()


def maude_view(pages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int, list[str]]:
    """Device adverse event reports in report-number order, one per number, as nested records.

    The manufacturer contact person's fields (every key that starts with ``manufacturer_contact_``)
    and the free-text narratives (``mdr_text``) are removed at every depth. Returns the records,
    the number of repeated report numbers that were skipped and the dropped key names.
    """
    unique: dict[str, dict[str, Any]] = {}
    repeated = 0
    for page in pages:
        for record in page["results"]:
            number = record["report_number"]
            if number in unique:
                repeated += 1
            else:
                unique[number] = record
    contact = {
        key
        for record in unique.values()
        for key in _keys(record)
        if key.startswith(MAUDE_DROP_PREFIX)
    }
    drop = frozenset(contact) | MAUDE_DROP
    view = nested_view(list(unique.values()), drop, lambda r: r["report_number"])
    return view, repeated, sorted(drop)


def _build_maude(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    raw = root / "openfda_device_event" / MAUDE_SNAPSHOT / "raw"
    files = sorted(raw.glob("maude_*.json"))
    if not files:
        raise ViewError("no report page in the snapshot")
    pages = [json.loads(path.read_text(encoding="utf-8")) for path in files]
    view, repeated, dropped = maude_view(pages)
    folder = out / "openfda_device_event"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "reports.jsonl"
    target.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in view))
    _record(
        manifest,
        "openfda_device_event",
        {"reports.jsonl": (target, len(view))},
        dropped=["manufacturer contact person fields", "free-text narratives (mdr_text)"],
        pseudonymised=[],
        sampling={
            "method": "every report received on one day (2023-03-01), sorted by report number, pages of 500",  # noqa: E501
            "pages": [p.name for p in files],
            "reports": len(view),
            "repeated_reports": repeated,
            "dropped_keys": dropped,
        },
        source_snapshot=f"openfda_device_event/{MAUDE_SNAPSHOT}",
    )


UNISG_SNAPSHOT = "2026-11-22"
UNISG_LOG = "training_tenhertz_log_20230411-095748.txt"
UNISG_HEAD = (
    "timestamp",
    "station",
    "current_state",
    "current_task",
    "current_task_duration",
    "current_sub_task",
)
UNISG_ACTIVITY_COLUMNS = (
    "process_instance", "process_key", "process_state", "activity_name", "activity_type",
    "start_time", "end_time", "duration_ms", "canceled",
)  # fmt: skip


def unisg_sensor_view(messages: list[dict[str, Any]]) -> pd.DataFrame:
    """Ten-hertz station messages of the smart factory model, one row per message, in time order.

    Every station reports its own sensors, so the columns of other stations are missing by design.
    The message identifier is dropped; times and numbers that cannot be read become missing and
    messages without a readable time are dropped.
    """
    frame = pd.DataFrame(messages)
    for column in UNISG_HEAD:
        if column not in frame.columns:
            raise ViewError(f"column {column!r} not found")
    frame = frame.drop(columns=[c for c in ("id",) if c in frame.columns])
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], errors="coerce")
    frame = frame[frame["timestamp"].notna()]
    numeric = sorted(set(frame.columns) - set(UNISG_HEAD))
    for column in numeric:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["current_task_duration"] = pd.to_numeric(frame["current_task_duration"], errors="coerce")
    ordered = frame[[*UNISG_HEAD, *numeric]]
    return ordered.sort_values(["timestamp", "station"], kind="stable").reset_index(drop=True)


def unisg_activity_view(
    activities: list[dict[str, Any]], processes: list[dict[str, Any]]
) -> pd.DataFrame:
    """Activity instances of the workflow engine with the final state of their process instance.

    Rows are kept in the order of the start time. An activity whose process instance is not in the
    process file keeps a missing process state.
    """
    states = {p["id"]: p.get("state") for p in processes}
    rows = [
        {
            "process_instance": a["processInstanceId"],
            "process_key": a["processDefinitionKey"],
            "process_state": states.get(a["processInstanceId"]),
            "activity_name": a["activityName"],
            "activity_type": a["activityType"],
            "start_time": a["startTime"],
            "end_time": a["endTime"],
            "duration_ms": a["durationInMillis"],
            "canceled": a["canceled"],
        }
        for a in activities
    ]
    frame = pd.DataFrame(rows, columns=list(UNISG_ACTIVITY_COLUMNS))
    frame["start_time"] = pd.to_datetime(frame["start_time"], errors="coerce", utc=True)
    frame["end_time"] = pd.to_datetime(frame["end_time"], errors="coerce", utc=True)
    frame["duration_ms"] = pd.to_numeric(frame["duration_ms"], errors="coerce")
    frame["canceled"] = frame["canceled"].astype(bool)
    return frame.sort_values(["start_time", "process_instance"], kind="stable").reset_index(
        drop=True
    )


def _build_unisg(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    raw = root / "zen_unisg_factory" / UNISG_SNAPSHOT / "raw"
    messages, bad = [], 0
    for line in (raw / UNISG_LOG).read_bytes().decode("utf-8").splitlines():
        try:
            messages.append(json.loads(line))
        except ValueError:
            bad += 1
    activities = json.loads((raw / "camunda-activity.json").read_bytes())
    processes = json.loads((raw / "camunda-process.json").read_bytes())
    sensors = unisg_sensor_view(messages)
    events = unisg_activity_view(activities, processes)
    folder = out / "zen_unisg_factory"
    folder.mkdir(parents=True, exist_ok=True)
    sensor_file, event_file = folder / "sensors.csv", folder / "activities.csv"
    sensors.to_csv(sensor_file, index=False)
    events.to_csv(event_file, index=False)
    _record(
        manifest,
        "zen_unisg_factory",
        {"sensors.csv": (sensor_file, len(sensors)), "activities.csv": (event_file, len(events))},
        dropped=["message identifiers"],
        pseudonymised=[],
        sampling={
            "method": "the 36-minute 10 Hz training log of 2023-04-11 and the whole Camunda activity and process logs of 2022-09 to 2023-04; the test log was not fetched",  # noqa: E501
            "messages": len(messages),
            "unreadable_lines": bad,
            "stations": sorted(set(sensors["station"])),
            "activity_instances": len(events),
            "process_instances": len(processes),
        },
        source_snapshot=f"zen_unisg_factory/{UNISG_SNAPSHOT}",
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


def _build_care_farm(
    root: Path, out: Path, manifest: dict[str, Any], source: str, method: str
) -> None:
    import io

    raw = root / source / CARE_SNAPSHOT / "raw"
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
    folder = out / source
    folder.mkdir(parents=True, exist_ok=True)
    series, events = folder / "series.csv", folder / "events.csv"
    view.to_csv(series, index=False)
    info.sort_values("event_id").to_csv(events, index=False)
    _record(
        manifest,
        source,
        {"series.csv": (series, len(view)), "events.csv": (events, len(info))},
        dropped=["minimum, maximum and standard-deviation columns of every sensor"],
        pseudonymised=[],
        sampling={
            "method": method,
            "datasets": ids,
            "anomaly_datasets_in_view": int(
                info.loc[info["in_view"] & (info["event_label"] == "anomaly"), "event_id"].count()
            ),  # noqa: E501
            "rows_in": len(view),
        },
        source_snapshot=f"{source}/{CARE_SNAPSHOT}",
    )


def _build_care(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    _build_care_farm(
        root,
        out,
        manifest,
        "zen_care_wind_b",
        "five of the fifteen datasets of Wind Farm B (three with a labelled anomaly event, two normal); Wind Farm A and C and ten datasets of B were not fetched",  # noqa: E501
    )


def _build_care_a(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    _build_care_farm(
        root,
        out,
        manifest,
        "zen_care_wind_a",
        "eight of the 22 datasets of Wind Farm A (four with a labelled fault event, four normal); Wind Farm B and C and fourteen datasets of A were not fetched",  # noqa: E501
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


PBDB_REL_OCC = (
    "occurrence_no", "collection_no", "accepted_no", "reference_no", "accepted_rank",
    "early_interval", "max_ma", "min_ma",
)  # fmt: skip
PBDB_REL_TAXA = (
    "taxon_no", "orig_no", "accepted_no", "parent_no", "taxon_rank", "taxon_name", "is_extant",
    "n_occs", "reference_no", "firstapp_max_ma", "firstapp_min_ma", "lastapp_max_ma", "lastapp_min_ma",  # noqa: E501
)  # fmt: skip
PBDB_REL_RELATIONS = (
    ("occurrences", "accepted_no", "taxa", "taxon_no"),
    ("taxa", "parent_no", "taxa", "taxon_no"),
)


def taxon_closure(taxa: pd.DataFrame, needed: set[int]) -> tuple[pd.DataFrame, int]:
    """The taxa named by the needed identifiers and every ancestor reachable by ``parent_no``.

    Returns the taxa in identifier order and the number of ancestors that the full table itself does
    not contain (identifiers that are absent from the source, not from the sample). A taxon is
    followed once, so a cycle in the source ends the walk. ``taxon_no`` must be unique.
    """
    parent = taxa.set_index("taxon_no")["parent_no"]
    known = set(parent.index)
    seen: set[int] = set()
    missing: set[int] = set()
    frontier = {n for n in needed if n in known}
    while frontier:
        seen |= frontier
        step = {int(x) for x in parent.reindex(sorted(frontier)).dropna()}
        missing |= step - known
        frontier = (step & known) - seen
    kept = taxa[taxa["taxon_no"].isin(seen)].sort_values("taxon_no")
    return kept.reset_index(drop=True), len(missing)


def _pbdb_member(
    raw: Path, scratch: Path, columns: tuple[str, ...], stride: int
) -> tuple[pd.DataFrame, dict[str, Any]]:
    import parquet_reader as pr
    from acquisition import extract_member, zip_members

    members = [m for m in zip_members(raw) if m["name"].endswith(".parquet")]
    if len(members) != 1:
        raise ViewError(f"expected one Parquet member, found {len(members)}")
    got = extract_member(raw, members[0]["name"], scratch, max_bytes=1 << 30, max_ratio=200)
    absent = [
        c for c in columns if c not in [c["name"] for c in pr.inspect(got["path"])["columns"]]
    ]
    if absent:
        raise ViewError(f"columns not found: {absent}")
    return pr.read_sample(got["path"], columns=list(columns), max_rows=10**7, stride=stride)


def _build_pbdb_relational(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    import tempfile

    base = root / "zen_pbdb" / SNAPSHOT / "raw"
    with tempfile.TemporaryDirectory() as scratch:
        occ, record = _pbdb_member(
            base / "pbdb_parquet.zip", Path(scratch), PBDB_REL_OCC, PBDB_STRIDE
        )
        taxa, _ = _pbdb_member(base / "pbdb_taxa_parquet.zip", Path(scratch), PBDB_REL_TAXA, 1)
    for column in (
        "occurrence_no",
        "collection_no",
        "accepted_no",
        "reference_no",
        "max_ma",
        "min_ma",
    ):
        occ[column] = pd.to_numeric(occ[column], errors="coerce")
    for column in ("taxon_no", "orig_no", "accepted_no", "parent_no", "n_occs", "reference_no"):
        taxa[column] = pd.to_numeric(taxa[column], errors="coerce")
    occ = occ.sort_values("occurrence_no").reset_index(drop=True)
    needed = {int(n) for n in occ["accepted_no"].dropna()}
    kept, absent_parents = taxon_closure(taxa, needed)
    folder = out / "zen_pbdb_relational"
    folder.mkdir(parents=True, exist_ok=True)
    occ_file, taxa_file = folder / "occurrences.csv", folder / "taxa.csv"
    occ.to_csv(occ_file, index=False)
    kept.to_csv(taxa_file, index=False)
    known = set(taxa["taxon_no"].dropna().astype(int))
    _record(
        manifest,
        "zen_pbdb_relational",
        {"occurrences.csv": (occ_file, len(occ)), "taxa.csv": (taxa_file, len(kept))},
        dropped=["contributor names", "free text", "all other columns of both tables"],
        pseudonymised=[],
        sampling={
            "method": f"one occurrence in {PBDB_STRIDE} in file order (the C2a sample) with the taxa they name and every ancestor of those taxa; the other taxa are not included",  # noqa: E501
            "relations": [list(r) for r in PBDB_REL_RELATIONS],
            "occurrences_rows_read": record["rows_read"],
            "occurrences_without_taxon": int(occ["accepted_no"].isna().sum()),
            "occurrences_with_unknown_taxon": int(sum(1 for n in needed if n not in known)),
            "ancestors_absent_from_source": absent_parents,
            "taxa_in_source": len(taxa),
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


AQS_SNAPSHOT = "2026-11-22"
AQS_YEARS = (2022, 2023)
AQS_MONITORS = 12
AQS_COLUMNS = (
    "State Code", "County Code", "Site Num", "POC", "Latitude", "Longitude", "Date GMT",
    "Time GMT", "Sample Measurement", "Units of Measure", "MDL", "Qualifier", "Method Code",
)  # fmt: skip
AQS_UNITS = "Parts per million"


def _aqs_id(chunk: pd.DataFrame) -> pd.Series:
    return (
        chunk["State Code"]
        + "-"
        + chunk["County Code"]
        + "-"
        + chunk["Site Num"]
        + "-"
        + chunk["POC"]
    )


def aqs_pick(monitors: list[str], count: int) -> list[str]:
    """An even stride over the sorted monitor list, never a choice by value."""
    ordered = sorted(monitors)
    return ordered[:: max(1, len(ordered) // count)][:count]


def aqs_hourly_view(
    chunks: list[pd.DataFrame], monitors: list[str]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Hourly ozone of the chosen monitors in UTC, by monitor then time, and the monitor table.

    The measurement, its detection limit, the method code and the qualifier flag are kept as
    published; the unit must be parts per million. Rows with an unreadable time are dropped and
    counted (``attrs["rows_dropped"]``), never guessed.
    """
    parts, places = [], []
    for chunk in chunks:
        if set(chunk["Units of Measure"].dropna()) - {AQS_UNITS}:
            raise ViewError("unexpected unit of measure")
        chunk = chunk.assign(monitor=_aqs_id(chunk))
        chunk = chunk[chunk["monitor"].isin(monitors)]
        stamps = pd.to_datetime(
            chunk["Date GMT"] + " " + chunk["Time GMT"], format="%Y-%m-%d %H:%M", errors="coerce"
        )
        parts.append(
            pd.DataFrame(
                {
                    "monitor": chunk["monitor"],
                    "timestamp": stamps,
                    "ozone_ppm": pd.to_numeric(chunk["Sample Measurement"], errors="coerce"),
                    "mdl_ppm": pd.to_numeric(chunk["MDL"], errors="coerce"),
                    "method_code": chunk["Method Code"].astype("string"),
                    "qualifier": chunk["Qualifier"].astype("string"),
                }
            )
        )
        places.append(chunk[["monitor", "Latitude", "Longitude"]].drop_duplicates())
    table = pd.concat(parts)
    kept = table[table["timestamp"].notna()].sort_values(["monitor", "timestamp"])
    kept = kept.reset_index(drop=True)
    kept.attrs = {"rows_dropped": int(len(table) - len(kept))}
    sites = pd.concat(places).drop_duplicates("monitor").sort_values("monitor")
    sites = sites.rename(columns={"Latitude": "latitude", "Longitude": "longitude"})
    return kept, sites.reset_index(drop=True)


def _aqs_chunks(path: Path, columns: tuple[str, ...]) -> Any:
    import zipfile

    with zipfile.ZipFile(path) as archive, archive.open(archive.namelist()[0]) as member:
        yield from pd.read_csv(member, usecols=list(columns), dtype=str, chunksize=500_000)


def _build_aqs(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    raw = root / "epa_aqs_ozone_hourly" / AQS_SNAPSHOT / "raw"
    paths = [raw / f"hourly_44201_{year}.zip" for year in AQS_YEARS]
    id_columns = AQS_COLUMNS[:4]
    present = [
        set().union(*(set(_aqs_id(c)) for c in _aqs_chunks(path, id_columns))) for path in paths
    ]
    common = sorted(set.intersection(*present))
    chosen = aqs_pick(common, AQS_MONITORS)
    frames, sites = [], []
    for path in paths:
        frame, place = aqs_hourly_view(_aqs_chunks(path, AQS_COLUMNS), chosen)
        frames.append(frame)
        sites.append(place)
    view = pd.concat(frames).sort_values(["monitor", "timestamp"])
    view = view.reset_index(drop=True)
    places = pd.concat(sites).drop_duplicates("monitor").sort_values("monitor")
    folder = out / "epa_aqs_ozone_hourly"
    folder.mkdir(parents=True, exist_ok=True)
    series, monitors = folder / "ozone.csv", folder / "monitors.csv"
    view.to_csv(series, index=False)
    places.to_csv(monitors, index=False)
    per = view.groupby("monitor")["timestamp"].agg(["min", "max", "count"])
    _record(
        manifest,
        "epa_aqs_ozone_hourly",
        {"ozone.csv": (series, len(view)), "monitors.csv": (monitors, len(places))},
        dropped=["state and county names, datum, date of last change, local time"],
        pseudonymised=[],
        sampling={
            "method": "an even stride over the sorted ids of the monitors that report in both years",  # noqa: E501
            "monitors_in_both_years": len(common),
            "monitors": len(chosen),
            "years": list(AQS_YEARS),
            "rows_dropped": int(sum(f.attrs["rows_dropped"] for f in frames)),
            "missing_value_share": round(float(view["ozone_ppm"].isna().mean()), 4),
            "flagged_share": round(float(view["qualifier"].notna().mean()), 4),
            "first_by_monitor": {m: str(v) for m, v in per["min"].items()},
            "last_by_monitor": {m: str(v) for m, v in per["max"].items()},
            "hours_by_monitor": {m: int(v) for m, v in per["count"].items()},
        },
        source_snapshot=f"epa_aqs_ozone_hourly/{AQS_SNAPSHOT}",
    )


USGS_SNAPSHOT = "2026-11-22"
USGS_COLUMNS = ("monitoring_location_id", "time", "value", "approval_status", "qualifier")


def usgs_continuous_view(pages: list[dict[str, Any]]) -> pd.DataFrame:
    """Continuous discharge values in UTC by monitoring location then time.

    Geometry, row identifiers, the series identifier and the publisher's revision time are
    dropped; the value, the approval status and the qualifier stay as published. Repeated
    (location, time) pairs are kept once and counted (``attrs["duplicates"]``), the unit must be
    cubic feet per second.
    """
    rows = []
    for page in pages:
        for feature in page["features"]:
            props = feature["properties"]
            if props["unit_of_measure"] != "ft^3/s":
                raise ViewError("unexpected unit of measure")
            rows.append({c: props[c] for c in USGS_COLUMNS})
    frame = pd.DataFrame(rows, columns=list(USGS_COLUMNS))
    frame["timestamp"] = pd.to_datetime(frame.pop("time"), utc=True, errors="coerce")
    frame["timestamp"] = frame["timestamp"].dt.tz_localize(None)
    frame["discharge_cfs"] = pd.to_numeric(frame.pop("value"), errors="coerce")
    frame = frame.rename(columns={"monitoring_location_id": "monitor"})
    frame = frame[frame["timestamp"].notna()]
    unique = frame.drop_duplicates(["monitor", "timestamp"])
    ordered = unique.sort_values(["monitor", "timestamp"])
    ordered = ordered[["monitor", "timestamp", "discharge_cfs", "approval_status", "qualifier"]]
    ordered = ordered.reset_index(drop=True)
    ordered.attrs = {"duplicates": int(len(frame) - len(unique))}
    return ordered


def _build_usgs(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    raw = root / "usgs_continuous_discharge" / USGS_SNAPSHOT / "raw"
    files = sorted(raw.glob("discharge_*_p*.json"))
    if not files:
        raise ViewError("no discharge page in the snapshot")
    view = usgs_continuous_view([json.loads(p.read_text()) for p in files])
    folder = out / "usgs_continuous_discharge"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "discharge.csv"
    view.to_csv(target, index=False)
    per = view.groupby("monitor")["timestamp"]
    step = per.apply(lambda s: s.diff().dt.total_seconds().div(60).median())
    _record(
        manifest,
        "usgs_continuous_discharge",
        {"discharge.csv": (target, len(view))},
        dropped=["geometry", "row and time series identifiers", "last_modified", "method_category"],
        pseudonymised=[],
        sampling={
            "method": "four fixed monitoring locations, 2022-01-01 to 2023-12-31, pages of 50,000 values",  # noqa: E501
            "pages": [p.name for p in files],
            "duplicates": view.attrs["duplicates"],
            "missing_value_share": round(float(view["discharge_cfs"].isna().mean()), 4),
            "provisional_share": round(float((view["approval_status"] != "Approved").mean()), 4),
            "median_step_minutes": {m: float(v) for m, v in step.items()},
            "first_by_monitor": {m: str(v) for m, v in per.min().items()},
            "last_by_monitor": {m: str(v) for m, v in per.max().items()},
        },
        source_snapshot=f"usgs_continuous_discharge/{USGS_SNAPSHOT}",
    )


WIKI_SNAPSHOT = "2026-11-22"
WIKI_COLUMNS = (
    "page_id", "namespace", "revision_id", "parent_id", "timestamp", "editor", "editor_kind",
    "minor", "has_comment", "text_bytes",
)  # fmt: skip


def wiki_revision_view(lines: list[str]) -> pd.DataFrame:
    """Revisions of the complete pages of a stub history, in page then file order.

    A registered contributor is identified by the numeric id and an anonymous one by the IP
    address, both replaced by a salted hash; user names, page titles and edit summaries are not
    kept (only whether a summary exists). Pages after the last closed page are dropped and counted
    (``attrs["incomplete_pages"]``). A document type declaration is refused.
    """
    import xml.etree.ElementTree as ET  # noqa: S405 - DOCTYPE and ENTITY declarations are refused

    closed = [i for i, line in enumerate(lines) if line.strip() == "</page>"]
    if not closed:
        raise ViewError("no complete page in the stub history")
    text = "\n".join(lines[: closed[-1] + 1]) + "\n</mediawiki>"
    if "<!DOCTYPE" in text or "<!ENTITY" in text:
        raise ViewError("document type declarations are refused")
    incomplete = sum(1 for line in lines[closed[-1] + 1 :] if line.strip() == "<page>")
    rows = []
    for _, element in ET.iterparse(io.StringIO(text)):
        if element.tag.rpartition("}")[2] != "page":
            continue
        page = {c.tag.rpartition("}")[2]: c for c in element}
        for rev in (c for c in element if c.tag.rpartition("}")[2] == "revision"):
            fields = {c.tag.rpartition("}")[2]: c for c in rev}
            rows.append(_wiki_row(page, fields))
        element.clear()
    frame = pd.DataFrame(rows, columns=list(WIKI_COLUMNS))
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
    frame["timestamp"] = frame["timestamp"].dt.tz_localize(None)
    for column in ("page_id", "namespace", "revision_id", "parent_id", "text_bytes"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce").astype("Int64")
    frame.attrs = {"incomplete_pages": incomplete}
    return frame


def _wiki_row(page: dict[str, Any], rev: dict[str, Any]) -> dict[str, Any]:
    def value(node: Any) -> str | None:
        return None if node is None else node.text

    who = (
        {c.tag.rpartition("}")[2]: c.text for c in rev["contributor"]}
        if "contributor" in rev
        else {}
    )
    if who.get("id"):
        editor, kind = pseudonym(f"user:{who['id']}"), "registered"
    elif who.get("ip"):
        editor, kind = pseudonym(f"ip:{who['ip']}"), "anonymous"
    else:
        editor, kind = None, "unknown"
    text = rev.get("text")
    return {
        "page_id": value(page.get("id")),
        "namespace": value(page.get("ns")),
        "revision_id": value(rev.get("id")),
        "parent_id": value(rev.get("parentid")),
        "timestamp": value(rev.get("timestamp")),
        "editor": editor,
        "editor_kind": kind,
        "minor": "minor" in rev,
        "has_comment": "comment" in rev,
        "text_bytes": None if text is None else text.get("bytes"),
    }


def gzip_members_lines(blob: bytes) -> tuple[list[str], bool]:
    """Complete text lines of a gzip file made of several members that may be cut off.

    Members are read one after the other; a torn last line is dropped. The flag says whether the
    last member ended inside ``blob``.
    """
    import zlib

    out = bytearray()
    complete = True
    while blob:
        decoder = zlib.decompressobj(wbits=31)
        out += decoder.decompress(blob)
        complete = decoder.eof
        blob = decoder.unused_data
    lines = out.decode().split("\n")
    tail = lines.pop()
    if complete and tail:
        lines.append(tail)
    return lines, complete


def _build_wiki(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    raw = root / "wikimedia_simplewiki_edits" / WIKI_SNAPSHOT / "raw"
    lines, stream_complete = gzip_members_lines(
        (raw / "stub_meta_history_head.xml.gz").read_bytes()
    )
    view = wiki_revision_view(lines)
    folder = out / "wikimedia_simplewiki_edits"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "revisions.csv"
    view.to_csv(target, index=False)
    known = set(view["revision_id"].dropna())
    linked = view["parent_id"].dropna()
    _record(
        manifest,
        "wikimedia_simplewiki_edits",
        {"revisions.csv": (target, len(view))},
        dropped=["user names", "page titles", "edit summaries", "text locations and hashes"],
        pseudonymised=["editor"],
        salt_label=SALT,
        sampling={
            "method": "gzip prefix of the stub history in page-id order: complete revision histories of the lowest page ids",  # noqa: E501
            "pages": int(view["page_id"].nunique()),
            "incomplete_pages": view.attrs["incomplete_pages"],
            "stream_complete": stream_complete,
            "first_revision": str(view["timestamp"].min()),
            "last_revision": str(view["timestamp"].max()),
            "unreadable_timestamps": int(view["timestamp"].isna().sum()),
            "parents_outside_view": int((~linked.isin(known)).sum()),
            "anonymous_share": round(float((view["editor_kind"] == "anonymous").mean()), 4),
        },
        source_snapshot=f"wikimedia_simplewiki_edits/{WIKI_SNAPSHOT} (dump of 2026-11-01)",
    )


UNIPROT_SNAPSHOT = "2026-11-22"
UNIPROT_DROP = frozenset({"references", "sequence"})


def uniprot_view(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Unique UniProtKB entries ordered by primary accession, citations and sequence removed."""
    unique: dict[str, dict[str, Any]] = {}
    for entry in entries:
        unique.setdefault(entry["primaryAccession"], entry)
    return redact_emails(
        nested_view(list(unique.values()), UNIPROT_DROP, lambda r: r["primaryAccession"])
    )


def _build_uniprot(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    raw = root / "uniprot_kb_reviewed" / UNIPROT_SNAPSHOT / "raw"
    files = sorted(raw.glob("uniprot_*.json"))
    if not files:
        raise ViewError("no UniProt file in the snapshot")
    entries: list[dict[str, Any]] = []
    for path in files:
        entries += json.loads(path.read_text())["results"]
    view = uniprot_view(entries)
    folder = out / "uniprot_kb_reviewed"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "entries.jsonl"
    target.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in view))
    _record(
        manifest,
        "uniprot_kb_reviewed",
        {"entries.jsonl": (target, len(view))},
        dropped=["references", "sequence"],
        pseudonymised=[],
        sampling={
            "entries_in": len(entries),
            "files": [p.name for p in files],
            "method": "250 reviewed Swiss-Prot entries per organism across six model organisms",
        },
        source_snapshot=f"uniprot_kb_reviewed/{UNIPROT_SNAPSHOT}",
    )


OSV_SNAPSHOT = "2026-11-22"
OSV_DROP = frozenset({"credits"})


def osv_go_view(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Unique GO-* Go Vulnerability Database advisories ordered by id, credits redacted."""
    unique: dict[str, dict[str, Any]] = {}
    for record in records:
        advisory_id = record["id"]
        if advisory_id.startswith("GO-"):
            unique.setdefault(advisory_id, record)
    return redact_emails(nested_view(list(unique.values()), OSV_DROP, lambda r: r["id"]))


def _build_osv_go(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    import zipfile

    archive = root / "osv_go_advisories" / OSV_SNAPSHOT / "raw" / "osv_go_all.zip"
    if not archive.exists():
        raise ViewError("no OSV Go zip archive in the snapshot")
    with zipfile.ZipFile(archive) as zf:
        members = sorted(n for n in zf.namelist() if n.endswith(".json"))
        records = [json.loads(zf.read(n)) for n in members]
    view = osv_go_view(records)
    folder = out / "osv_go_advisories"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "advisories.jsonl"
    target.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in view))
    _record(
        manifest,
        "osv_go_advisories",
        {"advisories.jsonl": (target, len(view))},
        dropped=["credits"],
        pseudonymised=[],
        sampling={
            "archive_records": len(records),
            "go_records": len(view),
            "method": "all GO-* Go Vulnerability Database advisories from Go/all.zip (non-GO prefixes excluded to stay under CC BY 4.0)",  # noqa: E501
        },
        source_snapshot=f"osv_go_advisories/{OSV_SNAPSHOT}",
    )


GFZ_SNAPSHOT = "2026-11-22"


def gfz_kp_view(lines: list[str]) -> pd.DataFrame:
    """Three-hourly geomagnetic Kp and ap indices in UTC ordered by time."""
    rows = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split()
        rows.append(
            {
                "timestamp": f"{parts[0]}-{parts[1]}-{parts[2]} {int(float(parts[3])):02d}:00:00",
                "kp": parts[7],
                "ap": parts[8],
                "definitive": parts[9],
            }
        )
    frame = pd.DataFrame(rows, columns=["timestamp", "kp", "ap", "definitive"])
    frame["timestamp"] = pd.to_datetime(
        frame["timestamp"], format="%Y-%m-%d %H:%M:%S", errors="coerce"
    )
    kp = pd.to_numeric(frame["kp"], errors="coerce")
    ap = pd.to_numeric(frame["ap"], errors="coerce")
    frame["kp"] = kp.mask(kp == -1.0)
    frame["ap"] = ap.mask(ap == -1)
    frame["definitive"] = pd.to_numeric(frame["definitive"], errors="coerce").astype("Int64")
    return frame[frame["timestamp"].notna()].sort_values("timestamp").reset_index(drop=True)


def _build_gfz_kp(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    source = root / "gfz_kp_index" / GFZ_SNAPSHOT / "raw" / "Kp_ap_since_1932.txt"
    if not source.exists():
        raise ViewError("no GFZ Kp file in the snapshot")
    view = gfz_kp_view(source.read_text().splitlines())
    folder = out / "gfz_kp_index"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "kp_ap.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "gfz_kp_index",
        {"kp_ap.csv": (target, len(view))},
        dropped=["half_hour_midpoint", "days_since_1932", "midpoint_days"],
        pseudonymised=[],
        sampling={
            "definitive_rows": int((view["definitive"] == 1).sum()),
            "first_timestamp": str(view["timestamp"].min()),
            "last_timestamp": str(view["timestamp"].max()),
            "method": "complete GFZ Niemegk 3-hourly Kp/ap time series",
            "missing_kp_rows": int(view["kp"].isna().sum()),
        },
        source_snapshot=f"gfz_kp_index/{GFZ_SNAPSHOT}",
    )


DWD_SNAPSHOT = "2026-11-22"
DWD_START = 2018010100


def dwd_hourly_view(frames: list[pd.DataFrame], start: int = DWD_START) -> pd.DataFrame:
    """Hourly DWD air temperature and humidity from ``start`` onward by station and UTC time."""
    parts = []
    for raw in frames:
        sub = raw[raw["MESS_DATUM"] >= start]
        temp = pd.to_numeric(sub["TT_TU"], errors="coerce")
        humidity = pd.to_numeric(sub["RF_TU"], errors="coerce")
        parts.append(
            pd.DataFrame(
                {
                    "station_id": sub["STATIONS_ID"].astype(str).str.strip(),
                    "timestamp": pd.to_datetime(
                        sub["MESS_DATUM"], format="%Y%m%d%H", errors="coerce"
                    ),
                    "temp_c": temp.mask(temp == -999),
                    "rel_humidity_pct": humidity.mask(humidity == -999),
                    "quality_code": pd.to_numeric(sub["QN_9"], errors="coerce").astype("Int64"),
                }
            )
        )
    merged = pd.concat(parts)
    valid = merged[merged["timestamp"].notna()]
    unique = valid.drop_duplicates(["station_id", "timestamp"])
    ordered = unique.sort_values(["station_id", "timestamp"]).reset_index(drop=True)
    ordered.attrs = {"duplicates": int(len(valid) - len(unique))}
    return ordered


def _build_dwd(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    import zipfile

    raw = root / "dwd_hourly_climate" / DWD_SNAPSHOT / "raw"
    files = sorted(raw.glob("stundenwerte_TU_*.zip"))
    if not files:
        raise ViewError("no DWD station archive in the snapshot")
    frames = []
    for path in files:
        with zipfile.ZipFile(path) as archive:
            members = sorted(
                n
                for n in archive.namelist()
                if n.startswith("produkt_tu_stunde_") and n.endswith(".txt")
            )
            with archive.open(members[0]) as handle:
                frames.append(pd.read_csv(handle, sep=";"))
    view = dwd_hourly_view(frames)
    folder = out / "dwd_hourly_climate"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "air_temperature.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "dwd_hourly_climate",
        {"air_temperature.csv": (target, len(view))},
        dropped=["eor_marker"],
        pseudonymised=[],
        sampling={
            "archives": len(files),
            "duplicates_dropped": view.attrs["duplicates"],
            "first_timestamp": str(view["timestamp"].min()),
            "last_timestamp": str(view["timestamp"].max()),
            "method": "12 strided DWD hourly TU stations filtered from 2018-01-01 onward",
            "stations": int(view["station_id"].nunique()),
        },
        source_snapshot=f"dwd_hourly_climate/{DWD_SNAPSHOT}",
    )


RTE_SNAPSHOT = "2026-11-22"
RTE_DROP = ("perimetre", "nature", "date", "heure")


def rte_eco2mix_view(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Half-hourly RTE eco2mix national telemetry in UTC, sorted and deduplicated by time."""
    merged = pd.concat(frames)
    ts = pd.to_datetime(merged["date_heure"], utc=True, errors="coerce").dt.tz_localize(None)
    valid = merged[ts.notna()].drop(columns=[*RTE_DROP, "date_heure"]).copy()
    valid.insert(0, "timestamp", ts[ts.notna()].to_numpy())
    for col in valid.columns:
        if col != "timestamp":
            valid[col] = pd.to_numeric(valid[col], errors="coerce")
    half = valid[valid["consommation"].notna()]
    unique = half.drop_duplicates("timestamp")
    ordered = unique.sort_values("timestamp").reset_index(drop=True)
    ordered.attrs = {
        "duplicates": int(len(half) - len(unique)),
        "quarter_hour_rows_dropped": int(len(valid) - len(half)),
        "unreadable_timestamps": int(len(merged) - len(valid)),
    }
    return ordered


def _build_rte(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    raw = root / "rte_eco2mix_national" / RTE_SNAPSHOT / "raw"
    files = sorted(raw.glob("eco2mix_national_*.csv"))
    if not files:
        raise ViewError("no RTE eco2mix file in the snapshot")
    frames = [pd.read_csv(p, sep=";", dtype=str) for p in files]
    view = rte_eco2mix_view(frames)
    folder = out / "rte_eco2mix_national"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "eco2mix.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "rte_eco2mix_national",
        {"eco2mix.csv": (target, len(view))},
        dropped=list(RTE_DROP),
        pseudonymised=[],
        sampling={
            "duplicates_dropped": view.attrs["duplicates"],
            "files": [p.name for p in files],
            "first_timestamp": str(view["timestamp"].min()),
            "last_timestamp": str(view["timestamp"].max()),
            "method": "half-hourly definitive RTE eco2mix national grid series for 2020-2023",
            "quarter_hour_rows_dropped": view.attrs["quarter_hour_rows_dropped"],
            "unreadable_timestamps": view.attrs["unreadable_timestamps"],
        },
        source_snapshot=f"rte_eco2mix_national/{RTE_SNAPSHOT}",
    )


ADEME_SNAPSHOT = "2026-11-22"
ADEME_NUMERIC = (
    "annee_construction",
    "surface_habitable_logement",
    "conso_5_usages_par_m2_ep",
    "emission_ges_5_usages_par_m2",
)


def ademe_dpe_view(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Deduplicated French residential EPC (DPE) records with pseudonymised certificate ids."""
    renamed = []
    for frame in frames:
        copy = frame.copy()
        copy.columns = [c.replace(" ", "_") for c in copy.columns]
        renamed.append(copy)
    merged = pd.concat(renamed)
    merged["numero_dpe"] = merged["numero_dpe"].map(pseudonym)
    unique = merged.drop_duplicates("numero_dpe").copy()
    for col in ADEME_NUMERIC:
        unique[col] = pd.to_numeric(unique[col], errors="coerce")
    ordered = unique.sort_values(["date_etablissement_dpe", "numero_dpe"]).reset_index(drop=True)
    ordered.attrs = {"duplicates": int(len(merged) - len(unique))}
    return ordered


def _build_ademe_dpe(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    raw = root / "ademe_dpe_existant" / ADEME_SNAPSHOT / "raw"
    files = sorted(raw.glob("dpe_*.csv"))
    if not files:
        raise ViewError("no ADEME DPE file in the snapshot")
    view = ademe_dpe_view([pd.read_csv(p, dtype=str) for p in files])
    folder = out / "ademe_dpe_existant"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "dpe.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "ademe_dpe_existant",
        {"dpe.csv": (target, len(view))},
        dropped=["addresses", "ban_identifiers", "rnb_identifiers", "coordinates"],
        pseudonymised=["numero_dpe"],
        salt_label=SALT,
        sampling={
            "duplicates_dropped": view.attrs["duplicates"],
            "files": [p.name for p in files],
            "method": "five fixed 2024 dates (10,000 rows per date) with coded attributes only",
        },
        source_snapshot=f"ademe_dpe_existant/{ADEME_SNAPSHOT}",
    )


ALIM_SNAPSHOT = "2026-11-22"
ALIM_KEEP = (
    "numero_inspection",
    "date_inspection",
    "synthese_eval_sanit",
    "app_code_synthese_eval_sanit",
    "evaluation_globale",
    "contexte_inpection",
    "secteur_activite",
    "ods_type_activite",
    "type_activite",
    "app_libelle_activite_etablissement",
    "app_id_regroupement_etablissement",
    "app_libelle_regroupement_etablissement",
    "filtre",
    "type_suite",
    "reg_code",
    "dep_code",
)


def alimconfiance_view(frame: pd.DataFrame) -> pd.DataFrame:
    """De-identified sanitary inspection records sorted by date and pseudonymised id."""
    kept = frame[list(ALIM_KEEP)].copy()
    kept["numero_inspection"] = kept["numero_inspection"].map(pseudonym)
    unique = kept.drop_duplicates("numero_inspection")
    ordered = unique.sort_values(["date_inspection", "numero_inspection"]).reset_index(drop=True)
    ordered.attrs = {"duplicates": int(len(kept) - len(unique))}
    return ordered


def _build_alimconfiance(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    source = root / "dgal_alimconfiance" / ALIM_SNAPSHOT / "raw" / "export_alimconfiance.csv"
    if not source.exists():
        raise ViewError("no DGAL AlimConfiance file in the snapshot")
    view = alimconfiance_view(pd.read_csv(source, sep=";", dtype=str))
    folder = out / "dgal_alimconfiance"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "inspections.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "dgal_alimconfiance",
        {"inspections.csv": (target, len(view))},
        dropped=["establishment_names", "siret", "agrement", "addresses", "communes", "geo"],
        pseudonymised=["numero_inspection"],
        salt_label=SALT,
        sampling={
            "duplicates_dropped": view.attrs["duplicates"],
            "method": "complete Alim'Confiance register projected to coded non-identifying attributes",  # noqa: E501
        },
        source_snapshot=f"dgal_alimconfiance/{ALIM_SNAPSHOT}",
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
    _build_pbdb_relational,
    _build_kelmarsh,
    _build_wikidata,
    _build_bess,
    _build_care,
    _build_care_a,
    _build_nvd,
    _build_unisg,
    _build_backblaze,
    _build_tlc,
    _build_maude,
    _build_aqs,
    _build_usgs,
    _build_wiki,
    _build_uniprot,
    _build_osv_go,
    _build_gfz_kp,
    _build_dwd,
    _build_rte,
    _build_ademe_dpe,
    _build_alimconfiance,
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
