"""Provenance audit of the flat tabular (C1) and categorical or mixed (C2a) strata.

The historical counts of these strata are numbers of tables or UCI identifiers. A table is not an
independent source: twins (an ADBench table derived from a UCI table) share a source, and sources
whose listed creators overlap are grouped transitively as one provenance group (conservative: a
shared author can imply a shared generating process or collection protocol). Groups are counted per
stratum but defined over all audited sources. Domains are the repository's subject areas; the
generating-mechanism families come from a fixed mapping of those areas, so the classification is
reproducible. The UCI platform is a curator, not a dependence by itself.
"""

from __future__ import annotations

import json
import re
import time
import urllib.request
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any

TARGETS = {"C1": 36, "C2a": 30}
MECHANISMS = {
    "Physics and Chemistry": "instrument measurement",
    "Engineering": "instrument measurement",
    "Climate and Environment": "instrument measurement",
    "Earth and Environmental Sciences": "instrument measurement",
    "Health and Medicine": "clinical or biological records",
    "Biology": "clinical or biological records",
    "Business": "administrative or survey records",
    "Social Science": "administrative or survey records",
    "Economics": "administrative or survey records",
    "Computer Science": "computational or derived features",
}
API = "https://archive.ics.uci.edu/api/dataset?id={}"


def person_key(name: str) -> str:
    """Comparable form of a person name: "Kohavi, Ronny", "R. Kohavi" and "ronny  kohavi" differ
    only in format; an initial form keeps the surname first so it does not match a full name."""
    text = re.sub(r"\s+", " ", name.strip().lower())
    if "," in text:
        last, _, first = text.partition(",")
        return f"{last.strip()} {first.strip()}".strip()
    parts = text.split(" ")
    if len(parts) > 1 and len(parts[0].rstrip(".")) == 1:
        return f"{parts[-1]} {parts[0].rstrip('.')}"
    return text


def group_sources(metadata: dict[str, dict[str, Any]]) -> dict[str, str]:
    """Provenance group of every source: transitive closure of shared creators, named by its
    smallest member."""
    parent = {s: s for s in metadata}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    owner: dict[str, str] = {}
    for source in sorted(metadata):
        for creator in metadata[source].get("creators") or []:
            key = person_key(creator)
            if not key:
                continue
            if key in owner:
                a, b = find(source), find(owner[key])
                if a != b:
                    parent[max(a, b)] = min(a, b)
            else:
                owner[key] = source
    return {s: find(s) for s in metadata}


def mechanism(area: str | None) -> str:
    return MECHANISMS.get(area or "", "other")


def audit(rows: list[dict[str, Any]], metadata: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Counts per stratum. ``rows`` are catalogue rows (id, source, schema_kind, time_verified)."""
    stratum_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("time_verified") or row.get("stratum"):
            continue
        kind = row.get("schema_kind")
        tagged = set(row.get("tags") or [])
        categorical = kind in ("categorical", "mixed") or tagged & {"categorical_only"}
        stratum_rows["C2a" if categorical else "C1"].append(row)
    audited = {r["source"] for rs in stratum_rows.values() for r in rs}
    groups = group_sources({s: metadata.get(s, {}) for s in audited})
    out: dict[str, Any] = {}
    for name in ("C1", "C2a"):
        rs = stratum_rows.get(name, [])
        if not rs:
            continue
        sources = {r["source"] for r in rs}
        made = {groups[s] for s in sources}
        areas = sorted({metadata.get(s, {}).get("area") or "unknown" for s in sources})
        mechs = sorted({mechanism(metadata.get(s, {}).get("area")) for s in sources})
        sizes = [sum(1 for s in sources if groups[s] == g) for g in made]
        out[name] = {
            "tables": len(rs),
            "sources": len(sources),
            "groups": len(made),
            "domains": len(areas),
            "mechanisms": len(mechs),
            "domain_list": areas,
            "mechanism_list": mechs,
            "largest_group_share": round(max(sizes) / len(sources), 4),
            "target": TARGETS[name],
        }
    every = {r["source"] for rs in stratum_rows.values() for r in rs}
    out["ALL"] = {
        "sources": len(every),
        "groups": len({groups[s] for s in every}),
        "tables": sum(len(rs) for rs in stratum_rows.values()),
    }
    return out


def guardrails(entry: dict[str, Any], domains: int = 5, mechanisms: int = 3) -> dict[str, Any]:
    """Exploratory (3 domains, 2 mechanisms) and generalisation (given minima, target groups)."""
    missing = []
    if entry["groups"] < entry["target"]:
        missing.append(f"groups: {entry['groups']} of {entry['target']}")
    if entry["domains"] < domains:
        missing.append(f"domains: {entry['domains']} of {domains}")
    if entry["mechanisms"] < mechanisms:
        missing.append(f"mechanisms: {entry['mechanisms']} of {mechanisms}")
    return {
        "exploratory": entry["domains"] >= 3 and entry["mechanisms"] >= 2,
        "generalisation": not missing,
        "missing": missing,
    }


def _open(url: str) -> bytes:
    request = urllib.request.Request(
        url, headers={"User-Agent": "etl-benchmark-acquisition (academic research)"}
    )
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 - https, listed host
        return response.read(2_000_000)


def fetch_metadata(
    ids: list[int],
    cache: Path,
    opener: Callable[[str], bytes] = _open,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, dict[str, Any]]:
    """Creators and subject area of UCI tables, from the cache or the repository's API."""
    have: dict[str, dict[str, Any]] = json.loads(cache.read_text()) if cache.exists() else {}
    for number in ids:
        if str(number) in have:
            continue
        sleep(0.5)
        data = json.loads(opener(API.format(number)))["data"]
        have[str(number)] = {"creators": data.get("creators") or [], "area": data.get("area")}
    cache.write_text(json.dumps(have, indent=1, sort_keys=True) + "\n")
    return have


def run(
    rows: list[dict[str, Any]],
    cache: Path,
    opener: Callable[[str], bytes] = _open,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Fetch the missing metadata of the audited UCI sources, audit, and add guardrail status."""
    ids = sorted(
        {
            int(r["source"].split(":", 1)[1])
            for r in rows
            if str(r.get("source", "")).startswith("uci:") and not r.get("time_verified")
        }
    )
    metadata = fetch_metadata(ids, cache, opener=opener, sleep=sleep)
    keyed = {f"uci:{k}": v for k, v in metadata.items()}
    result = audit(rows, keyed)
    for name in ("C1", "C2a"):
        if name in result:
            result[name]["guardrails"] = guardrails(
                result[name],
                domains=5,
                mechanisms=3 if name == "C1" else 3,
            )
    return result


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    here = Path(__file__).resolve().parent
    sys.path[:0] = [str(here), str(here.parent / "src")]
    import dataset_catalog as dc

    base = here.parent / "verification/evidence/dataset_registry_v2"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, default=base)
    args = parser.parse_args(argv)
    result = run(dc.stratum_rows(), args.dir / "uci_metadata_cache.json")
    (args.dir / "provenance_audit_c1_c2a.json").write_text(
        json.dumps(result, indent=1, sort_keys=True) + "\n"
    )
    print({k: {kk: v[kk] for kk in ("tables", "sources", "groups")} for k, v in result.items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
