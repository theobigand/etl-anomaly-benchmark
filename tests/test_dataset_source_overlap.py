"""Population counts and source overlap are recomputed from archived artifacts."""

import json
from pathlib import Path

from research.dataset_registry import UCI_SOURCES

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "verification/evidence"
RUNS = EVIDENCE / "labelled_pool/runs"


def _labelled():
    keys = sorted(path.stem for path in RUNS.glob("*.json"))
    adbench = [key.removeprefix("adbench_") for key in keys if key.startswith("adbench_")]
    uci = [int(key.removeprefix("uci_")) for key in keys if key.startswith("uci_")]
    return keys, adbench, uci


def test_manifest_and_problem_populations_match_the_audit():
    manifest = json.loads((EVIDENCE / "dataset_registry/pool_manifest.json").read_text())
    keys, adbench, uci = _labelled()
    assert len(manifest) == 152 and len({row["id"] for row in manifest}) == 152
    assert (len(keys), len(adbench), len(uci)) == (100, 36, 64)
    eligibility = json.loads((EVIDENCE / "pool_extension/typed/eligibility.json").read_text())
    eligible = [row for row in eligibility if row["eligible"]]
    assert len(eligible) == 58
    assert sorted((s, sum(r["source"] == s for r in eligible)) for s in ("adbench", "uci")) == [
        ("adbench", 16),
        ("uci", 42),
    ]


def test_source_overlap_separates_occurrences_from_unique_sources():
    _, adbench, labelled_uci = _labelled()
    pool = {
        row["uci_id"]
        for row in json.loads((EVIDENCE / "dataset_registry/uci_pool.json").read_text())["rows"]
    }
    origin = {name: UCI_SOURCES[name][0] for name in adbench if name in UCI_SOURCES}
    assert [name for name in adbench if name not in origin] == ["fraud"]
    assert (len(origin), len(set(origin.values()))) == (35, 30)

    in_pool = [name for name, source in origin.items() if source in pool]
    assert (len(in_pool), len({origin[name] for name in in_pool})) == (22, 19)

    labelled = set(labelled_uci)
    shared = {source for source in origin.values() if source in labelled}
    adbench_side = [name for name, source in origin.items() if source in labelled]
    assert (len(adbench_side), len(shared), len(labelled & shared)) == (17, 15, 15)


def test_eligibility_criteria_hold_for_every_carrier_and_every_exclusion_has_a_reason():
    rows = json.loads((EVIDENCE / "pool_extension/typed/eligibility.json").read_text())
    assert len(rows) == 152
    for row in rows:
        if row["eligible"]:
            assert row["rows"] >= 3_000 and len(row["report"]["columns"]) >= 4
        else:
            assert row["reason"]
