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
    import sys
    import zipfile

    sys.path.insert(0, str(Path(__file__).resolve().parent))
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


def series_view(raw: pd.DataFrame, spec: dict[str, Any]) -> pd.DataFrame:
    """A table in time order with a parsed ``timestamp`` and its numeric columns.

    The time columns are joined with a space and parsed with the exact declared format; a row whose
    time cannot be read is dropped and counted (``attrs["rows_dropped"]``), never guessed. Other
    columns are read as numbers (unreadable values become missing); text columns are dropped.
    """
    frame = raw.rename(columns=lambda c: str(c).lstrip("\ufeff"))
    if not all(c in frame.columns for c in spec["time"]):
        raise ViewError(f"time column not found in {list(frame.columns)[:6]}")
    joined = frame[spec["time"]].astype(str).agg(" ".join, axis=1)
    stamps = pd.to_datetime(joined, format=spec["format"], errors="coerce")
    hour = spec.get("hour")
    if hour:
        stamps = stamps + pd.to_timedelta(pd.to_numeric(frame[hour], errors="coerce"), unit="h")
    used = {*spec["time"], *([hour] if hour else [])}
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
