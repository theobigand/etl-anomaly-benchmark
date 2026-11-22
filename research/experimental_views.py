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


EV_SNAPSHOT = "2026-11-22"


def ev_charging_view(frame: pd.DataFrame) -> pd.DataFrame:
    """Residential EV charging sessions in UTC with pseudonymised user and session ids."""
    out = pd.DataFrame(
        {
            "session_id": frame["session_id"].map(pseudonym),
            "user_id": frame["user_id"].map(pseudonym),
            "location": frame["location"].astype("string"),
            "plugin_time": pd.to_datetime(
                frame["plugin_time"], format="%Y-%m-%d %H:%M:%S", errors="coerce"
            ),
            "plugout_time": pd.to_datetime(
                frame["plugout_time"], format="%Y-%m-%d %H:%M:%S", errors="coerce"
            ),
            "connection_hours": pd.to_numeric(
                frame["connection_time"].astype(str).str.replace(",", "."), errors="coerce"
            ),
            "energy_kwh": pd.to_numeric(
                frame["energy_session"].astype(str).str.replace(",", "."), errors="coerce"
            ),
        }
    )
    valid = out[out["plugin_time"].notna()]
    unique = valid.drop_duplicates("session_id")
    ordered = unique.sort_values(["plugin_time", "session_id"]).reset_index(drop=True)
    ordered.attrs = {
        "duplicates": int(len(valid) - len(unique)),
        "unreadable_timestamps": int(len(out) - len(valid)),
    }
    return ordered


def _build_ev_charging(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    source = root / "zen_ev_charging" / EV_SNAPSHOT / "raw" / "Dataset1_charging_reports.csv"
    if not source.exists():
        raise ViewError("no EV charging file in the snapshot")
    view = ev_charging_view(pd.read_csv(source, sep=";", dtype=str))
    folder = out / "zen_ev_charging"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "sessions.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "zen_ev_charging",
        {"sessions.csv": (target, len(view))},
        dropped=[],
        pseudonymised=["session_id", "user_id"],
        salt_label=SALT,
        sampling={
            "duplicates_dropped": view.attrs["duplicates"],
            "locations": int(view["location"].nunique()),
            "method": "complete Dataset1_charging_reports session log across 12 residential sites",
            "unreadable_timestamps": view.attrs["unreadable_timestamps"],
            "users": int(view["user_id"].nunique()),
        },
        source_snapshot=f"zen_ev_charging/{EV_SNAPSHOT}",
    )


AZURE_SNAPSHOT = "2026-11-22"
AZURE_MODULO = 100


def azure_packing_view(frame: pd.DataFrame) -> pd.DataFrame:
    """Ordered cloud VM allocation sequences for tenants with at least two requests."""
    counts = frame.groupby("tenantId")["vmId"].transform("count")
    ordered = frame[counts >= 2].sort_values(["tenantId", "starttime", "vmId"])
    ordered["position"] = ordered.groupby("tenantId").cumcount()
    out = ordered.rename(
        columns={"tenantId": "tenant_id", "vmId": "vm_id", "vmTypeId": "vm_type_id"}
    )[
        ["tenant_id", "position", "starttime", "endtime", "vm_id", "vm_type_id", "priority"]
    ].reset_index(drop=True)
    out.attrs = {"single_vm_rows_dropped": int((counts < 2).sum())}
    return out


def _build_azure_packing(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    import sqlite3
    import tempfile
    import zipfile

    archive = root / "azure_packing_2020" / AZURE_SNAPSHOT / "raw" / "AzurePackingTraceV1.zip"
    if not archive.exists():
        raise ViewError("no Azure packing zip archive in the snapshot")
    with zipfile.ZipFile(archive) as zf, tempfile.TemporaryDirectory() as tmp:
        members = sorted(n for n in zf.namelist() if n.endswith(".sqlite"))
        db_path = Path(zf.extract(members[0], tmp))
        con = sqlite3.connect(db_path)
        try:
            frame = pd.read_sql_query(
                "SELECT vmId, tenantId, vmTypeId, priority, starttime, endtime "
                "FROM vm WHERE tenantId % ? = 0",
                con,
                params=(AZURE_MODULO,),
            )
        finally:
            con.close()
    view = azure_packing_view(frame)
    folder = out / "azure_packing_2020"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "allocations.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "azure_packing_2020",
        {"allocations.csv": (target, len(view))},
        dropped=["vmType hardware dimensions", "single-VM tenants"],
        pseudonymised=[],
        sampling={
            "method": "deterministic 1-in-100 tenant slice (tenantId % 100 == 0) limited to multi-VM tenants ordered by relative starttime",  # noqa: E501
            "modulo": AZURE_MODULO,
            "single_vm_rows_dropped": view.attrs["single_vm_rows_dropped"],
            "tenants": int(view["tenant_id"].nunique()),
        },
        source_snapshot=f"azure_packing_2020/{AZURE_SNAPSHOT}",
    )


AOE_SNAPSHOT = "2026-11-22"
AOE_MAX_BYTES = 128 << 20
AOE_COLUMNS = (
    "case_id",
    "position",
    "time",
    "action",
    "amount",
    "win",
    "player_id",
    "match_id",
    "strategy",
    "map_type",
    "civilization",
    "civilization_category",
    "elo",
)


def aoe_interactions_view(traces: list[dict[str, Any]]) -> pd.DataFrame:
    """Real-time strategy gameplay event sequences with pseudonymised match and player ids."""
    rows: list[dict[str, Any]] = []
    for trace in traces:
        attrs = trace["attributes"]
        case_id = pseudonym(trace["case"])
        player = attrs.get("player_id")
        match = attrs.get("match_id")
        shared = {
            "case_id": case_id,
            "player_id": None if player is None else pseudonym(str(player)),
            "match_id": None if match is None else pseudonym(str(match)),
            "strategy": attrs.get("strategy"),
            "map_type": attrs.get("map_type"),
            "civilization": attrs.get("civilization"),
            "civilization_category": attrs.get("civilization_category"),
            "elo": attrs.get("elo"),
        }
        for pos, event in enumerate(trace["events"]):
            rows.append(
                {
                    **shared,
                    "position": pos,
                    "time": event.get("time:timestamp"),
                    "action": event.get("concept:name"),
                    "amount": event.get("amount"),
                    "win": event.get("win"),
                }
            )
    frame = pd.DataFrame(rows, columns=list(AOE_COLUMNS))
    frame["time"] = pd.to_datetime(frame["time"], utc=True, errors="coerce").dt.tz_localize(None)
    for col in ("amount", "win", "elo"):
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    return frame.sort_values(["case_id", "position"]).reset_index(drop=True)


def _build_aoe(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    import acquisition
    import xes_stream

    archive = root / "zen_aoe_interactions" / AOE_SNAPSHOT / "raw" / "aoe_xes_head.zip"
    if not archive.exists():
        raise ViewError("no AoE XES prefix archive in the snapshot")
    prefix = acquisition.zip_prefix_lines(archive.read_bytes(), AOE_MAX_BYTES)
    stream = io.BytesIO(("\n".join(prefix["lines"]) + "\n").encode())
    parsed = xes_stream.read_traces(stream, compressed=False, modulo=1)
    view = aoe_interactions_view(parsed.traces)
    folder = out / "zen_aoe_interactions"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "events.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "zen_aoe_interactions",
        {"events.csv": (target, len(view))},
        dropped=[],
        pseudonymised=["case_id", "player_id", "match_id"],
        salt_label=SALT,
        sampling={
            "member": prefix["member"],
            "method": "4 MiB compressed zip-prefix of Age of Empires interaction log decoded via xes_stream",  # noqa: E501
            "status": parsed.status,
            "traces": len(parsed.traces),
        },
        source_snapshot=f"zen_aoe_interactions/{AOE_SNAPSHOT}",
    )


CHARITY_SNAPSHOT = "2026-11-22"
CHARITY_MODULO = 20
CHARITY_FILES: dict[str, str] = {
    "charity": "publicextract.charity.zip",
    "annual_return_history": "publicextract.charity_annual_return_history.zip",
    "area_of_operation": "publicextract.charity_area_of_operation.zip",
    "classification": "publicextract.charity_classification.zip",
    "event_history": "publicextract.charity_event_history.zip",
}
CHARITY_SPEC: dict[str, Any] = {
    "tables": {
        "charity": {
            "keep": [
                "organisation_number",
                "registered_charity_number",
                "linked_charity_number",
                "charity_type",
                "charity_registration_status",
                "date_of_registration",
                "date_of_removal",
                "charity_reporting_status",
                "latest_acc_fin_period_start_date",
                "latest_acc_fin_period_end_date",
                "latest_income",
                "latest_expenditure",
                "charity_insolvent",
                "charity_in_administration",
                "charity_previously_excepted",
                "charity_is_cdf_or_cif",
                "charity_is_cio",
                "cio_is_dissolved",
                "charity_gift_aid",
                "charity_has_land",
            ]
        },
        "annual_return_history": {
            "keep": [
                "organisation_number",
                "registered_charity_number",
                "fin_period_start_date",
                "fin_period_end_date",
                "ar_cycle_reference",
                "reporting_due_date",
                "date_annual_return_received",
                "date_accounts_received",
                "total_gross_income",
                "total_gross_expenditure",
                "accounts_qualified",
                "suppression_ind",
                "suppression_type",
            ]
        },
        "area_of_operation": {
            "keep": [
                "organisation_number",
                "registered_charity_number",
                "linked_charity_number",
                "geographic_area_type",
                "geographic_area_description",
                "parent_geographic_area_type",
                "parent_geographic_area_description",
                "welsh_ind",
            ]
        },
        "classification": {
            "keep": [
                "organisation_number",
                "registered_charity_number",
                "linked_charity_number",
                "classification_code",
                "classification_type",
                "classification_description",
            ]
        },
        "event_history": {
            "keep": [
                "organisation_number",
                "registered_charity_number",
                "linked_charity_number",
                "charity_event_order",
                "event_type",
                "date_of_event",
                "assoc_organisation_number",
                "assoc_registered_charity_number",
            ]
        },
    },
    "relations": [
        ["annual_return_history", "organisation_number", "charity", "organisation_number"],
        ["area_of_operation", "organisation_number", "charity", "organisation_number"],
        ["classification", "organisation_number", "charity", "organisation_number"],
        ["event_history", "organisation_number", "charity", "organisation_number"],
    ],
}


def charity_register_view(
    tables: dict[str, pd.DataFrame], modulo: int = CHARITY_MODULO
) -> tuple[dict[str, pd.DataFrame], list[dict[str, Any]]]:
    """Non-identifying Charity Commission register tables sliced by organisation number."""
    projected, _ = tables_view(tables, CHARITY_SPEC)
    filtered: dict[str, pd.DataFrame] = {}
    for name, frame in projected.items():
        nums = pd.to_numeric(frame["organisation_number"], errors="coerce")
        sub = frame[nums % modulo == 0]
        filtered[name] = sub.sort_values(list(sub.columns))
    views, relations = tables_view(filtered, CHARITY_SPEC)
    return {name: frame.reset_index(drop=True) for name, frame in views.items()}, relations


