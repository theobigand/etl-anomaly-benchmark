"""Structural validation of acquired data, independent of any detector (tasks T434-T436).

Three checks: the content of a time-series file (``.tsf``), the shape of nested JSON records (depth,
arrays, optional fields, type variation) and the referential integrity of a foreign key.
"""

from __future__ import annotations

from typing import Any


def read_tsf(text: str) -> dict[str, Any]:
    """Header facts and series of a .tsf file; ``?`` marks a missing value."""
    header: dict[str, str] = {}
    series: list[dict[str, Any]] = []
    columns: list[str] = []
    in_data = False
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if in_data:
            fields = line.split(":", len(columns))
            start = fields[columns.index("start_timestamp")] if "start_timestamp" in columns else ""
            series.append(
                {
                    "name": fields[0],
                    "start": start,
                    "values": [None if v == "?" else float(v) for v in fields[-1].split(",")],
                }
            )
        elif line.lower() == "@data":
            in_data = True
        elif line.startswith("@"):
            key, _, value = line[1:].partition(" ")
            if key.lower() == "attribute":
                columns.append(value.split()[0])
            header[key.lower()] = value
    return {
        "frequency": header.get("frequency"),
        "horizon": header.get("horizon"),
        "missing_flag": header.get("missing") == "true",
        "equal_length_flag": header.get("equallength") == "true",
        "series": series,
    }


def tsf_summary(parsed: dict[str, Any]) -> dict[str, Any]:
    lengths = [len(s["values"]) for s in parsed["series"]]
    total = sum(lengths)
    missing = sum(v is None for s in parsed["series"] for v in s["values"])
    return {
        "series": len(lengths),
        "min_length": min(lengths) if lengths else 0,
        "max_length": max(lengths) if lengths else 0,
        "points": total,
        "missing_share": missing / total if total else 0.0,
        "frequency": parsed["frequency"],
        "has_start": bool(parsed["series"])
        and all(s["start"] not in ("", "?") for s in parsed["series"]),
    }


def _walk(value: Any, path: str, out: dict[str, dict[str, Any]], depth: int) -> int:
    """Record the types of every leaf path of one record in ``out``; return the deepest level."""
    deepest = depth
    if isinstance(value, dict):
        for key, child in value.items():
            deepest = max(deepest, _walk(child, f"{path}.{key}" if path else key, out, depth + 1))
    else:
        node = out.setdefault(path, {"types": set(), "array": False})
        node["types"].add(type(value).__name__)
        if isinstance(value, list):
            node["array"] = True
            for item in value:
                if isinstance(item, dict):
                    deepest = max(deepest, _walk(item, path, out, depth + 1))
    return deepest