def _build_charity_register(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    import csv
    import zipfile

    raw = root / "uk_charity_register" / CHARITY_SNAPSHOT / "raw"
    tables: dict[str, pd.DataFrame] = {}
    for name, zname in CHARITY_FILES.items():
        archive_path = raw / zname
        if not archive_path.exists():
            raise ViewError(f"no UK charity zip {zname} in the snapshot")
        with zipfile.ZipFile(archive_path) as zf, zf.open(zf.namelist()[0]) as handle:
            tables[name] = pd.read_csv(handle, sep="\t", dtype=str, quoting=csv.QUOTE_NONE)
    views, relations = charity_register_view(tables)
    folder = out / "uk_charity_register"
    folder.mkdir(parents=True, exist_ok=True)
    files: dict[str, tuple[Path, int]] = {}
    for name, frame in views.items():
        target = folder / f"{name}.csv"
        frame.to_csv(target, index=False)
        files[f"{name}.csv"] = (target, len(frame))
    _record(
        manifest,
        "uk_charity_register",
        files,
        dropped=[
            "charity_name",
            "charity_contact_*",
            "charity_activities",
            "reason",
            "assoc_charity_name",
            "trustee table (not downloaded)",
        ],
        pseudonymised=[],
        relations=relations,
        sampling={
            "method": f"deterministic 1-in-{CHARITY_MODULO} slice on organisation_number across 5 non-trustee extracts",  # noqa: E501
            "modulo": CHARITY_MODULO,
        },
        source_snapshot=f"uk_charity_register/{CHARITY_SNAPSHOT}",
    )


JAPAN_SNAPSHOT = "2026-11-22"
JAPAN_PREFIX = "reconstructed_buildings_japan_v1.1/csv/"
JAPAN_SPEC: dict[str, Any] = {
    "tables": {
        "buildings": {
            "keep": [
                "building_id",
                "site_id",
                "period_id",
                "building_type_id",
                "archaeological_basis_relation_id",
                "archaeological_evidence_site_id",
                "is_above_archaeological_feature",
                "designer_status_id",
                "date_status_id",
                "location_status_id",
                "is_standing",
                "is_rebuilt",
                "built_year",
                "frame_material_id",
                "roof_material_id",
                "roof_shape_id",
                "plan_layout_id",
                "pillar_count",
                "floor_length_m",
                "floor_width_m",
                "floor_diameter_m",
                "floor_area_m2",
                "latitude",
                "longitude",
            ]
        },
        "building_designers": {"keep": ["building_id", "designer_id"]},
        "designers": {"keep": ["designer_id", "is_individual", "primary_designer_type_id"]},
        "sites": {
            "keep": [
                "site_id",
                "prefecture_code",
                "municipality_code",
                "district_code",
                "ward_code",
                "designation_id",
                "designation_date",
                "latitude",
                "longitude",
            ]
        },
        "archaeological_evidence_sites": {
            "keep": ["archaeological_evidence_site_id", "site_name_en", "display_site_id"]
        },
        "site_sources": {"keep": ["site_id", "source_id"]},
        "sources": {
            "keep": [
                "source_id",
                "year",
                "source_type_id",
                "source_kind_id",
                "building_info_status_id",
                "ncid",
                "naid",
                "crid",
            ]
        },
    },
    "relations": [
        ["buildings", "site_id", "sites", "site_id"],
        [
            "buildings",
            "archaeological_evidence_site_id",
            "archaeological_evidence_sites",
            "archaeological_evidence_site_id",
        ],
        ["building_designers", "building_id", "buildings", "building_id"],
        ["building_designers", "designer_id", "designers", "designer_id"],
        ["site_sources", "site_id", "sites", "site_id"],
        ["site_sources", "source_id", "sources", "source_id"],
    ],
}


def japan_buildings_view(
    tables: dict[str, pd.DataFrame],
) -> tuple[dict[str, pd.DataFrame], list[dict[str, Any]]]:
    """De-identified seven-table Japan reconstructed buildings relational slice."""
    views, relations = tables_view(tables, JAPAN_SPEC)
    ordered = {
        name: frame.sort_values(list(frame.columns)).reset_index(drop=True)
        for name, frame in views.items()
    }
    return ordered, relations


def _build_japan_buildings(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    import zipfile

    archive = (
        root
        / "zen_japan_buildings"
        / JAPAN_SNAPSHOT
        / "raw"
        / "reconstructed_buildings_japan_v1.1.zip"  # noqa: E501
    )
    if not archive.exists():
        raise ViewError("no Japan buildings zip archive in the snapshot")
    tables: dict[str, pd.DataFrame] = {}
    with zipfile.ZipFile(archive) as zf:
        for name in JAPAN_SPEC["tables"]:
            with zf.open(f"{JAPAN_PREFIX}{name}.csv") as handle:
                tables[name] = pd.read_csv(handle, dtype=str)
    views, relations = japan_buildings_view(tables)
    folder = out / "zen_japan_buildings"
    folder.mkdir(parents=True, exist_ok=True)
    files: dict[str, tuple[Path, int]] = {}
    for name, frame in views.items():
        target = folder / f"{name}.csv"
        frame.to_csv(target, index=False)
        files[f"{name}.csv"] = (target, len(frame))
    _record(
        manifest,
        "zen_japan_buildings",
        files,
        dropped=[
            "designer personal/company names, affiliations and URLs",
            "source authors, titles and URLs",
            "site street addresses and postal codes",
            "free-text notes",
        ],
        pseudonymised=[],
        relations=relations,
        sampling={"method": "complete core 7-table relational schema (no row sampling)"},
        source_snapshot=f"zen_japan_buildings/{JAPAN_SNAPSHOT}",
    )


COOPS_SNAPSHOT = "2026-11-22"


def coops_tides_view(records: list[dict[str, Any]]) -> tuple[pd.DataFrame, int]:
    """Hourly coastal water levels, sigma and quality flags ordered by station and UTC time."""
    raw = pd.DataFrame(records, columns=["station_id", "t", "v", "s", "f"])
    out = pd.DataFrame(
        {
            "station_id": raw["station_id"].astype(str),
            "timestamp": pd.to_datetime(raw["t"], format="%Y-%m-%d %H:%M", errors="coerce"),
            "water_level_m": pd.to_numeric(raw["v"], errors="coerce"),
            "sigma_m": pd.to_numeric(raw["s"], errors="coerce"),
            "flags": raw["f"].astype(str),
        }
    )
    out = out[out["timestamp"].notna()].sort_values(["station_id", "timestamp"])
    dups = int(out.duplicated(["station_id", "timestamp"]).sum())
    deduped = out.drop_duplicates(["station_id", "timestamp"], keep="first").reset_index(drop=True)
    return deduped, dups


def _build_coops_tides(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    files = sorted((root / "noaa_coops_tides" / COOPS_SNAPSHOT / "raw").glob("coops_*.json"))
    if not files:
        raise ViewError("no NOAA CO-OPS JSON files in the snapshot")
    records: list[dict[str, Any]] = []
    for path in files:
        payload = json.loads(path.read_text())
        station_id = payload["metadata"]["id"]
        for item in payload.get("data", []):
            records.append({"station_id": station_id, **item})
    view, dups = coops_tides_view(records)
    folder = out / "noaa_coops_tides"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "tides.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "noaa_coops_tides",
        {"tides.csv": (target, len(view))},
        dropped=[],
        pseudonymised=[],
        sampling={
            "duplicates_dropped": dups,
            "first_timestamp": str(view["timestamp"].min()),
            "flagged_rows": int((view["flags"] != "0,0").sum()),
            "last_timestamp": str(view["timestamp"].max()),
            "method": "six US coastal stations hourly water level (2022-2024 GMT)",
            "missing_value_rows": int(view["water_level_m"].isna().sum()),
            "stations": int(view["station_id"].nunique()),
        },
        source_snapshot=f"noaa_coops_tides/{COOPS_SNAPSHOT}",
    )


GML_CO2_SNAPSHOT = "2026-11-22"


def gml_co2_view(text: str) -> pd.DataFrame:
    """Weekly Mauna Loa atmospheric CO2 series with -999.99 sentinels masked to NaN."""
    raw = pd.read_csv(io.StringIO(text), comment="#")
    ts = pd.to_datetime(raw[["year", "month", "day"]], errors="coerce")
    cols = {
        "decimal_year": "decimal",
        "co2_ppm": "average",
        "one_year_ago_ppm": "1 year ago",
        "ten_years_ago_ppm": "10 years ago",
        "increase_since_1800_ppm": "increase since 1800",
    }
    data: dict[str, Any] = {"timestamp": ts}
    for out_col, src_col in cols.items():
        vals = pd.to_numeric(raw[src_col], errors="coerce")
        data[out_col] = vals.mask(vals == -999.99)
    data["ndays"] = pd.to_numeric(raw["ndays"], errors="coerce").astype("Int64")
    out = pd.DataFrame(data)
    return out[out["timestamp"].notna()].sort_values("timestamp").reset_index(drop=True)


def _build_gml_co2(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    source = root / "noaa_gml_co2_weekly" / GML_CO2_SNAPSHOT / "raw" / "co2_weekly_mlo.csv"
    if not source.exists():
        raise ViewError("no NOAA GML CO2 file in the snapshot")
    view = gml_co2_view(source.read_text())
    folder = out / "noaa_gml_co2_weekly"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "co2_weekly.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "noaa_gml_co2_weekly",
        {"co2_weekly.csv": (target, len(view))},
        dropped=[],
        pseudonymised=[],
        sampling={
            "first_timestamp": str(view["timestamp"].min()),
            "last_timestamp": str(view["timestamp"].max()),
            "method": "complete weekly Mauna Loa atmospheric CO2 record (1974-2026)",
            "missing_co2_rows": int(view["co2_ppm"].isna().sum()),
        },
        source_snapshot=f"noaa_gml_co2_weekly/{GML_CO2_SNAPSHOT}",
    )


CNC_SNAPSHOT = "2026-11-22"
CNC_SIGNALS = (
    "CoolantFlow",
    "ProgramStatus",
    "ProgramDetail",
    "ToolNumber",
    "DriveStatus",
    "DoorStatusMain",
    "DoorStatusTooling",
    "CabinDoorLockFront",
    "CabinDoorLockSide",
    "DNCMode",
    "SpindleCleaning",
    "ChipCleaningGunStatus",
    "OverrideSpindle",
    "OverrideFeed",
    "FeedRate",
    "SpindleSpeed",
    "SpindleApproval",
    "RapidTraverseKey",
    "Warmup",
    "Production",
)


def cnc_milling_view(named_frames: list[tuple[str, pd.DataFrame]]) -> tuple[pd.DataFrame, int]:
    """Five-axis CNC controller signals across production series ordered by series and time."""
    parts = []
    for series_id, raw in named_frames:
        data: dict[str, Any] = {
            "series_id": series_id,
            "timestamp": pd.to_datetime(
                raw["DateTime"], format="%Y-%m-%d %H:%M:%S", errors="coerce"
            ),
        }
        for col in CNC_SIGNALS:
            data[col] = pd.to_numeric(raw[col], errors="coerce")
        parts.append(pd.DataFrame(data))
    combined = pd.concat(parts, ignore_index=True)
    combined = combined[combined["timestamp"].notna()].sort_values(["series_id", "timestamp"])
    dups = int(combined.duplicated(["series_id", "timestamp"]).sum())
    deduped = combined.drop_duplicates(["series_id", "timestamp"], keep="first").reset_index(
        drop=True
    )
    return deduped, dups


def _build_cnc_milling(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    files = sorted((root / "zen_cnc_milling" / CNC_SNAPSHOT / "raw").glob("Data_from_*.csv"))
    if not files:
        raise ViewError("no CNC milling CSV files in the snapshot")
    named = [(p.stem.removeprefix("Data_from_"), pd.read_csv(p)) for p in files]
    view, dups = cnc_milling_view(named)
    folder = out / "zen_cnc_milling"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "cnc_milling.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "zen_cnc_milling",
        {"cnc_milling.csv": (target, len(view))},
        dropped=["Unnamed: 0", "Phase", "Phase_compressed", "PocketTable"],
        pseudonymised=[],
        sampling={
            "duplicates_dropped": dups,
            "first_timestamp": str(view["timestamp"].min()),
            "last_timestamp": str(view["timestamp"].max()),
            "method": "complete 13-file five-axis CNC production series telemetry (Nov 2021 - Apr 2022)",  # noqa: E501
            "series_count": int(view["series_id"].nunique()),
            "series_files": len(files),
        },
        source_snapshot=f"zen_cnc_milling/{CNC_SNAPSHOT}",
    )


WB_SNAPSHOT = "2026-11-22"
WB_MONEY_COLS = (
    ("curr_total_commitment", "curr_total_commitment"),
    ("curr_ibrd_commitment", "curr_ibrd_commitment"),
    ("curr_ida_commitment", "curr_ida_commitment"),
    ("grant_amt", "grantamt"),
    ("lend_project_cost", "lendprojectcost"),
)


def _num_clean(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype(str).str.replace(",", ""), errors="coerce")


def wb_projects_view(records: list[dict[str, Any]]) -> pd.DataFrame:
    """World Bank IBRD/IDA project lending commitments sorted by project_id."""
    cols = [
        "project_id",
        "board_approval_date",
        "closing_date",
        "approval_fy",
        "country_code",
        "region_name",
        "lending_instrument",
        "lending_instrument_type",
        "prodline",
        "status",
        *[c for c, _ in WB_MONEY_COLS],
        "sector1_name",
        "sector1_percent",
    ]
    rows = []
    for rec in records:
        cc = rec.get("countrycode")
        sec = rec.get("sector1") if isinstance(rec.get("sector1"), dict) else {}
        row: dict[str, Any] = {
            "project_id": rec.get("id"),
            "board_approval_date": rec.get("boardapprovaldate"),
            "closing_date": rec.get("closingdate"),
            "approval_fy": rec.get("approvalfy"),
            "country_code": cc[0] if isinstance(cc, list) and cc else None,
            "region_name": rec.get("regionname"),
            "lending_instrument": rec.get("lendinginstr"),
            "lending_instrument_type": rec.get("lendinginstrtype"),
            "prodline": rec.get("prodline"),
            "status": rec.get("status"),
            "sector1_name": sec.get("Name") or None,
            "sector1_percent": sec.get("Percent"),
        }
        for out_c, src_c in WB_MONEY_COLS:
            row[out_c] = rec.get(src_c)
        rows.append(row)
    frame = pd.DataFrame(rows, columns=cols)
    frame["approval_fy"] = pd.to_numeric(frame["approval_fy"], errors="coerce").astype("Int64")
    frame["sector1_percent"] = pd.to_numeric(frame["sector1_percent"], errors="coerce")
    for out_c, _ in WB_MONEY_COLS:
        frame[out_c] = _num_clean(frame[out_c])
    return (
        frame[frame["project_id"].notna()]
        .drop_duplicates("project_id", keep="first")
        .sort_values("project_id")
        .reset_index(drop=True)
    )


def _build_wb_projects(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    files = sorted((root / "wb_lending_projects" / WB_SNAPSHOT / "raw").glob("wb_projects_*.json"))
    if not files:
        raise ViewError("no World Bank project JSON files in the snapshot")
    records: list[dict[str, Any]] = []
    for path in files:
        records.extend(json.loads(path.read_text()).get("projects", {}).values())
    view = wb_projects_view(records)
    folder = out / "wb_lending_projects"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "projects.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "wb_lending_projects",
        {"projects.csv": (target, len(view))},
        dropped=["teamleadname", "project_name", "projectdocs", "url"],
        pseudonymised=[],
        sampling={
            "method": "first 10 deterministic pagination pages (500 rows per offset 0..4500 in API default order)",  # noqa: E501
            "pages": len(files),
        },
        source_snapshot=f"wb_lending_projects/{WB_SNAPSHOT}",
    )


QLD_PETROL_SNAPSHOT = "2026-11-22"
QLD_TEXT_COLS = (
    "reporting_period",
    "production_type",
    "permit_number",
    "basin",
    "reservoir_unit_name",
    "strat_unit_name",
    "field_name",
)
QLD_NUM_COLS = (
    "gas_cum_volume_mm3",
    "gas_flared_vented_cum_volume_mm3",
    "gas_vented_cum_volume_mm3",
    "gas_flared_cum_volume_mm3",
    "gas_used_cum_volume_mm3",
    "oil_cum_volume_mmbbl",
    "oil_used_cum_volume_mmbbl",
    "lpg_cum_volume_kt",
    "lpg_used_cum_volume_kt",
    "condensate_cum_volume_mmbbl",
    "condensate_used_cum_volume_mmbbl",
    "water_cum_volume_ml",
    "water_total_volume_ml",
    "wells_on_prod",
)


def queensland_petrol_view(raw: pd.DataFrame) -> pd.DataFrame:
    """Queensland half-yearly petroleum and gas production ledger sorted deterministically."""
    data: dict[str, Any] = {col: raw[col].astype(str) for col in QLD_TEXT_COLS}
    for col in QLD_NUM_COLS:
        data[col] = pd.to_numeric(raw[col], errors="coerce")
    frame = pd.DataFrame(data)
    return frame.sort_values(
        ["reporting_period", "permit_number", "field_name", "reservoir_unit_name"]
    ).reset_index(drop=True)


def _build_queensland_petrol(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    source = root / "zen_queensland_petrol" / QLD_PETROL_SNAPSHOT / "raw" / "data.csv"
    if not source.exists():
        raise ViewError("no Queensland petroleum CSV in the snapshot")
    view = queensland_petrol_view(pd.read_csv(source, dtype=str))
    folder = out / "zen_queensland_petrol"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "production.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "zen_queensland_petrol",
        {"production.csv": (target, len(view))},
        dropped=[
            "authorized_holder",
            "remark",
            "secondary_strat_unit_name",
            "field_name_prod_corr",
        ],
        pseudonymised=[],
        sampling={"method": "complete 2026-09-04 Queensland petroleum and gas field release"},
        source_snapshot=f"zen_queensland_petrol/{QLD_PETROL_SNAPSHOT}",
    )


INPI_SNAPSHOT = "2026-11-22"
INPI_NUM_COLS = (
    "chiffre_d_affaires",
    "marge_brute",
    "ebe",
    "ebit",
    "resultat_net",
    "taux_d_endettement",
    "ratio_de_liquidite",
    "ratio_de_vetuste",
    "autonomie_financiere",
    "poids_bfr_exploitation_sur_ca",
    "couverture_des_interets",
    "caf_sur_ca",
    "capacite_de_remboursement",
    "marge_ebe",
    "resultat_courant_avant_impots_sur_ca",
    "poids_bfr_exploitation_sur_ca_jours",
    "rotation_des_stocks_jours",
    "credit_clients_jours",
    "credit_fournisseurs_jours",
)


def inpi_ratios_view(raw: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Public INPI corporate annual filings with salted pseudonymised SIREN identifiers."""
    public = raw[raw["confidentiality"] == "Public"]
    dropped_conf = len(raw) - len(public)
    data: dict[str, Any] = {
        "siren_id": public["siren"].fillna("").map(lambda s: pseudonym(str(s)) if s else ""),
        "date_cloture_exercice": public["date_cloture_exercice"].astype(str),
        "type_bilan": public["type_bilan"].astype(str),
    }
    for col in INPI_NUM_COLS:
        data[col] = pd.to_numeric(public[col], errors="coerce")
    frame = pd.DataFrame(data)
    ordered = frame.sort_values(["siren_id", "date_cloture_exercice"]).reset_index(drop=True)
    return ordered, dropped_conf


def _build_inpi_ratios(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    source = root / "inpi_bce_ratios" / INPI_SNAPSHOT / "raw" / "ratios_inpi_bce_30k.csv"
    if not source.exists():
        raise ViewError("no INPI BCE ratios CSV in the snapshot")
    view, dropped_conf = inpi_ratios_view(pd.read_csv(source, sep=";", dtype=str))
    folder = out / "inpi_bce_ratios"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "ratios.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "inpi_bce_ratios",
        {"ratios.csv": (target, len(view))},
        dropped=["confidentiality"],
        pseudonymised=["siren"],
        salt_label=SALT,
        sampling={
            "method": "first 30,000 filings ordered by SIREN ascending filtered to confidentiality=Public",  # noqa: E501
            "non_public_dropped": dropped_conf,
        },
        source_snapshot=f"inpi_bce_ratios/{INPI_SNAPSHOT}",
    )


def _write_jsonl(folder: Path, filename: str, rows: list[dict[str, Any]]) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / filename
    target.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))
    return target


ROR_SNAPSHOT = "2026-11-22"
ROR_STRIDE = 15


def ror_view(records: list[dict[str, Any]], stride: int = ROR_STRIDE) -> list[dict[str, Any]]:
    """Every ``stride``-th unique ROR organization in canonical ``id`` order, e-mails redacted."""
    unique: dict[str, dict[str, Any]] = {}
    for record in records:
        unique.setdefault(record["id"], record)
    sliced = nested_view(list(unique.values()), frozenset(), lambda r: r["id"])[::stride]
    return redact_emails(sliced)


def _build_ror(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    import zipfile

    archive = root / "ror_organizations" / ROR_SNAPSHOT / "raw" / "ror_data.zip"
    if not archive.exists():
        raise ViewError("no ROR zip archive in the snapshot")
    with zipfile.ZipFile(archive) as zf:
        members = sorted(n for n in zf.namelist() if n.endswith(".json"))
        if not members:
            raise ViewError("no ROR JSON member in the archive")
        records = json.loads(zf.read(members[0]))
    view = ror_view(records)
    target = _write_jsonl(out / "ror_organizations", "organizations.jsonl", view)
    _record(
        manifest,
        "ror_organizations",
        {"organizations.jsonl": (target, len(view))},
        dropped=[],
        pseudonymised=[],
        sampling={
            "method": "every 15th ROR v2 organization record in canonical id order across all statuses",  # noqa: E501
            "total_records": len(records),
            "stride": ROR_STRIDE,
            "kept": len(view),
        },
        source_snapshot=f"ror_organizations/{ROR_SNAPSHOT}",
    )


RCSB_SNAPSHOT = "2026-11-22"


def rcsb_pdb_view(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Unique RCSB PDB macromolecular entries ordered by ``rcsb_id``, e-mails redacted."""
    unique: dict[str, dict[str, Any]] = {}
    for entry in entries:
        unique.setdefault(entry["rcsb_id"], entry)
    return redact_emails(nested_view(list(unique.values()), frozenset(), lambda r: r["rcsb_id"]))


def _build_rcsb_pdb(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    raw = root / "rcsb_pdb_entries" / RCSB_SNAPSHOT / "raw"
    files = sorted(raw.glob("entries_b*.json"))
    if not files:
        raise ViewError("no RCSB PDB entry files in the snapshot")
    entries: list[dict[str, Any]] = []
    for path in files:
        entries += json.loads(path.read_text())["data"]["entries"]
    view = rcsb_pdb_view(entries)
    target = _write_jsonl(out / "rcsb_pdb_entries", "entries.jsonl", view)
    _record(
        manifest,
        "rcsb_pdb_entries",
        {"entries.jsonl": (target, len(view))},
        dropped=[
            "audit_author (omitted in GraphQL query)",
            "citation authors (omitted in GraphQL query)",
        ],
        pseudonymised=[],
        sampling={
            "method": "earliest released structures per calendar year ordered by initial_release_date and rcsb_id (2024:350, 2025:350, 2026:300)",  # noqa: E501
            "entries_in": len(entries),
            "files": [p.name for p in files],
        },
        source_snapshot=f"rcsb_pdb_entries/{RCSB_SNAPSHOT}",
    )


NWS_SNAPSHOT = "2026-11-22"
NWS_DROP = frozenset({"sender"})


def nws_alerts_view(features: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Unique NWS CAP alert GeoJSON features ordered by alert id, sender removed and e-mails redacted."""  # noqa: E501
    unique: dict[str, dict[str, Any]] = {}
    for feature in features:
        unique.setdefault(feature["properties"]["id"], feature)
    cleaned = nested_view(list(unique.values()), NWS_DROP, lambda r: r["properties"]["id"])
    return redact_emails(cleaned)


def _build_nws_alerts(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    raw = root / "nws_weather_alerts" / NWS_SNAPSHOT / "raw"
    files = sorted(raw.glob("alerts_p*.json"))
    if not files:
        raise ViewError("no NWS alerts JSON in the snapshot")
    features: list[dict[str, Any]] = []
    for path in files:
        features += json.loads(path.read_text())["features"]
    view = nws_alerts_view(features)
    target = _write_jsonl(out / "nws_weather_alerts", "alerts.jsonl", view)
    _record(
        manifest,
        "nws_weather_alerts",
        {"alerts.jsonl": (target, len(view))},
        dropped=sorted(NWS_DROP),
        pseudonymised=[],
        sampling={
            "method": "four consecutive 500-alert cursor pages from NWS alerts API",
            "features_in": len(features),
            "unique_alerts": len(view),
            "files": [p.name for p in files],
        },
        source_snapshot=f"nws_weather_alerts/{NWS_SNAPSHOT}",
    )


NOUMEA_SNAPSHOT = "2026-11-22"
NOUMEA_DROP = ("shipping_agent", "vessel_operator", "vessel_name")
NOUMEA_TEXT_COLS = (
    "id",
    "voyage_date",
    "traffic_type",
    "vessel_type",
    "vessel_type_code",
    "vessel_flag",
    "vessel_region",
    "nc_port_of_touch",
    "origin_city_code",
    "origin_city",
    "origin_country_code",
    "origin_country",
    "origin_region",
    "destination_city_code",
    "destination_city",
    "destination_country_code",
    "destination_country",
    "destination_region",
)
NOUMEA_NUM_COLS = (
    "year",
    "voyage_number",
    "vessel_tonnage",
    "latitude_origine",
    "longitude_origine",
    "latitude_destination",
    "longitude_destination",
)


def port_noumea_view(raw: pd.DataFrame) -> pd.DataFrame:
    """Port of Noumea vessel stopover records with operator/ship names dropped and IMO pseudonymised."""  # noqa: E501
    data: dict[str, Any] = {col: raw[col] for col in NOUMEA_TEXT_COLS}
    data["vessel_imo_id"] = [
        pseudonym(str(v)) if pd.notna(v) and str(v) else "" for v in raw["vessel_imo"]
    ]
    for col in NOUMEA_NUM_COLS:
        data[col] = pd.to_numeric(raw[col], errors="coerce")
    cols = [
        "id",
        "year",
        "voyage_number",
        "voyage_date",
        "traffic_type",
        "vessel_imo_id",
        "vessel_type",
        "vessel_type_code",
        "vessel_flag",
        "vessel_region",
        "vessel_tonnage",
        "nc_port_of_touch",
        "origin_city_code",
        "origin_city",
        "latitude_origine",
        "longitude_origine",
        "origin_country_code",
        "origin_country",
        "origin_region",
        "destination_city_code",
        "destination_city",
        "latitude_destination",
        "longitude_destination",
        "destination_country_code",
        "destination_country",
        "destination_region",
    ]
    return pd.DataFrame(data)[cols].sort_values(["voyage_date", "id"])


def _build_port_noumea(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    source = root / "zen_port_noumea" / NOUMEA_SNAPSHOT / "raw" / "stopover_nc_2002_2017.csv"
    if not source.exists():
        raise ViewError("no Port of Noumea stopover CSV in the snapshot")
    raw = pd.read_csv(source, dtype=str, encoding="latin-1")
    view = port_noumea_view(raw)
    folder = out / "zen_port_noumea"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "stopovers.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "zen_port_noumea",
        {"stopovers.csv": (target, len(view))},
        dropped=list(NOUMEA_DROP),
        pseudonymised=["vessel_imo"],
        salt_label=SALT,
        sampling={
            "method": "complete New Caledonia international port stopover table",
            "vessels": int(view["vessel_imo_id"].nunique()),
        },
        source_snapshot=f"zen_port_noumea/{NOUMEA_SNAPSHOT}",
    )


KANTO_SNAPSHOT = "2026-11-22"
KANTO_TEXT_COLS = ("id", "Watershed", "Mountain", "Symbol code", "Lithology category")
KANTO_NUM_COLS = ("Area (m2)", "Inferred volume (m3)", "Mean slope (degree)")


def kanto_landslides_view(raw: pd.DataFrame) -> pd.DataFrame:
    """1923 Kanto earthquake landslide polygons without free-text notes, sorted deterministically."""  # noqa: E501
    data: dict[str, Any] = {col: raw[col] for col in KANTO_TEXT_COLS}
    for col in KANTO_NUM_COLS:
        data[col] = pd.to_numeric(raw[col], errors="coerce")
    return pd.DataFrame(data).sort_values(["Mountain", "Lithology category", "id"])


def _build_kanto_landslides(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    import zipfile

    archive = root / "zen_kanto_landslides" / KANTO_SNAPSHOT / "raw" / "kanto_landslides.zip"
    if not archive.exists():
        raise ViewError("no Kanto landslide zip archive in the snapshot")
    with zipfile.ZipFile(archive) as zf:
        members = sorted(n for n in zf.namelist() if n.endswith(".csv"))
        if not members:
            raise ViewError("no Kanto landslide CSV in the archive")
        with zf.open(members[0]) as fh:
            raw = pd.read_csv(fh, dtype=str)
    view = kanto_landslides_view(raw)
    folder = out / "zen_kanto_landslides"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "landslides.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "zen_kanto_landslides",
        {"landslides.csv": (target, len(view))},
        dropped=["Note"],
        pseudonymised=[],
        sampling={"method": "complete 1923 Kanto earthquake landslide CSV attribute table"},
        source_snapshot=f"zen_kanto_landslides/{KANTO_SNAPSHOT}",
    )


NHIF_SNAPSHOT = "2026-11-22"
NHIF_STRIDE = 75
NHIF_TEXT_COLS = (
    "region_num",
    "region_name",
    "pathway_code",
    "diagnosis_primary",
    "diagnosis_secondary",
    "period",
    "period_start",
    "period_end",
)
NHIF_NUM_COLS = ("n_cases", "n_insured", "year", "month")


def nhif_cases_view(raw: pd.DataFrame, stride: int = NHIF_STRIDE) -> pd.DataFrame:
    """Every ``stride``-th Bulgarian NHIF inpatient claim row with facility pseudonymised."""
    sampled = raw.iloc[::stride]
    data: dict[str, Any] = {col: sampled[col] for col in NHIF_TEXT_COLS}
    data["facility_id"] = [
        pseudonym(str(v)) if pd.notna(v) and str(v) else "" for v in sampled["facility_name"]
    ]
    for col in NHIF_NUM_COLS:
        data[col] = pd.to_numeric(sampled[col], errors="coerce")
    cols = [
        "region_num",
        "region_name",
        "facility_id",
        "pathway_code",
        "diagnosis_primary",
        "diagnosis_secondary",
        "n_cases",
        "n_insured",
        "period",
        "period_start",
        "period_end",
        "year",
        "month",
    ]
    return pd.DataFrame(data)[cols].sort_values(
        ["period", "region_num", "facility_id", "pathway_code", "diagnosis_primary"]
    )


def _build_nhif_cases(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    import gzip

    archive = (
        root / "zen_nhif_hospital_cases" / NHIF_SNAPSHOT / "raw" / "nhif_hospital_cases.csv.gz"
    )
    if not archive.exists():
        raise ViewError("no NHIF hospital cases gzip archive in the snapshot")
    with gzip.open(archive, "rt", encoding="utf-8") as fh:
        raw = pd.read_csv(fh, dtype=str)
    view = nhif_cases_view(raw)
    folder = out / "zen_nhif_hospital_cases"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "hospital_cases.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "zen_nhif_hospital_cases",
        {"hospital_cases.csv": (target, len(view))},
        dropped=[],
        pseudonymised=["facility_name"],
        salt_label=SALT,
        sampling={
            "method": "every 75th record across the sorted NHIF hospitalisation table",
            "total_records": len(raw),
            "stride": NHIF_STRIDE,
            "facilities": int(view["facility_id"].nunique()),
        },
        source_snapshot=f"zen_nhif_hospital_cases/{NHIF_SNAPSHOT}",
    )


INGV_SNAPSHOT = "2026-11-22"
INGV_DROP = ("Author", "Catalog", "Contributor", "ContributorID", "EventLocationName", "MagAuthor")


def ingv_seismic_view(raw: pd.DataFrame) -> pd.DataFrame:
    """Unique INGV ISIDe seismic catalog events with UTC date key sorted chronologically."""
    dedup = raw.drop_duplicates(subset=["#EventID"])
    frame = pd.DataFrame(
        {
            "event_id": dedup["#EventID"],
            "time": dedup["Time"],
            "event_date": dedup["Time"].str.slice(0, 10),
            "latitude": pd.to_numeric(dedup["Latitude"], errors="coerce"),
            "longitude": pd.to_numeric(dedup["Longitude"], errors="coerce"),
            "depth_km": pd.to_numeric(dedup["Depth/Km"], errors="coerce"),
            "mag_type": dedup["MagType"],
            "magnitude": pd.to_numeric(dedup["Magnitude"], errors="coerce"),
            "event_type": dedup["EventType"],
        }
    )
    return frame.sort_values(["time", "event_id"])


def _build_ingv_seismic(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    raw_dir = root / "ingv_seismic_events" / INGV_SNAPSHOT / "raw"
    files = sorted(raw_dir.glob("ingv_*.txt"))
    if not files:
        raise ViewError("no INGV seismic text files in the snapshot")
    raw = pd.concat([pd.read_csv(path, sep="|", dtype=str) for path in files], ignore_index=True)
    view = ingv_seismic_view(raw)
    folder = out / "ingv_seismic_events"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "events.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "ingv_seismic_events",
        {"events.csv": (target, len(view))},
        dropped=sorted(INGV_DROP),
        pseudonymised=[],
        sampling={
            "method": "complete INGV ISIDe FDSNWS catalog queries with minmagnitude>=1.5 across 2022-2024",  # noqa: E501
            "files": [p.name for p in files],
            "days": int(view["event_date"].nunique()),
        },
        source_snapshot=f"ingv_seismic_events/{INGV_SNAPSHOT}",
    )


GHA_SNAPSHOT = "2026-11-22"
GHA_DROP = (
    "author_email",
    "author_name",
    "commit_hash",
    "committer_email",
    "committer_name",
    "uid",
)
GHA_COLS = (
    "repo_id",
    "committed_date",
    "authored_date",
    "file_path",
    "previous_file_path",
    "file_hash",
    "previous_file_hash",
    "git_change_type",
    "valid_yaml",
    "probably_workflow",
    "valid_workflow",
)


def gha_workflows_view(lines: list[str], complete: bool = False) -> tuple[pd.DataFrame, int]:
    """Per-repository GitHub Actions workflow change events without author/committer identities."""
    import csv

    rows = list(csv.DictReader(lines))
    dropped_partial = 0
    if not complete and rows:
        trailing = rows[-1]["repository"]
        kept = [row for row in rows if row["repository"] != trailing]
        dropped_partial = len(rows) - len(kept)
        rows = kept
    frame = pd.DataFrame(
        [
            {
                "repo_id": pseudonym(r["repository"]) if r.get("repository") else "",
                "committed_date": r["committed_date"],
                "authored_date": r["authored_date"],
                "file_path": r["file_path"],
                "previous_file_path": r["previous_file_path"],
                "file_hash": r["file_hash"],
                "previous_file_hash": r["previous_file_hash"],
                "git_change_type": r["git_change_type"],
                "valid_yaml": r["valid_yaml"],
                "probably_workflow": r["probably_workflow"],
                "valid_workflow": r["valid_workflow"],
            }
            for r in rows
        ],
        columns=GHA_COLS,
    )
    for col in ("committed_date", "authored_date"):
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    return (
        frame.sort_values(["repo_id", "committed_date", "file_path", "file_hash"]),
        dropped_partial,
    )


def _build_gha_workflows(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    archive = root / "zen_gha_workflows" / GHA_SNAPSHOT / "raw" / "workflows_prefix.csv.gz"
    if not archive.exists():
        raise ViewError("no GHA workflows gzip prefix in the snapshot")
    lines, complete = gzip_members_lines(archive.read_bytes())
    view, dropped_partial = gha_workflows_view(lines, complete)
    folder = out / "zen_gha_workflows"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "workflows.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "zen_gha_workflows",
        {"workflows.csv": (target, len(view))},
        dropped=list(GHA_DROP),
        pseudonymised=["repository"],
        salt_label=SALT,
        sampling={
            "method": "6 MB gzip prefix of Zenodo 20340547 workflows.csv.gz sorted by repository with trailing partial repository dropped when stream truncated",  # noqa: E501
            "stream_complete": complete,
            "partial_repo_rows_dropped": dropped_partial,
            "repos": int(view["repo_id"].nunique()),
        },
        source_snapshot=f"zen_gha_workflows/{GHA_SNAPSHOT}",
    )


WALS_SNAPSHOT = "2026-11-22"
WALS_PREFIX = "wals-2020.3/cldf/"
WALS_RAW_TABLES = (
    "languages",
    "parameters",
    "codes",
    "values",
    "chapters",
    "areas",
    "countries",
)
WALS_SPEC: dict[str, Any] = {
    "tables": {
        "languages": {
            "keep": [
                "ID",
                "Name",
                "Macroarea",
                "Latitude",
                "Longitude",
                "Glottocode",
                "ISO639P3code",
                "Family",
                "Subfamily",
                "Genus",
                "Country_ID",
                "Parent_ID",
            ]
        },
        "parameters": {"keep": ["ID", "Name", "Chapter_ID"]},
        "codes": {"keep": ["ID", "Parameter_ID", "Name", "Description", "Number"]},
        "values": {"keep": ["ID", "Language_ID", "Parameter_ID", "Value", "Code_ID"]},
        "chapters": {"keep": ["ID", "Name", "Number", "Area_ID"]},
        "areas": {"keep": ["ID", "Name"]},
        "countries": {"keep": ["ID", "Name"]},
        "language_countries": {"keep": ["Language_ID", "Country_ID"]},
    },
    "relations": [
        ["values", "Language_ID", "languages", "ID"],
        ["values", "Parameter_ID", "parameters", "ID"],
        ["values", "Code_ID", "codes", "ID"],
        ["codes", "Parameter_ID", "parameters", "ID"],
        ["parameters", "Chapter_ID", "chapters", "ID"],
        ["chapters", "Area_ID", "areas", "ID"],
        ["languages", "Parent_ID", "languages", "ID"],
        ["language_countries", "Language_ID", "languages", "ID"],
        ["language_countries", "Country_ID", "countries", "ID"],
    ],
}


def wals_cldf_view(
    tables: dict[str, pd.DataFrame],
) -> tuple[dict[str, pd.DataFrame], list[dict[str, Any]]]:
    """Core WALS CLDF relational schema plus normalized language_countries junction table."""
    langs = tables["languages"]
    pairs = {
        (str(lang_id), code)
        for lang_id, raw_codes in langs[["ID", "Country_ID"]].fillna("").to_numpy()
        for code in str(raw_codes).split()
    }
    junction = pd.DataFrame(list(pairs), columns=["Language_ID", "Country_ID"])
    views, relations = tables_view({**tables, "language_countries": junction}, WALS_SPEC)
    ordered = {
        name: frame.sort_values(list(frame.columns)).reset_index(drop=True)
        for name, frame in views.items()
    }
    return ordered, relations


def _build_wals_cldf(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    import zipfile

    archive = root / "wals_cldf" / WALS_SNAPSHOT / "raw" / "wals_v2020.3.zip"
    if not archive.exists():
        raise ViewError("no WALS CLDF zip archive in the snapshot")
    tables: dict[str, pd.DataFrame] = {}
    with zipfile.ZipFile(archive) as zf:
        for name in WALS_RAW_TABLES:
            with zf.open(f"{WALS_PREFIX}{name}.csv") as handle:
                tables[name] = pd.read_csv(handle, dtype=str, keep_default_na=False)
    views, relations = wals_cldf_view(tables)
    folder = out / "wals_cldf"
    folder.mkdir(parents=True, exist_ok=True)
    files: dict[str, tuple[Path, int]] = {}
    for name, frame in views.items():
        target = folder / f"{name}.csv"
        frame.to_csv(target, index=False)
        files[f"{name}.csv"] = (target, len(frame))
    _record(
        manifest,
        "wals_cldf",
        files,
        dropped=[
            "contributors.csv",
            "Contributor_ID",
            "With_Contributor_ID",
            "Contributor",
            "Citation",
            "Source",
            "Comment",
            "Description",
            "examples.csv",
            "media.csv",
            "genealogy.csv",
            "language_names.csv",
        ],
        pseudonymised=[],
        relations=relations,
        sampling={
            "method": "complete 7 core CLDF linguistic typology tables plus normalized language_countries junction table (no row sampling)"  # noqa: E501
        },
        source_snapshot=f"wals_cldf/{WALS_SNAPSHOT}",
    )


CORDIS_SNAPSHOT = "2026-11-22"
CORDIS_PROJECT_COLS = (
    "id",
    "acronym",
    "status",
    "startDate",
    "endDate",
    "totalCost",
    "ecMaxContribution",
    "topics",
    "ecSignatureDate",
    "frameworkProgramme",
    "masterCall",
    "subCall",
    "fundingScheme",
    "nature",
    "contentUpdateDate",
    "rcn",
    "grantDoi",
    "Human-validated",
    "legalBasis",
)
CORDIS_SPEC: dict[str, Any] = {
    "tables": {
        "project": {"keep": list(CORDIS_PROJECT_COLS)},
        "organization": {
            "keep": [
                "projectID",
                "projectAcronym",
                "org_id",
                "SME",
                "activityType",
                "country",
                "nutsCode",
                "contentUpdateDate",
                "rcn",
                "order",
                "role",
                "ecContribution",
                "netEcContribution",
                "totalCost",
                "endOfParticipation",
                "active",
            ]
        },
        "euroSciVoc": {
            "keep": [
                "euroSciVocCode",
                "euroSciVocPath",
                "euroSciVocTitle",
                "euroSciVocDescription",
                "projectID",
            ]
        },
        "topics": {"keep": ["topic", "title", "projectID"]},
        "legalBasis": {"keep": ["legalBasis", "title", "uniqueProgrammePart", "projectID"]},
        "policyPriorities": {
            "keep": ["ai", "biodiversity", "cleanAir", "climate", "digitalAgenda", "projectID"]
        },
    },
    "relations": [
        ["organization", "projectID", "project", "id"],
        ["euroSciVoc", "projectID", "project", "id"],
        ["topics", "projectID", "project", "id"],
        ["legalBasis", "projectID", "project", "id"],
        ["policyPriorities", "projectID", "project", "id"],
    ],
}


def parse_cordis_projects(text: str) -> pd.DataFrame:
    """Reconstruct wrapped CORDIS ``project.csv`` lines and extract structured project columns."""
    lines = text.splitlines()
    records: list[str] = []
    for line in lines[1:]:
        if re.match(r'^"\d+";"', line):
            records.append(line)
        elif records:
            records[-1] += " " + line
    rows = []
    for rec in records:
        body = rec[1:-1]
        head = body.split('";"', 15)
        tail = body.rsplit('";"', 6)
        rows.append(
            [
                head[0],
                head[1],
                head[2],
                head[4],
                head[5],
                head[6],
                head[7],
                head[8],
                head[9],
                head[10],
                head[11],
                head[12],
                head[13],
                head[14],
                tail[1],
                tail[2],
                tail[3],
                tail[5],
                tail[6],
            ]
        )
    return pd.DataFrame(rows, columns=CORDIS_PROJECT_COLS)


def cordis_horizon_view(
    tables: dict[str, pd.DataFrame],
) -> tuple[dict[str, pd.DataFrame], list[dict[str, Any]]]:
    """Six-table CORDIS Horizon Europe schema without free text or identifying org fields."""
    org = tables["organization"].copy()
    org["org_id"] = [
        pseudonym(str(v)) if pd.notna(v) and str(v) else "" for v in org["organisationID"]
    ]
    views, relations = tables_view({**tables, "organization": org}, CORDIS_SPEC)
    ordered = {
        name: frame.sort_values(list(frame.columns)).reset_index(drop=True)
        for name, frame in views.items()
    }
    return ordered, relations


def _build_cordis_horizon(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    import zipfile

    archive = root / "cordis_horizon_europe" / CORDIS_SNAPSHOT / "raw" / "cordis_horizon_csv.zip"
    if not archive.exists():
        raise ViewError("no CORDIS Horizon Europe zip archive in the snapshot")
    tables: dict[str, pd.DataFrame] = {}
    with zipfile.ZipFile(archive) as zf:
        tables["project"] = parse_cordis_projects(zf.read("project.csv").decode("utf-8"))
        for name in CORDIS_SPEC["tables"]:
            if name == "project":
                continue
            with zf.open(f"{name}.csv") as handle:
                tables[name] = pd.read_csv(handle, sep=";", dtype=str)
    views, relations = cordis_horizon_view(tables)
    folder = out / "cordis_horizon_europe"
    folder.mkdir(parents=True, exist_ok=True)
    files: dict[str, tuple[Path, int]] = {}
    for name, frame in views.items():
        target = folder / f"{name}.csv"
        frame.to_csv(target, index=False)
        files[f"{name}.csv"] = (target, len(frame))
    _record(
        manifest,
        "cordis_horizon_europe",
        files,
        dropped=[
            "project.title",
            "project.objective",
            "project.keywords",
            "organization.name",
            "organization.shortName",
            "organization.vatNumber",
            "organization.street",
            "organization.postCode",
            "organization.city",
            "organization.geolocation",
            "organization.organizationURL",
            "organization.contactForm",
            "webItem.csv",
            "webLink.csv",
        ],
        pseudonymised=["organisationID"],
        salt_label=SALT,
        relations=relations,
        sampling={
            "method": "complete 6 core CORDIS Horizon Europe tables (no row sampling); projects parsed across wrapped quotes",  # noqa: E501
        },
        source_snapshot=f"cordis_horizon_europe/{CORDIS_SNAPSHOT}",
    )


WAVE24_SNAPSHOT = "2026-11-22"


def telecom_kpis_view(named_texts: list[tuple[str, str]]) -> pd.DataFrame:
    """Five-minute real telecom operator KPI time series ordered by series_id and elapsed_s."""
    rows: list[tuple[str, int, float]] = []
    for series_id, text in named_texts:
        for line in text.splitlines():
            parts = line.split()
            if len(parts) == 2:
                rows.append((series_id, int(parts[0]), float(parts[1])))
    frame = pd.DataFrame(rows, columns=["series_id", "elapsed_s", "kpi_value"])
    return frame.sort_values(["series_id", "elapsed_s"]).reset_index(drop=True)


def _build_telecom_kpis(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    import zipfile

    archive = (
        root
        / "zen_telecom_kpis"
        / WAVE24_SNAPSHOT
        / "raw"
        / "network_operator_KPIs_time_series_dataset.zip"  # noqa: E501
    )
    if not archive.exists():
        raise ViewError("no telecom KPI archive in the snapshot")
    with zipfile.ZipFile(archive) as zf:
        members = sorted(n for n in zf.namelist() if "/data_real/" in n and n.endswith(".txt"))
        named = [(Path(n).stem, zf.read(n).decode("utf-8")) for n in members]
    view = telecom_kpis_view(named)
    folder = out / "zen_telecom_kpis"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "telecom_kpis.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "zen_telecom_kpis",
        {"telecom_kpis.csv": (target, len(view))},
        dropped=["data_series/"],
        pseudonymised=[],
        sampling={
            "max_elapsed_s": int(view["elapsed_s"].max()),
            "method": "complete 14 real telecom operator KPI traces from data_real/ (300s elapsed cadence)",  # noqa: E501
            "min_elapsed_s": int(view["elapsed_s"].min()),
            "series_count": int(view["series_id"].nunique()),
        },
        source_snapshot=f"zen_telecom_kpis/{WAVE24_SNAPSHOT}",
    )


def dk_heating_view(dma_frames: list[tuple[str, pd.DataFrame, pd.DataFrame]]) -> pd.DataFrame:
    """Hourly Danish district heating demand and active-meter counts per DMA in UTC."""
    parts = []
    for dma_id, agg, meters in dma_frames:
        a = agg.rename(columns={"Unnamed: 0": "ts", "cons": "consumption_kwh"})
        m = meters.rename(columns={"Unnamed: 0": "ts"})
        merged = a.merge(m, how="outer")
        parts.append(
            pd.DataFrame(
                {
                    "dma_id": dma_id,
                    "timestamp": pd.to_datetime(merged["ts"], utc=True, errors="coerce"),
                    "consumption_kwh": pd.to_numeric(merged["consumption_kwh"], errors="coerce"),
                    "contributing_meters": pd.to_numeric(
                        merged["contributing_meters"], errors="coerce"
                    ).astype("Int64"),
                }
            )
        )
    frame = pd.concat(parts)
    return (
        frame[frame["timestamp"].notna()]
        .sort_values(["dma_id", "timestamp"])
        .reset_index(drop=True)
    )


def _build_dk_heating(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    raw_dir = root / "zen_dk_district_heating" / WAVE24_SNAPSHOT / "raw"
    dma_frames: list[tuple[str, pd.DataFrame, pd.DataFrame]] = []
    for dma in ("a", "b", "c"):
        agg_p = raw_dir / f"dma_{dma}_aggregated.csv"
        met_p = raw_dir / f"dma_{dma}_contributing_meters.csv"
        if not agg_p.exists() or not met_p.exists():
            raise ViewError("no Danish district heating CSVs in the snapshot")
        dma_frames.append((f"dma_{dma}", pd.read_csv(agg_p), pd.read_csv(met_p)))
    view = dk_heating_view(dma_frames)
    folder = out / "zen_dk_district_heating"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "district_heating.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "zen_dk_district_heating",
        {"district_heating.csv": (target, len(view))},
        dropped=["dma_*_norm_aggregated.csv", "weather.csv"],
        pseudonymised=[],
        sampling={
            "dmas": int(view["dma_id"].nunique()),
            "first_timestamp": str(view["timestamp"].min()),
            "last_timestamp": str(view["timestamp"].max()),
            "method": "complete 3-DMA hourly raw consumption and contributing-meter series (2016-2019 UTC)",  # noqa: E501
        },
        source_snapshot=f"zen_dk_district_heating/{WAVE24_SNAPSHOT}",
    )


def water_demand_view(raw: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Raw hourly municipal water pumping demand and local weather, deduplicated on DST fallback."""
    hh = raw["Time"].astype(str).str.strip().str[:2]
    ts = pd.to_datetime(
        raw["Date"].astype(str).str.strip() + " " + hh,
        format="%m/%d/%Y %H",
        errors="coerce",
    )
    frame = pd.DataFrame(
        {
            "timestamp": ts,
            "consumption_m3": pd.to_numeric(raw["Consumption"], errors="coerce"),
            "temperature_c": pd.to_numeric(raw["Temperature"], errors="coerce"),
            "rain_mm": pd.to_numeric(raw["Rain"], errors="coerce"),
            "sun_min": pd.to_numeric(raw["Sun"], errors="coerce"),
        }
    )
    valid = frame[frame["timestamp"].notna()]
    dups = int(valid.duplicated("timestamp").sum())
    deduped = valid.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
    return deduped, dups


def _build_water_demand(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    source = root / "zen_water_demand" / WAVE24_SNAPSHOT / "raw" / "waterconsumption_rawdata.csv"
    if not source.exists():
        raise ViewError("no water demand CSV in the snapshot")
    view, dups = water_demand_view(pd.read_csv(source))
    folder = out / "zen_water_demand"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "water_demand.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "zen_water_demand",
        {"water_demand.csv": (target, len(view))},
        dropped=[],
        pseudonymised=[],
        sampling={
            "duplicates_dropped": dups,
            "first_timestamp": str(view["timestamp"].min()),
            "last_timestamp": str(view["timestamp"].max()),
            "method": "complete un-imputed raw hourly water pumping series (2016-2021)",
            "missing_consumption_rows": int(view["consumption_m3"].isna().sum()),
            "missing_rain_rows": int(view["rain_mm"].isna().sum()),
        },
        source_snapshot=f"zen_water_demand/{WAVE24_SNAPSHOT}",
    )


DMSP_NUM_COLS: tuple[tuple[str, str], ...] = (
    ("fom", "FOM"),
    ("lat_eq1", "SC_GEOCENTRIC_LAT EQ1"),
    ("lat_po1", "SC_GEOCENTRIC_LAT PO1"),
    ("lat_po2", "SC_GEOCENTRIC_LAT PO2"),
    ("lat_eq2", "SC_GEOCENTRIC_LAT EQ2"),
    ("lon_eq1", "SC_GEOCENTRIC_LON EQ1"),
    ("lon_po1", "SC_GEOCENTRIC_LON PO1"),
    ("lon_po2", "SC_GEOCENTRIC_LON PO2"),
    ("lon_eq2", "SC_GEOCENTRIC_LON EQ2"),
    ("mlat_eq1", "mlat EQ1"),
    ("mlat_po1", "mlat PO1"),
    ("mlat_po2", "mlat PO2"),
    ("mlat_eq2", "mlat EQ2"),
    ("mlt_eq1", "mlt EQ1"),
    ("mlt_po1", "mlt PO1"),
    ("mlt_po2", "mlt PO2"),
    ("mlt_eq2", "mlt EQ2"),
)
_DMSP_NAME = re.compile(r"dmsp-(f\d+)_.*?_(\d{8})_")


def dmsp_auroral_view(named_frames: list[tuple[str, str, pd.DataFrame]]) -> pd.DataFrame:
    """DMSP polar-orbit auroral boundary telemetry ordered by spacecraft and UTC pass start."""
    parts = []
    for spacecraft, day, raw in named_frames:
        start_s = pd.to_numeric(raw["UTSecond Pass Start"], errors="coerce")
        end_s = pd.to_numeric(raw["UTSecond Pass End"], errors="coerce")
        data: dict[str, Any] = {
            "spacecraft": spacecraft,
            "timestamp": pd.to_datetime(day, format="%Y%m%d", utc=True)
            + pd.to_timedelta(start_s, unit="s"),
            "pass_duration_s": end_s - start_s,
            "hemisphere": pd.to_numeric(raw["hemisphere"], errors="coerce").astype("Int64"),
        }
        for out_col, src_col in DMSP_NUM_COLS:
            data[out_col] = pd.to_numeric(raw[src_col], errors="coerce")
        parts.append(pd.DataFrame(data))
    combined = pd.concat(parts)
    return (
        combined[combined["timestamp"].notna()]
        .sort_values(["spacecraft", "timestamp"])
        .reset_index(drop=True)
    )


def _build_dmsp_auroral(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    import zipfile

    archive = (
        root
        / "zen_dmsp_auroral"
        / WAVE24_SNAPSHOT
        / "raw"
        / "fom_boundaries_F16_F17_F18_2010_2014.zip"  # noqa: E501
    )
    if not archive.exists():
        raise ViewError("no DMSP auroral archive in the snapshot")
    named_frames: list[tuple[str, str, pd.DataFrame]] = []
    with zipfile.ZipFile(archive) as zf:
        for name in sorted(n for n in zf.namelist() if n.endswith(".csv")):
            match = _DMSP_NAME.search(Path(name).name)
            if not match:
                continue
            df = pd.read_csv(io.BytesIO(zf.read(name)), comment="#")
            if not df.empty:
                named_frames.append((match.group(1).upper(), match.group(2), df))
    view = dmsp_auroral_view(named_frames)
    folder = out / "zen_dmsp_auroral"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "dmsp_auroral.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "zen_dmsp_auroral",
        {"dmsp_auroral.csv": (target, len(view))},
        dropped=["UTSec EQ1", "UTSec PO1", "UTSec PO2", "UTSec EQ2"],
        pseudonymised=[],
        sampling={
            "files_loaded": len(named_frames),
            "first_timestamp": str(view["timestamp"].min()),
            "last_timestamp": str(view["timestamp"].max()),
            "method": "complete 2010-2014 DMSP F16/F17/F18 polar-orbit auroral boundary passes",
            "spacecrafts": int(view["spacecraft"].nunique()),
        },
        source_snapshot=f"zen_dmsp_auroral/{WAVE24_SNAPSHOT}",
    )


DTS_TEXT_COLS = ("record_date", "account_type", "transaction_type", "transaction_catg")
DTS_NUM_COLS = (
    "transaction_today_amt",
    "transaction_mtd_amt",
    "transaction_fytd_amt",
    "record_fiscal_year",
    "record_fiscal_quarter",
    "src_line_nbr",
)


def treasury_dts_view(records: list[dict[str, Any]]) -> pd.DataFrame:
    """U.S. Daily Treasury Statement operating cash ledger rows sorted by date and line."""
    rows = [{c: r.get(c) for c in (*DTS_TEXT_COLS, *DTS_NUM_COLS)} for r in records]
    frame = pd.DataFrame(rows, columns=[*DTS_TEXT_COLS, *DTS_NUM_COLS])
    for col in DTS_NUM_COLS:
        frame[col] = _num_clean(frame[col])
    return (
        frame[frame["record_date"].notna()]
        .sort_values(
            [
                "record_date",
                "src_line_nbr",
                "account_type",
                "transaction_type",
                "transaction_catg",
            ]
        )
        .reset_index(drop=True)
    )


def _build_treasury_dts(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    files = sorted(
        (root / "us_treasury_dts" / WAVE24_SNAPSHOT / "raw").glob("dts_2024_2025_p*.json")
    )
    if not files:
        raise ViewError("no US Treasury DTS JSON files in the snapshot")
    records: list[dict[str, Any]] = []
    for path in files:
        records.extend(json.loads(path.read_text()).get("data", []))
    view = treasury_dts_view(records)
    folder = out / "us_treasury_dts"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "dts_operating_cash.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "us_treasury_dts",
        {"dts_operating_cash.csv": (target, len(view))},
        dropped=[
            "transaction_catg_desc",
            "table_nbr",
            "table_nm",
            "record_calendar_year",
            "record_calendar_quarter",
            "record_calendar_month",
            "record_calendar_day",
        ],
        pseudonymised=[],
        sampling={
            "first_date": str(view["record_date"].min()),
            "last_date": str(view["record_date"].max()),
            "method": "complete 2024-01-01 to 2025-12-31 Daily Treasury Statement Table II release",  # noqa: E501
            "pages": len(files),
        },
        source_snapshot=f"us_treasury_dts/{WAVE24_SNAPSHOT}",
    )


FDIC_NUM_COLS = (
    "ASSET",
    "DEP",
    "EQ",
    "NETINC",
    "INTINC",
    "EINTEXP",
    "LNLSNET",
    "ROA",
    "ROE",
    "RBCRWAJ",
    "NUMEMP",
    "OFFDOM",
)
FDIC_OUT_COLS = (
    "cert_id",
    "repdte",
    "bkclass",
    "stalp",
    *(c.lower() for c in FDIC_NUM_COLS),
)


def fdic_financials_view(records: list[dict[str, Any]]) -> pd.DataFrame:
    """FDIC year-end Call Report bank financials with salted pseudonymised CERT ids."""
    rows = []
    for rec in records:
        cert = rec.get("CERT")
        if cert is None:
            continue
        row: dict[str, Any] = {
            "cert_id": pseudonym(str(cert)),
            "repdte": rec.get("REPDTE"),
            "bkclass": rec.get("BKCLASS"),
            "stalp": rec.get("STALP"),
        }
        for col in FDIC_NUM_COLS:
            row[col.lower()] = rec.get(col)
        rows.append(row)
    frame = pd.DataFrame(rows, columns=list(FDIC_OUT_COLS))
    for col in FDIC_NUM_COLS:
        frame[col.lower()] = pd.to_numeric(frame[col.lower()], errors="coerce")
    return frame.sort_values(["repdte", "cert_id"]).reset_index(drop=True)


def _build_fdic_financials(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    files = sorted((root / "fdic_bank_financials" / WAVE24_SNAPSHOT / "raw").glob("fdic_*.json"))
    if not files:
        raise ViewError("no FDIC bank financials JSON files in the snapshot")
    records: list[dict[str, Any]] = []
    for path in files:
        records.extend(item["data"] for item in json.loads(path.read_text()).get("data", []))
    view = fdic_financials_view(records)
    folder = out / "fdic_bank_financials"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "bank_financials.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "fdic_bank_financials",
        {"bank_financials.csv": (target, len(view))},
        dropped=["ID"],
        pseudonymised=["CERT"],
        salt_label=SALT,
        sampling={
            "institutions": int(view["cert_id"].nunique()),
            "method": "four complete year-end cross-sections (REPDTE 20221231-20251231)",
            "snapshots": len(files),
        },
        source_snapshot=f"fdic_bank_financials/{WAVE24_SNAPSHOT}",
    )


SNCF_TEXT_COLS = ("date", "service", "gare_depart", "gare_arrivee")
SNCF_NUM_COLS = (
    "duree_moyenne",
    "nb_train_prevu",
    "nb_annulation",
    "nb_train_depart_retard",
    "retard_moyen_depart",
    "retard_moyen_tous_trains_depart",
    "nb_train_retard_arrivee",
    "retard_moyen_arrivee",
    "retard_moyen_tous_trains_arrivee",
    "nb_train_retard_sup_15",
    "retard_moyen_trains_retard_sup15",
    "nb_train_retard_sup_30",
    "nb_train_retard_sup_60",
    "prct_cause_externe",
    "prct_cause_infra",
    "prct_cause_gestion_trafic",
    "prct_cause_materiel_roulant",
    "prct_cause_gestion_gare",
    "prct_cause_prise_en_charge_voyageurs",
)


def sncf_tgv_view(raw: pd.DataFrame) -> pd.DataFrame:
    """Monthly SNCF TGV route punctuality ledger without free-text comments."""
    data: dict[str, Any] = {col: raw[col].astype(str) for col in SNCF_TEXT_COLS}
    for col in SNCF_NUM_COLS:
        data[col] = pd.to_numeric(raw[col], errors="coerce")
    frame = pd.DataFrame(data)
    return frame.sort_values(list(SNCF_TEXT_COLS)).reset_index(drop=True)


def _build_sncf_tgv(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    source = root / "sncf_tgv_regularite" / WAVE24_SNAPSHOT / "raw" / "sncf_tgv_regularite.csv"
    if not source.exists():
        raise ViewError("no SNCF TGV regularity CSV in the snapshot")
    view = sncf_tgv_view(pd.read_csv(source, sep=";", dtype=str))
    folder = out / "sncf_tgv_regularite"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "tgv_regularity.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "sncf_tgv_regularite",
        {"tgv_regularity.csv": (target, len(view))},
        dropped=[
            "commentaire_annulation",
            "commentaire_retards_depart",
            "commentaires_retard_arrivee",
        ],
        pseudonymised=[],
        sampling={
            "first_month": str(view["date"].min()),
            "last_month": str(view["date"].max()),
            "method": "complete monthly SNCF TGV route punctuality and delay-cause ledger",
        },
        source_snapshot=f"sncf_tgv_regularite/{WAVE24_SNAPSHOT}",
    )


DGCCRF_FUELS = ("gazole", "sp95", "e85", "gplc", "e10", "sp98")
DGCCRF_COLS = (
    "station_id",
    "pop",
    "code_departement",
    "code_region",
    "automate_24_24",
    "fuel_type",
    "price_eur",
    "price_updated_at",
)


def dgccrf_fuel_view(raw: pd.DataFrame) -> pd.DataFrame:
    """French retail fuel station price postings melted across all six fuels with salted ids."""
    station_ids = raw["id"].map(pseudonym)
    parts = []
    for fuel in DGCCRF_FUELS:
        prices = pd.to_numeric(raw[f"{fuel}_prix"], errors="coerce")
        sub = pd.DataFrame(
            {
                "station_id": station_ids,
                "pop": raw["pop"],
                "code_departement": raw["code_departement"],
                "code_region": raw["code_region"],
                "automate_24_24": raw["horaires_automate_24_24"],
                "fuel_type": fuel,
                "price_eur": prices,
                "price_updated_at": raw[f"{fuel}_maj"],
            }
        )
        parts.append(sub[prices.notna()])
    frame = pd.concat(parts)
    return frame[list(DGCCRF_COLS)].sort_values(["station_id", "fuel_type"]).reset_index(drop=True)


def _build_dgccrf_fuel(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    source = root / "dgccrf_fuel_prices" / WAVE24_SNAPSHOT / "raw" / "dgccrf_fuel_prices.csv"
    if not source.exists():
        raise ViewError("no DGCCRF fuel prices CSV in the snapshot")
    view = dgccrf_fuel_view(pd.read_csv(source, sep=";", dtype=str))
    folder = out / "dgccrf_fuel_prices"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "fuel_prices.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "dgccrf_fuel_prices",
        {"fuel_prices.csv": (target, len(view))},
        dropped=[
            "adresse",
            "ville",
            "cp",
            "latitude",
            "longitude",
            "horaires",
            "services",
            "prix",
            "rupture",
            "geom",
            "horaires_jour",
            "services_service",
            "departement",
            "region",
            "carburants_*",
            "*_rupture_*",
        ],
        pseudonymised=["id"],
        salt_label=SALT,
        sampling={
            "method": "point-in-time national convenience snapshot melted to non-null per-fuel price postings",  # noqa: E501
            "stations": int(view["station_id"].nunique()),
        },
        source_snapshot=f"dgccrf_fuel_prices/{WAVE24_SNAPSHOT}",
    )


def federal_register_view(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Unique Federal Register regulatory documents ordered by document_number, e-mails redacted."""  # noqa: E501
    unique: dict[str, dict[str, Any]] = {}
    for record in records:
        unique.setdefault(record["document_number"], record)
    return redact_emails(
        nested_view(list(unique.values()), frozenset(), lambda r: r["document_number"])
    )


def _build_federal_register(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    raw = root / "us_federal_register" / WAVE24_SNAPSHOT / "raw"
    files = sorted(raw.glob("fr_2025_p*.json"))
    if not files:
        raise ViewError("no Federal Register JSON in the snapshot")
    records: list[dict[str, Any]] = []
    for path in files:
        records += json.loads(path.read_text())["results"]
    view = federal_register_view(records)
    target = _write_jsonl(out / "us_federal_register", "documents.jsonl", view)
    _record(
        manifest,
        "us_federal_register",
        {"documents.jsonl": (target, len(view))},
        dropped=[],
        pseudonymised=[],
        sampling={
            "documents_in": len(records),
            "files": [p.name for p in files],
            "method": "oldest 20 pages x 100 published in 2025 from Federal Register API v1",
            "unique_documents": len(view),
        },
        source_snapshot=f"us_federal_register/{WAVE24_SNAPSHOT}",
    )


DATACITE_DROP = frozenset({"creators", "contributors", "descriptions"})


def datacite_dois_view(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Unique DataCite dataset DOIs without creator/contributor/description fields, e-mails redacted."""  # noqa: E501
    unique: dict[str, dict[str, Any]] = {}
    for record in records:
        unique.setdefault(record["id"], record)
    cleaned = nested_view(list(unique.values()), DATACITE_DROP, lambda r: r["id"])
    return redact_emails(cleaned)


def _build_datacite_dois(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    raw = root / "datacite_dois" / WAVE24_SNAPSHOT / "raw"
    files = sorted(raw.glob("datacite_2025_p*.json"))
    if not files:
        raise ViewError("no DataCite DOI JSON in the snapshot")
    records: list[dict[str, Any]] = []
    for path in files:
        records += json.loads(path.read_text())["data"]
    view = datacite_dois_view(records)
    target = _write_jsonl(out / "datacite_dois", "dois.jsonl", view)
    _record(
        manifest,
        "datacite_dois",
        {"dois.jsonl": (target, len(view))},
        dropped=sorted(DATACITE_DROP),
        pseudonymised=[],
        sampling={
            "dois_in": len(records),
            "files": [p.name for p in files],
            "method": "created-ordered first 10 pages x 100 of published=2025 dataset DOIs",
            "unique_dois": len(view),
        },
        source_snapshot=f"datacite_dois/{WAVE24_SNAPSHOT}",
    )


GBIF_LICENSE = "http://creativecommons.org/publicdomain/zero/1.0/legalcode"
GBIF_DROP = frozenset(
    {
        "recordedBy",
        "identifiedBy",
        "recordedByIDs",
        "identifiedByIDs",
        "georeferencedBy",
        "verbatimIdentification",
        "occurrenceRemarks",
        "eventRemarks",
        "locality",
        "verbatimLocality",
        "fieldNotes",
        "rightsHolder",
        "preparations",
        "creator",
    }
)


def gbif_cc0_view(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Unique CC0 GBIF occurrences without collector/locality/media-creator fields, e-mails redacted."""  # noqa: E501
    unique: dict[int, dict[str, Any]] = {}
    for record in records:
        if record.get("license") == GBIF_LICENSE:
            unique.setdefault(record["key"], record)
    cleaned = nested_view(list(unique.values()), GBIF_DROP, lambda r: r["key"])
    return redact_emails(cleaned)


def _build_gbif_cc0(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    raw = root / "gbif_cc0_occurrences" / WAVE24_SNAPSHOT / "raw"
    files = sorted(raw.glob("gbif_cc0_2024_p*.json"))
    if not files:
        raise ViewError("no GBIF occurrence JSON in the snapshot")
    records: list[dict[str, Any]] = []
    for path in files:
        records += json.loads(path.read_text())["results"]
    view = gbif_cc0_view(records)
    target = _write_jsonl(out / "gbif_cc0_occurrences", "occurrences.jsonl", view)
    _record(
        manifest,
        "gbif_cc0_occurrences",
        {"occurrences.jsonl": (target, len(view))},
        dropped=sorted(GBIF_DROP),
        pseudonymised=[],
        sampling={
            "files": [p.name for p in files],
            "method": "offset prefix 5 pages x 300 of 2024 georeferenced CC0_1_0 occurrences",
            "records_in": len(records),
            "unique_occurrences": len(view),
        },
        source_snapshot=f"gbif_cc0_occurrences/{WAVE24_SNAPSHOT}",
    )


def chembl_molecules_view(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Unique ChEMBL molecule JSON records ordered by molecule_chembl_id, e-mails redacted."""
    unique: dict[str, dict[str, Any]] = {}
    for record in records:
        unique.setdefault(record["molecule_chembl_id"], record)
    return redact_emails(
        nested_view(list(unique.values()), frozenset(), lambda r: r["molecule_chembl_id"])
    )


def _build_chembl_molecules(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    raw = root / "chembl_molecules" / WAVE24_SNAPSHOT / "raw"
    files = sorted(raw.glob("chembl_mol_p*.json"))
    if not files:
        raise ViewError("no ChEMBL molecule JSON in the snapshot")
    records: list[dict[str, Any]] = []
    for path in files:
        records += json.loads(path.read_text())["molecules"]
    view = chembl_molecules_view(records)
    target = _write_jsonl(out / "chembl_molecules", "molecules.jsonl", view)
    _record(
        manifest,
        "chembl_molecules",
        {"molecules.jsonl": (target, len(view))},
        dropped=[],
        pseudonymised=[],
        sampling={
            "files": [p.name for p in files],
            "method": "identifier-ordered prefix 10 pages x 100 of ChEMBL_37 molecules",
            "molecules_in": len(records),
            "unique_molecules": len(view),
        },
        source_snapshot=f"chembl_molecules/{WAVE24_SNAPSHOT}",
    )


FL_CAT_COLS = (
    "highway_district_002",
    "county_code_003",
    "maintenance_021",
    "owner_022",
    "functional_class_026",
    "service_on_042a",
    "service_und_042b",
    "structure_kind_043a",
    "structure_type_043b",
    "deck_cond_058",
    "superstructure_cond_059",
    "substructure_cond_060",
    "date_of_inspect_090",
    "traffic_direction_102",
    "surface_type_108a",
    "bridge_condition",
    "date",
    "flood_risk_class",
    "svi_class",
)
FL_NUM_COLS = (
    "year_built_027",
    "adt_029",
    "year_adt_030",
    "structure_len_mt_049",
    "inspect_freq_months_091",
    "year_reconstructed_106",
    "percent_adt_truck_109",
    "future_adt_114",
    "year_of_future_adt_115",
    "lowest_rating",
    "latitude",
    "longitude",
    "svi_score",
)


def florida_bridges_view(raw: pd.DataFrame) -> pd.DataFrame:
    """Florida bridge inspection inventory preserving 'N' rating semantics and salted bridge ids."""  # noqa: E501
    data: dict[str, Any] = {
        "bridge_id": raw["bridge_id"].map(pseudonym),
        **{col: raw[col] for col in FL_CAT_COLS},
    }
    for col in FL_NUM_COLS:
        data[col] = pd.to_numeric(raw[col], errors="coerce")
    return pd.DataFrame(data).sort_values("bridge_id").reset_index(drop=True)


def _build_florida_bridges(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    source = (
        root
        / "zen_florida_bridges"
        / WAVE24_SNAPSHOT
        / "raw"
        / "DATA_Florida_BridgeInspection_Version1_0.csv"
    )
    if not source.exists():
        raise ViewError("no Florida bridge inspection CSV in the snapshot")
    view = florida_bridges_view(pd.read_csv(source, dtype=str))
    folder = out / "zen_florida_bridges"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "bridges.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "zen_florida_bridges",
        {"bridges.csv": (target, len(view))},
        dropped=[
            "objectid",
            "location_009",
            "fracture_last_date_093a",
            "undwater_last_date_093b",
            "spec_last_date_093c",
        ],
        pseudonymised=["bridge_id"],
        salt_label=SALT,
        sampling={"method": "complete Florida bridge structural inspection v1.0 release"},
        source_snapshot=f"zen_florida_bridges/{WAVE24_SNAPSHOT}",
    )


WRI_TEXT_COLS = (
    "gppd_idnr",
    "country",
    "country_long",
    "primary_fuel",
    "source",
    "geolocation_source",
    "estimated_generation_note_2013",
    "estimated_generation_note_2014",
    "estimated_generation_note_2015",
    "estimated_generation_note_2016",
    "estimated_generation_note_2017",
)
WRI_NUM_COLS = (
    "capacity_mw",
    "latitude",
    "longitude",
    "estimated_generation_gwh_2016",
    "estimated_generation_gwh_2017",
)


def wri_power_plants_view(raw: pd.DataFrame) -> pd.DataFrame:
    """Global Power Plant Database v1.3.0 without identifying names/owners or >50%-missing cols."""  # noqa: E501
    data: dict[str, Any] = {col: raw[col] for col in WRI_TEXT_COLS}
    for col in WRI_NUM_COLS:
        data[col] = pd.to_numeric(raw[col], errors="coerce")
    return pd.DataFrame(data).sort_values("gppd_idnr").reset_index(drop=True)


def _build_wri_power_plants(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    source = root / "wri_power_plants" / WAVE24_SNAPSHOT / "raw" / "global_power_plant_database.csv"
    if not source.exists():
        raise ViewError("no WRI global power plant CSV in the snapshot")
    view = wri_power_plants_view(pd.read_csv(source, dtype=str))
    folder = out / "wri_power_plants"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "power_plants.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "wri_power_plants",
        {"power_plants.csv": (target, len(view))},
        dropped=[
            "name",
            "owner",
            "url",
            "wepp_id",
            "other_fuel1",
            "other_fuel2",
            "other_fuel3",
            "commissioning_year",
            "year_of_capacity_data",
            "generation_gwh_2013..2019",
            "generation_data_source",
            "estimated_generation_gwh_2013..2015",
        ],
        pseudonymised=[],
        sampling={
            "countries": int(view["country"].nunique()),
            "method": "complete Global Power Plant Database v1.3.0 CSV release",
        },
        source_snapshot=f"wri_power_plants/{WAVE24_SNAPSHOT}",
    )


PARIS_TEXT_COLS = (
    "idbase",
    "domanialite",
    "arrondissement",
    "libellefrancais",
    "genre",
    "espece",
    "stadedeveloppement",
    "remarquable",
)
PARIS_NUM_COLS = ("circonferenceencm", "hauteurenm")


def paris_trees_view(raw: pd.DataFrame) -> pd.DataFrame:
    """City of Paris tree inventory without addresses/coordinates or >50%-missing columns."""
    data: dict[str, Any] = {col: raw[col] for col in PARIS_TEXT_COLS}
    for col in PARIS_NUM_COLS:
        data[col] = pd.to_numeric(raw[col], errors="coerce")
    return pd.DataFrame(data).sort_values("idbase").reset_index(drop=True)


def _build_paris_trees(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    source = root / "paris_urban_trees" / WAVE24_SNAPSHOT / "raw" / "les_arbres_25k.csv"
    if not source.exists():
        raise ViewError("no Paris urban trees CSV in the snapshot")
    view = paris_trees_view(pd.read_csv(source, sep=";", dtype=str))
    folder = out / "paris_urban_trees"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "trees.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "paris_urban_trees",
        {"trees.csv": (target, len(view))},
        dropped=[
            "typeemplacement",
            "complementadresse",
            "adresse",
            "idemplacement",
            "varieteoucultivar",
            "geo_point_2d",
        ],
        pseudonymised=[],
        sampling={
            "genera": int(view["genre"].nunique()),
            "method": "first 25,000 trees ordered ascending by idbase",
        },
        source_snapshot=f"paris_urban_trees/{WAVE24_SNAPSHOT}",
    )


def moodle_events_view(raw: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    """Moodle LMS clickstream events with English labels, UTC timestamps and salted user ids."""  # noqa: E501
    epochs = pd.to_numeric(raw["timecreated"], errors="coerce")
    frame = pd.DataFrame(
        {
            "user_id": raw["userid"].map(pseudonym),
            "timestamp": pd.to_datetime(epochs, unit="s", utc=True),
            "activity": raw["eventname"].map(lambda k: mapping.get(k, k)),
            "event_code": raw["eventname"],
        }
    )
    return (
        frame[frame["timestamp"].notna()]
        .sort_values(["user_id", "timestamp", "event_code"])
        .reset_index(drop=True)
    )


def _build_moodle_events(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    raw_dir = root / "zen_moodle_events" / WAVE24_SNAPSHOT / "raw"
    csv_p = raw_dir / "dataset-anon.csv"
    map_p = raw_dir / "moodle_activity_mapping_EN.json"
    if not csv_p.exists() or not map_p.exists():
        raise ViewError("no Moodle event log files in the snapshot")
    view = moodle_events_view(pd.read_csv(csv_p, dtype=str), json.loads(map_p.read_text()))
    folder = out / "zen_moodle_events"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "moodle_events.csv"
    view.to_csv(target, index=False)
    user_days = int(
        view.assign(d=view["timestamp"].dt.strftime("%Y-%m-%d")).groupby(["user_id", "d"]).ngroups
    )
    _record(
        manifest,
        "zen_moodle_events",
        {"moodle_events.csv": (target, len(view))},
        dropped=[],
        pseudonymised=["userid"],
        salt_label=SALT,
        sampling={
            "activities": int(view["activity"].nunique()),
            "method": "complete Moodle LMS anonymised clickstream log with English activity labels",
            "user_days": user_days,
            "users": int(view["user_id"].nunique()),
        },
        source_snapshot=f"zen_moodle_events/{WAVE24_SNAPSHOT}",
    )


NORP_FLUX_COLS: tuple[tuple[str, str], ...] = (
    ("flux_1g", "F1G"),
    ("flux_2g", "F2G"),
    ("flux_3_75g", "F3.75G"),
    ("flux_9_4g", "F9.4G"),
    ("flux_17g", "F17G"),
    ("flux_35g", "F35G"),
)


def norp_solar_bursts_view(raw: pd.DataFrame) -> pd.DataFrame:
    """NAOJ Nobeyama Radio Polarimeters solar radio burst events ordered chronologically UTC."""  # noqa: E501
    clean = raw.rename(columns=str.strip).apply(lambda s: s.str.strip())
    start_ts, max_ts, end_ts = (
        pd.to_datetime(
            clean["Date"] + " " + clean[col],
            format="%Y-%m-%d %H:%M:%S",
            utc=True,
            errors="coerce",
        )
        for col in ("Start", "Max", "End")
    )
    max_ts = max_ts.where(max_ts >= start_ts, max_ts + pd.Timedelta(days=1))
    end_ts = end_ts.where(end_ts >= start_ts, end_ts + pd.Timedelta(days=1))
    data: dict[str, Any] = {
        "event_id": clean["EventID"],
        "year_month": clean["Date"].str[:7],
        "start_time": start_ts,
        "max_time": max_ts,
        "end_time": end_ts,
        "duration_s": (end_ts - start_ts).dt.total_seconds(),
        "goes_class": clean["GOES"].replace("", pd.NA),
        "rhessi_id": clean["RHESSI"].replace("", pd.NA),
    }
    for out_c, src_c in NORP_FLUX_COLS:
        data[out_c] = pd.to_numeric(clean[src_c], errors="coerce")
    frame = pd.DataFrame(data)
    return (
        frame[frame["start_time"].notna()]
        .sort_values(["start_time", "event_id"])
        .reset_index(drop=True)
    )


def _build_norp_solar_bursts(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    source = (
        root / "zen_norp_solar_bursts" / WAVE24_SNAPSHOT / "raw" / "myNoRP_Event_List_1988-2025.csv"
    )
    if not source.exists():
        raise ViewError("no NoRP solar burst CSV in the snapshot")
    view = norp_solar_bursts_view(pd.read_csv(source, skiprows=[1], dtype=str))
    folder = out / "zen_norp_solar_bursts"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "solar_bursts.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "zen_norp_solar_bursts",
        {"solar_bursts.csv": (target, len(view))},
        dropped=["units_row"],
        pseudonymised=[],
        sampling={
            "first_start": str(view["start_time"].min()),
            "last_start": str(view["start_time"].max()),
            "method": "complete 1988-2025 NAOJ Nobeyama solar radio burst catalog",
            "year_months": int(view["year_month"].nunique()),
        },
        source_snapshot=f"zen_norp_solar_bursts/{WAVE24_SNAPSHOT}",
    )


BLAZAR_NUM_COLS: tuple[tuple[str, str], ...] = (
    ("redshift", "Redshift"),
    ("flare_order", "Order"),
    ("start_met", "Start"),
    ("stop_met", "Stop"),
    ("duration_s", "Duration"),
    ("waiting_time_s", "WT"),
    ("quality", "Quality"),
    ("fluence", "Fluence"),
    ("fluence_unc", "FluenceUnc"),
    ("asymmetry_p", "AsymmetryP"),
    ("num_sub_flr_7d", "NumSubFlr7dayB"),
    ("num_sub_flr_3d", "NumSubFlr3dayB"),
    ("multi_scale", "MultiScale"),
    ("pe", "PE"),
    ("gpe", "GPE"),
)


def blazar_flares_view(raw: pd.DataFrame) -> pd.DataFrame:
    """Fermi-LAT blazar gamma-ray flare point-process events ordered by source_id and start_met."""  # noqa: E501
    data: dict[str, Any] = {"source_id": raw["Name"], "subclass": raw["Subclass"]}
    for out_c, src_c in BLAZAR_NUM_COLS:
        data[out_c] = pd.to_numeric(raw[src_c], errors="coerce")
    return pd.DataFrame(data).sort_values(["source_id", "start_met"]).reset_index(drop=True)


def _build_blazar_flares(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    source = root / "zen_blazar_flares" / WAVE24_SNAPSHOT / "raw" / "flareCatalog.csv"
    if not source.exists():
        raise ViewError("no blazar flare catalog CSV in the snapshot")
    view = blazar_flares_view(pd.read_csv(source, na_values=["-"], dtype=str))
    folder = out / "zen_blazar_flares"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "blazar_flares.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "zen_blazar_flares",
        {"blazar_flares.csv": (target, len(view))},
        dropped=[
            "HIndex",
            "CapToStemR",
            "CapToStemRUnc",
            "NumberExtremeEvt",
            "ClusterMinSize",
            "ClusterMaxSize",
        ],
        pseudonymised=[],
        sampling={
            "method": "complete Fermi-LAT multi-year blazar gamma-ray flare catalog",
            "sources": int(view["source_id"].nunique()),
        },
        source_snapshot=f"zen_blazar_flares/{WAVE24_SNAPSHOT}",
    )


WIND_FRAGILITY_PREFIX = "Wind_Fragility_Database_v2026.10/data/"
WIND_FRAGILITY_SPEC: dict[str, Any] = {
    "tables": {
        "curves": {
            "keep": [
                "Curve_ID",
                "Source_ID",
                "Asset_Class",
                "Material",
                "Structure_Form",
                "Structure_Function",
                "Circuit_Count",
                "Voltage_kV",
                "Structure_Height_m",
                "Span_Length_m",
                "Hazard_Type",
                "Damage_State",
                "Damage_State_Count",
                "Model_Form",
                "Derivation_Method",
                "Geography_Country",
            ]
        },
        "discretized": {
            "keep": [
                "Curve_ID",
                "Source_ID",
                "Asset_Class",
                "Damage_State",
                "Model_Form",
                "Median_mps",
                "Brackets_P50",
                "IM_Averaging_Time_s",
                "IM_Reference_Height_m",
                "IM_Exposure",
                "Evaluation",
                "V0",
                "V25",
                "V50",
                "V75",
                "V100",
                "V150",
            ]
        },
        "parameters": {
            "keep": [
                "Curve_ID",
                "Param_Name",
                "Param_Value",
                "Param_Unit",
                "Param_Applies_When",
            ]
        },
        "points": {
            "keep": [
                "Curve_ID",
                "IM_Value",
                "Probability",
                "Point_Source",
            ]
        },
        "sources": {
            "keep": [
                "Source_ID",
                "DOI",
                "Year",
                "Venue",
                "Publication_Type",
                "N_Curves",
            ]
        },
    },
    "relations": [
        ["curves", "Source_ID", "sources", "Source_ID"],
        ["discretized", "Curve_ID", "curves", "Curve_ID"],
        ["discretized", "Source_ID", "sources", "Source_ID"],
        ["parameters", "Curve_ID", "curves", "Curve_ID"],
        ["points", "Curve_ID", "curves", "Curve_ID"],
    ],
}


def wind_fragility_view(
    tables: dict[str, pd.DataFrame],
) -> tuple[dict[str, pd.DataFrame], list[dict[str, Any]]]:
    """Five-table power infrastructure wind fragility relational schema without author lists."""
    views, relations = tables_view(tables, WIND_FRAGILITY_SPEC)
    ordered = {
        name: frame.sort_values(list(frame.columns)).reset_index(drop=True)
        for name, frame in views.items()
    }
    return ordered, relations


def _build_wind_fragility(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    import zipfile

    archive = (
        root
        / "zen_wind_fragility"
        / WAVE24_SNAPSHOT
        / "raw"
        / "Wind_Fragility_Database_v2026.10.zip"
    )
    if not archive.exists():
        raise ViewError("no Wind Fragility Database zip archive in the snapshot")
    tables: dict[str, pd.DataFrame] = {}
    with zipfile.ZipFile(archive) as zf:
        for name in WIND_FRAGILITY_SPEC["tables"]:
            with zf.open(f"{WIND_FRAGILITY_PREFIX}{name.upper()}.csv") as handle:
                tables[name] = pd.read_csv(handle, dtype=str)
    views, relations = wind_fragility_view(tables)
    folder = out / "zen_wind_fragility"
    folder.mkdir(parents=True, exist_ok=True)
    files: dict[str, tuple[Path, int]] = {}
    for name, frame in views.items():
        target = folder / f"{name}.csv"
        frame.to_csv(target, index=False)
        files[f"{name}.csv"] = (target, len(frame))
    _record(
        manifest,
        "zen_wind_fragility",
        files,
        dropped=[
            "CURVES.Source_Location",
            "CURVES.Notes",
            "CURVES.Limit_State_Definition",
            "DISCRETIZED.V1..V149_intermediate_grid",
            "SOURCES.Authors",
            "SOURCES.Title",
        ],
        pseudonymised=[],
        relations=relations,
        sampling={
            "method": "complete 5-table Wind Fragility Database v2026.10 relational release (no row sampling)"  # noqa: E501
        },
        source_snapshot=f"zen_wind_fragility/{WAVE24_SNAPSHOT}",
    )


TERRALORE_MEMBERS = {
    "events": "1.0.0/events.csv",
    "sources": "1.0.0/sources.csv",
    "event_sources": "1.0.0/event-sources.csv",
}
TERRALORE_SPEC: dict[str, Any] = {
    "tables": {
        "events": {
            "keep": [
                "claim_id",
                "country_code",
                "country_name",
                "year",
                "year_label",
                "end_year",
                "category",
                "era_id",
                "history_updated",
            ]
        },
        "sources": {
            "keep": [
                "source_key",
                "country_code",
                "source_id",
                "publisher",
                "kind",
                "license",
                "accessed",
            ]
        },
        "event_sources": {
            "keep": [
                "claim_id",
                "source_key",
            ]
        },
    },
    "relations": [
        ["event_sources", "claim_id", "events", "claim_id"],
        ["event_sources", "source_key", "sources", "source_key"],
    ],
}


def terralore_chronicle_view(
    tables: dict[str, pd.DataFrame],
) -> tuple[dict[str, pd.DataFrame], list[dict[str, Any]]]:
    """Three-table TerraLore historical chronicle relational schema preserving ISO-2 'NA'."""
    views, relations = tables_view(tables, TERRALORE_SPEC)
    ordered = {
        name: frame.sort_values(list(frame.columns)).reset_index(drop=True)
        for name, frame in views.items()
    }
    return ordered, relations


def _build_terralore_chronicle(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    import tarfile

    archive = (
        root
        / "zen_terralore_chronicle"
        / WAVE24_SNAPSHOT
        / "raw"
        / "terralore-chronicle-events-1.0.0.tar.gz"
    )
    if not archive.exists():
        raise ViewError("no TerraLore chronicle tar.gz archive in the snapshot")
    tables: dict[str, pd.DataFrame] = {}
    with tarfile.open(archive) as tf:
        for name, member in TERRALORE_MEMBERS.items():
            tables[name] = pd.read_csv(tf.extractfile(member), dtype=str, keep_default_na=False)
    views, relations = terralore_chronicle_view(tables)
    folder = out / "zen_terralore_chronicle"
    folder.mkdir(parents=True, exist_ok=True)
    files: dict[str, tuple[Path, int]] = {}
    for name, frame in views.items():
        target = folder / f"{name}.csv"
        frame.to_csv(target, index=False)
        files[f"{name}.csv"] = (target, len(frame))
    _record(
        manifest,
        "zen_terralore_chronicle",
        files,
        dropped=[
            "events.title",
            "events.summary",
            "events.canonical_url",
            "sources.label",
            "sources.url",
            "events.ndjson",
        ],
        pseudonymised=[],
        relations=relations,
        sampling={
            "method": "complete 3-table TerraLore v1.0.0 historical chronicle relational archive (no row sampling)"  # noqa: E501
        },
        source_snapshot=f"zen_terralore_chronicle/{WAVE24_SNAPSHOT}",
    )


NCEI_STORM_FILES = {
    "details": "StormEvents_details-ftp_v1.0_d2024_c20261119.csv.gz",
    "locations": "StormEvents_locations-ftp_v1.0_d2024_c20261119.csv.gz",
    "fatalities": "StormEvents_fatalities-ftp_v1.0_d2024_c20261119.csv.gz",
}
NCEI_STORM_SPEC: dict[str, Any] = {
    "tables": {
        "details": {
            "keep": [
                "EVENT_ID",
                "EPISODE_ID",
                "BEGIN_YEARMONTH",
                "BEGIN_DAY",
                "BEGIN_TIME",
                "END_YEARMONTH",
                "END_DAY",
                "END_TIME",
                "STATE",
                "STATE_FIPS",
                "YEAR",
                "MONTH_NAME",
                "EVENT_TYPE",
                "CZ_TYPE",
                "CZ_FIPS",
                "CZ_NAME",
                "WFO",
                "CZ_TIMEZONE",
                "INJURIES_DIRECT",
                "INJURIES_INDIRECT",
                "DEATHS_DIRECT",
                "DEATHS_INDIRECT",
                "DAMAGE_PROPERTY",
                "DAMAGE_CROPS",
                "SOURCE",
                "MAGNITUDE",
                "MAGNITUDE_TYPE",
                "FLOOD_CAUSE",
                "TOR_F_SCALE",
                "BEGIN_LAT",
                "BEGIN_LON",
                "END_LAT",
                "END_LON",
            ]
        },
        "locations": {
            "keep": [
                "EVENT_ID",
                "EPISODE_ID",
                "YEARMONTH",
                "LOCATION_INDEX",
                "RANGE",
                "AZIMUTH",
                "LOCATION",
                "LATITUDE",
                "LONGITUDE",
            ]
        },
        "fatalities": {
            "keep": [
                "FATALITY_ID",
                "EVENT_ID",
                "FAT_YEARMONTH",
                "FAT_DAY",
                "FAT_TIME",
                "FATALITY_TYPE",
                "FATALITY_LOCATION",
                "EVENT_YEARMONTH",
            ]
        },
    },
    "relations": [
        ["locations", "EVENT_ID", "details", "EVENT_ID"],
        ["locations", "EPISODE_ID", "details", "EPISODE_ID"],
        ["fatalities", "EVENT_ID", "details", "EVENT_ID"],
    ],
}


def ncei_storm_events_view(
    tables: dict[str, pd.DataFrame],
) -> tuple[dict[str, pd.DataFrame], list[dict[str, Any]]]:
    """Three-table NOAA NCEI 2024 Storm Events relational schema without narratives."""
    views, relations = tables_view(tables, NCEI_STORM_SPEC)
    ordered = {
        name: frame.sort_values(list(frame.columns)).reset_index(drop=True)
        for name, frame in views.items()
    }
    return ordered, relations


def _build_ncei_storm_events(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    raw = root / "ncei_storm_events_2024" / WAVE24_SNAPSHOT / "raw"
    paths = {name: raw / fname for name, fname in NCEI_STORM_FILES.items()}
    if not all(p.exists() for p in paths.values()):
        raise ViewError("missing NOAA NCEI Storm Events CSV archives in the snapshot")
    tables = {name: pd.read_csv(path, dtype=str) for name, path in paths.items()}
    views, relations = ncei_storm_events_view(tables)
    folder = out / "ncei_storm_events_2024"
    folder.mkdir(parents=True, exist_ok=True)
    files: dict[str, tuple[Path, int]] = {}
    for name, frame in views.items():
        target = folder / f"{name}.csv"
        frame.to_csv(target, index=False)
        files[f"{name}.csv"] = (target, len(frame))
    _record(
        manifest,
        "ncei_storm_events_2024",
        files,
        dropped=[
            "details.EPISODE_NARRATIVE",
            "details.EVENT_NARRATIVE",
            "details.DATA_SOURCE",
            "locations.LAT2",
            "locations.LON2",
            "fatalities.FATALITY_AGE",
            "fatalities.FATALITY_SEX",
            "fatalities.FATALITY_DATE",
        ],
        pseudonymised=[],
        relations=relations,
        sampling={
            "method": "complete 2024 annual NOAA NCEI Storm Events 3-table relational release (no row sampling)"  # noqa: E501
        },
        source_snapshot=f"ncei_storm_events_2024/{WAVE24_SNAPSHOT}",
    )


WAVE25_SNAPSHOT = "2026-11-22"

OURAIRPORTS_TABLES = (
    "airports",
    "runways",
    "airport_frequencies",
    "navaids",
    "countries",
    "regions",
)
OURAIRPORTS_SPEC: dict[str, Any] = {
    "tables": {
        "airports": {
            "keep": [
                "id",
                "ident",
                "type",
                "name",
                "latitude_deg",
                "longitude_deg",
                "elevation_ft",
                "continent",
                "iso_country",
                "iso_region",
                "municipality",
                "scheduled_service",
                "icao_code",
                "iata_code",
                "gps_code",
                "local_code",
            ]
        },
        "runways": {
            "keep": [
                "id",
                "airport_ref",
                "airport_ident",
                "length_ft",
                "width_ft",
                "surface",
                "lighted",
                "closed",
                "le_ident",
                "le_heading_degT",
                "he_ident",
                "he_heading_degT",
            ]
        },
        "airport_frequencies": {
            "keep": ["id", "airport_ref", "airport_ident", "type", "description", "frequency_mhz"]
        },
        "navaids": {
            "keep": [
                "id",
                "ident",
                "name",
                "type",
                "frequency_khz",
                "latitude_deg",
                "longitude_deg",
                "elevation_ft",
                "iso_country",
                "dme_frequency_khz",
                "dme_channel",
                "magnetic_variation_deg",
                "usageType",
                "power",
                "associated_airport",
            ]
        },
        "countries": {"keep": ["id", "code", "name", "continent"]},
        "regions": {"keep": ["id", "code", "local_code", "name", "continent", "iso_country"]},
    },
    "relations": [
        ["airports", "iso_country", "countries", "code"],
        ["airports", "iso_region", "regions", "code"],
        ["regions", "iso_country", "countries", "code"],
        ["runways", "airport_ref", "airports", "id"],
        ["runways", "airport_ident", "airports", "ident"],
        ["airport_frequencies", "airport_ref", "airports", "id"],
        ["airport_frequencies", "airport_ident", "airports", "ident"],
        ["navaids", "associated_airport", "airports", "ident"],
        ["navaids", "iso_country", "countries", "code"],
    ],
}
OURAIRPORTS_DROPPED = [
    "airports.home_link",
    "airports.wikipedia_link",
    "airports.keywords",
    "runways.le_latitude_deg",
    "runways.le_longitude_deg",
    "runways.le_elevation_ft",
    "runways.le_displaced_threshold_ft",
    "runways.he_latitude_deg",
    "runways.he_longitude_deg",
    "runways.he_elevation_ft",
    "runways.he_displaced_threshold_ft",
    "navaids.filename",
    "navaids.dme_latitude_deg",
    "navaids.dme_longitude_deg",
    "navaids.dme_elevation_ft",
    "navaids.slaved_variation_deg",
    "countries.wikipedia_link",
    "countries.keywords",
    "regions.wikipedia_link",
    "regions.keywords",
]


def ourairports_view(
    tables: dict[str, pd.DataFrame],
) -> tuple[dict[str, pd.DataFrame], list[dict[str, Any]]]:
    """Six-table OurAirports aviation infrastructure schema without link and keyword text."""
    views, relations = tables_view(tables, OURAIRPORTS_SPEC)
    ordered = {
        name: frame.sort_values(list(frame.columns)).reset_index(drop=True)
        for name, frame in views.items()
    }
    return ordered, relations


def _build_ourairports(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    raw = root / "ourairports_db" / WAVE25_SNAPSHOT / "raw"
    paths = {name: raw / f"{name.replace('_', '-')}.csv" for name in OURAIRPORTS_TABLES}
    if not all(p.exists() for p in paths.values()):
        raise ViewError("missing OurAirports CSV tables in the snapshot")
    # keep_default_na=False: the ISO 3166 country code NA (Namibia) is a value, not a missing cell
    tables = {
        name: pd.read_csv(path, dtype=str, keep_default_na=False) for name, path in paths.items()
    }
    views, relations = ourairports_view(tables)
    folder = out / "ourairports_db"
    folder.mkdir(parents=True, exist_ok=True)
    files: dict[str, tuple[Path, int]] = {}
    for name, frame in views.items():
        target = folder / f"{name}.csv"
        frame.to_csv(target, index=False)
        files[f"{name}.csv"] = (target, len(frame))
    _record(
        manifest,
        "ourairports_db",
        files,
        dropped=OURAIRPORTS_DROPPED,
        pseudonymised=[],
        relations=relations,
        sampling={
            "method": "complete 2026-11-22 daily dump of six OurAirports relational tables (no row sampling)"  # noqa: E501
        },
        source_snapshot=f"ourairports_db/{WAVE25_SNAPSHOT}",
    )


CFTC_TEXT_COLS = (
    "report_date_as_yyyy_mm_dd",
    "market_and_exchange_names",
    "contract_market_name",
    "cftc_contract_market_code",
    "cftc_market_code",
    "commodity_name",
)
CFTC_NUM_COLS = (
    "open_interest_all",
    "prod_merc_positions_long",
    "prod_merc_positions_short",
    "swap_positions_long_all",
    "swap__positions_short_all",
    "swap__positions_spread_all",
    "m_money_positions_long_all",
    "m_money_positions_short_all",
    "m_money_positions_spread",
    "other_rept_positions_long",
    "other_rept_positions_short",
    "other_rept_positions_spread",
    "nonrept_positions_long_all",
    "nonrept_positions_short_all",
)


def cftc_cot_view(records: list[dict[str, Any]]) -> pd.DataFrame:
    """Weekly CFTC disaggregated futures-only trader-class positions, one row per report and contract."""  # noqa: E501
    unique: dict[str, dict[str, Any]] = {}
    for record in records:
        unique.setdefault(record["id"], record)
    rows = [{c: r.get(c) for c in (*CFTC_TEXT_COLS, *CFTC_NUM_COLS)} for r in unique.values()]
    frame = pd.DataFrame(rows, columns=[*CFTC_TEXT_COLS, *CFTC_NUM_COLS])
    frame["report_date_as_yyyy_mm_dd"] = frame["report_date_as_yyyy_mm_dd"].str[:10]
    for col in CFTC_NUM_COLS:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    return frame.sort_values(
        ["report_date_as_yyyy_mm_dd", "cftc_contract_market_code"]
    ).reset_index(drop=True)


def _build_cftc_cot(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    files = sorted(
        (root / "cftc_cot_disaggregated" / WAVE25_SNAPSHOT / "raw").glob(
            "cftc_cot_2024_2025_p*.json"
        )
    )
    if not files:
        raise ViewError("no CFTC Commitments of Traders JSON files in the snapshot")
    records: list[dict[str, Any]] = []
    for path in files:
        records.extend(json.loads(path.read_text()))
    view = cftc_cot_view(records)
    folder = out / "cftc_cot_disaggregated"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "cot_positions.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "cftc_cot_disaggregated",
        {"cot_positions.csv": (target, len(view))},
        dropped=[
            "id",
            "173 of 194 source columns (crop-year splits, changes, percentages, counts)",
        ],
        pseudonymised=[],
        sampling={
            "first_date": str(view["report_date_as_yyyy_mm_dd"].min()),
            "last_date": str(view["report_date_as_yyyy_mm_dd"].max()),
            "method": "complete 2024-01-01 to 2025-12-31 weekly Disaggregated Futures Only release, 21 of 194 columns",  # noqa: E501
            "pages": len(files),
        },
        source_snapshot=f"cftc_cot_disaggregated/{WAVE25_SNAPSHOT}",
    )


NDBC_STATIONS = ("41002", "41004", "42040", "44025", "46013", "46042", "51001")
#: publisher-defined missing-value codes of the NDBC standard meteorological files
NDBC_MISSING = {
    "WDIR": 999.0,
    "WSPD": 99.0,
    "GST": 99.0,
    "WVHT": 99.0,
    "DPD": 99.0,
    "APD": 99.0,
    "MWD": 999.0,
    "PRES": 9999.0,
    "ATMP": 999.0,
    "WTMP": 999.0,
    "DEWP": 999.0,
}
#: columns missing in every row of every selected station, not kept
NDBC_EMPTY = ("VIS", "TIDE")


def ndbc_buoys_view(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Ten-minute UTC buoy observations with the publisher missing codes turned into NaN."""
    parts = []
    for station, raw in sorted(frames.items()):
        stamp = raw["#YY"] + "-" + raw["MM"] + "-" + raw["DD"] + " " + raw["hh"] + ":" + raw["mm"]
        part = pd.DataFrame({"station_id": station, "timestamp": stamp})
        for col, code in NDBC_MISSING.items():
            values = pd.to_numeric(raw[col], errors="coerce")
            part[col] = values.mask(values == code)
        parts.append(part.drop_duplicates(["timestamp"]))
    return pd.concat(parts).sort_values(["station_id", "timestamp"]).reset_index(drop=True)


def _build_ndbc_buoys(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    raw = root / "ndbc_buoys_2023" / WAVE25_SNAPSHOT / "raw"
    paths = {s: raw / f"ndbc_{s}_2023.txt.gz" for s in NDBC_STATIONS}
    if not all(p.exists() for p in paths.values()):
        raise ViewError("missing NDBC standard meteorological files in the snapshot")
    frames = {s: pd.read_csv(p, sep=r"\s+", skiprows=[1], dtype=str) for s, p in paths.items()}
    view = ndbc_buoys_view(frames)
    folder = out / "ndbc_buoys_2023"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "buoy_observations.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "ndbc_buoys_2023",
        {"buoy_observations.csv": (target, len(view))},
        dropped=list(NDBC_EMPTY),
        pseudonymised=[],
        sampling={
            "method": "fixed-station selection: calendar-2023 standard meteorological files of seven NDBC-operated moored buoys",  # noqa: E501
            "stations": len(frames),
        },
        source_snapshot=f"ndbc_buoys_2023/{WAVE25_SNAPSHOT}",
    )


DAYLIGHT_COLS = (
    "event_start_utc",
    "event_end_utc",
    "event_duration_seconds",
    "wear_state",
    "social_context",
    "wear_activity",
    "nonwear_storage",
    "nighttime_position",
    "setting",
    "setting_location",
    "setting_specific",
    "daylight_condition",
    "electric_light_condition",
    "screen_phone",
    "screen_tablet",
    "screen_computer",
    "screen_television",
    "lighting_autonomy",
)


def daylight_events_view(raw: pd.DataFrame) -> pd.DataFrame:
    """Contextual event intervals per participant in start order, participant ids re-pseudonymised."""  # noqa: E501
    frame = raw[["participant_id", *DAYLIGHT_COLS]].copy()
    frame["participant_id"] = frame["participant_id"].map(lambda v: pseudonym(str(v)))
    return frame.sort_values(["participant_id", "event_start_utc", "event_end_utc"]).reset_index(
        drop=True
    )


def _build_daylight_events(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    source = root / "zen_daylight_events" / WAVE25_SNAPSHOT / "raw" / "events.csv"
    if not source.exists():
        raise ViewError("no Day in Daylight events CSV in the snapshot")
    view = daylight_events_view(pd.read_csv(source, dtype=str, keep_default_na=False))
    folder = out / "zen_daylight_events"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "context_events.csv"
    view.to_csv(target, index=False)
    _record(
        manifest,
        "zen_daylight_events",
        {"context_events.csv": (target, len(view))},
        dropped=["event_start_local"],
        pseudonymised=["participant_id"],
        salt_label=SALT,
        sampling={
            "method": "complete events.csv contextual event intervals of the 2025 equinox study",
            "participants": int(view["participant_id"].nunique()),
        },
        source_snapshot=f"zen_daylight_events/{WAVE25_SNAPSHOT}",
    )


CPSC_DROP = frozenset({"ConsumerContact", "Images", "URL"})


def cpsc_recalls_view(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Unique CPSC recall notices by RecallID without contact line, images and page link."""
    unique: dict[int, dict[str, Any]] = {}
    for record in records:
        unique.setdefault(record["RecallID"], record)
    kept = [{k: v for k, v in r.items() if k not in CPSC_DROP} for r in unique.values()]
    return redact_emails(sorted(kept, key=lambda r: r["RecallID"]))


def _build_cpsc_recalls(root: Path, out: Path, manifest: dict[str, Any]) -> None:
    source = root / "cpsc_recalls" / WAVE25_SNAPSHOT / "raw" / "cpsc_recalls_2024_2025.json"
    if not source.exists():
        raise ViewError("no CPSC recall JSON in the snapshot")
    records = json.loads(source.read_text())
    view = cpsc_recalls_view(records)
    target = _write_jsonl(out / "cpsc_recalls", "recalls.jsonl", view)
    _record(
        manifest,
        "cpsc_recalls",
        {"recalls.jsonl": (target, len(view))},
        dropped=sorted(CPSC_DROP),
        pseudonymised=[],
        sampling={
            "method": "complete 2024-01-01 to 2025-12-31 recall-date release from the Recall Retrieval API",  # noqa: E501
            "recalls_in": len(records),
            "unique_recalls": len(view),
        },
        source_snapshot=f"cpsc_recalls/{WAVE25_SNAPSHOT}",
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
    _build_ev_charging,
    _build_azure_packing,
    _build_aoe,
    _build_charity_register,
    _build_japan_buildings,
    _build_coops_tides,
    _build_gml_co2,
    _build_cnc_milling,
    _build_wb_projects,
    _build_queensland_petrol,
    _build_inpi_ratios,
    _build_ror,
    _build_rcsb_pdb,
    _build_nws_alerts,
    _build_port_noumea,
    _build_kanto_landslides,
    _build_nhif_cases,
    _build_ingv_seismic,
    _build_gha_workflows,
    _build_wals_cldf,
    _build_cordis_horizon,
    _build_telecom_kpis,
    _build_dk_heating,
    _build_water_demand,
    _build_dmsp_auroral,
    _build_treasury_dts,
    _build_fdic_financials,
    _build_sncf_tgv,
    _build_dgccrf_fuel,
    _build_federal_register,
    _build_datacite_dois,
    _build_gbif_cc0,
    _build_chembl_molecules,
    _build_florida_bridges,
    _build_wri_power_plants,
    _build_paris_trees,
    _build_moodle_events,
    _build_norp_solar_bursts,
    _build_blazar_flares,
    _build_wind_fragility,
    _build_terralore_chronicle,
    _build_ncei_storm_events,
    _build_ourairports,
    _build_cftc_cot,
    _build_ndbc_buoys,
    _build_daylight_events,
    _build_cpsc_recalls,
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