def json_shape(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Depth, per-path presence, array share and type set of a list of JSON objects.

    Presence and array share are shares of records: a path repeated inside one record (objects in
    an array) still counts once for that record.
    """
    paths: dict[str, dict[str, Any]] = {}
    deepest = 0
    for record in records:
        local: dict[str, dict[str, Any]] = {}
        deepest = max(deepest, _walk(record, "", local, 1))
        for path, node in local.items():
            total = paths.setdefault(path, {"present": 0, "types": set(), "arrays": 0})
            total["present"] += 1
            total["types"] |= node["types"]
            total["arrays"] += int(node["array"])
    n = len(records)
    report = {
        p: {
            "presence": v["present"] / n,
            "array_share": v["arrays"] / v["present"],
            "types": sorted(v["types"]),
        }
        for p, v in sorted(paths.items())
    }
    optional = sum(v["presence"] < 1 for v in report.values())
    return {
        "records": n,
        "max_depth": deepest,
        "paths": report,
        "optional_paths": optional,
        "variable_structure": optional > 0 or any(len(v["types"]) > 1 for v in report.values()),
    }


def orphans(child_keys: list[Any], parent_keys: set[Any]) -> dict[str, Any]:
    """Child key values (missing ones skipped) that name no parent row."""
    checked = [k for k in child_keys if k is not None]
    bad = sum(k not in parent_keys for k in checked)
    return {
        "checked": len(checked),
        "orphans": bad,
        "share": bad / len(checked) if checked else 0.0,
    }


def _tsf_report(root: Any) -> dict[str, Any]:
    import zipfile

    out = {}
    for path in sorted((root / "monash_zenodo" / "2026-11-21" / "raw").glob("*.zip")):
        with zipfile.ZipFile(path) as archive:
            member = next(n for n in archive.namelist() if n.endswith(".tsf"))
            out[path.name] = tsf_summary(read_tsf(archive.read(member).decode("utf-8", "replace")))
    return out


def _json_report(root: Any) -> dict[str, Any]:
    import json

    out = {}
    for source in ("openfda_drug_event", "openfda_drug_label", "openfda_food_enforcement"):
        records: list[dict[str, Any]] = []
        for path in sorted((root / source / "2026-11-21" / "raw").glob("*.json")):
            records += json.loads(path.read_text())["results"]
        shape = json_shape(records)
        out[source] = {k: shape[k] for k in ("records", "max_depth", "optional_paths")} | {
            "variable_structure": shape["variable_structure"],
            "paths": len(shape["paths"]),
            "array_paths": sum(v["array_share"] > 0 for v in shape["paths"].values()),
        }
    return out


#: (child table, child column, parent table, parent column) foreign keys of the Stack Exchange dump
STACK_KEYS = [
    ("Posts", "OwnerUserId", "Users", "Id"),
    ("Posts", "ParentId", "Posts", "Id"),
    ("Posts", "AcceptedAnswerId", "Posts", "Id"),
    ("Comments", "PostId", "Posts", "Id"),
    ("Comments", "UserId", "Users", "Id"),
    ("Votes", "PostId", "Posts", "Id"),
    ("Badges", "UserId", "Users", "Id"),
    ("PostLinks", "PostId", "Posts", "Id"),
    ("PostLinks", "RelatedPostId", "Posts", "Id"),
]


def _stack_report(root: Any) -> dict[str, Any]:
    import subprocess
    import tempfile
    import xml.etree.ElementTree as ET
    from pathlib import Path

    out = {}
    for archive in sorted((root / "stackexchange_dump" / "2026-11-21" / "raw").glob("*.7z")):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["bsdtar", "-xf", str(archive), "-C", tmp], check=True)  # noqa: S603, S607
            tables = {
                p.stem: [dict(e.attrib) for e in ET.parse(p).getroot()]
                for p in Path(tmp).glob("*.xml")
            }
        keys = {}
        for child, column, parent, key in STACK_KEYS:
            values = [r.get(column) for r in tables.get(child, [])]
            known = {r[key] for r in tables.get(parent, [])}
            keys[f"{child}.{column}->{parent}.{key}"] = orphans(values, known)
        out[archive.name] = {"tables": {k: len(v) for k, v in tables.items()}, "foreign_keys": keys}
    return out


def _off_report(root: Any) -> dict[str, Any]:
    import gzip
    import json

    path = next((root / "openfoodfacts_products" / "2026-11-21" / "raw").glob("*.gz"))
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        records = [json.loads(line) for line in handle if line.strip()]
    shape = json_shape(records)
    return {
        k: shape[k] for k in ("records", "max_depth", "optional_paths", "variable_structure")
    } | {
        "paths": len(shape["paths"]),
        "array_paths": sum(v["array_share"] > 0 for v in shape["paths"].values()),
        "multi_type_paths": sum(len(v["types"]) > 1 for v in shape["paths"].values()),
    }


def _openalex_report(root: Any) -> dict[str, Any]:
    import json

    raw = root / "openalex_works" / "2026-11-21" / "raw"

    def load(prefix: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for path in sorted(raw.glob(f"{prefix}_*.json")):
            out += json.loads(path.read_text())["results"]
        return out

    works, authors = load("works"), load("authors")
    institutions, sources = load("institutions"), load("sources")
    author_ids = [a["author"]["id"] for w in works for a in w["authorships"]]
    inst_ids = [i["id"] for w in works for a in w["authorships"] for i in a["institutions"]]
    source_ids = [(w.get("primary_location") or {}).get("source") for w in works]
    source_ids = [s["id"] for s in source_ids if s]
    cited = [r for w in works for r in w["referenced_works"]]
    shape = json_shape(works)
    return {
        "tables": {
            "works": len(works),
            "authors": len(authors),
            "institutions": len(institutions),
            "sources": len(sources),
        },
        "foreign_keys": {
            "authorships.author->authors": orphans(author_ids, {a["id"] for a in authors}),
            "authorships.institution->institutions": orphans(
                inst_ids, {i["id"] for i in institutions}
            ),
            "primary_location.source->sources": orphans(source_ids, {s["id"] for s in sources}),
            "referenced_works->works (sample only, expected incomplete)": orphans(
                cited, {w["id"] for w in works}
            ),
        },
        "works_shape": {k: shape[k] for k in ("records", "max_depth", "optional_paths")}
        | {"paths": len(shape["paths"])},
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json
    from pathlib import Path

    here = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=here / "data" / "acquired")
    parser.add_argument(
        "--out",
        type=Path,
        default=here / "verification/evidence/dataset_registry_v2/acquired_validation.json",
    )
    args = parser.parse_args(argv)
    report = {
        "monash_zenodo": _tsf_report(args.root),
        "openfda": _json_report(args.root),
        "stackexchange": _stack_report(args.root),
        "openalex": _openalex_report(args.root),
        "openfoodfacts": _off_report(args.root),
    }
    args.out.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    print({k: len(v) for k, v in report.items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
