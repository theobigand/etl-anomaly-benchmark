"""Exact tests of the readiness assessment of flat tabular (C1) and categorical (C2a) tables."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import flat_readiness as fr  # noqa: E402


def _frame(rows=600):
    rng = np.random.default_rng(0)
    return pd.DataFrame(
        {
            "a": rng.normal(size=rows),
            "b": rng.normal(size=rows),
            "c": rng.integers(0, 50, size=rows),
            "d": rng.normal(size=rows),
            "k1": rng.choice(["x", "y", "z", "w"], size=rows),
            "k2": rng.choice(["p", "q", "r"], size=rows),
            "const": 1,
        }
    )


def test_the_profile_counts_usable_numeric_and_categorical_columns_and_shares():
    f = _frame()
    f.loc[:59, "a"] = np.nan  # 10 percent of one column missing
    p = fr.profile(f)
    assert p["rows"] == 600 and p["columns"] == 7 and p["constant"] == 1
    assert (
        p["numeric"] == 4 and p["categorical"] == 2 and p["usable"] == 6
    )  # the constant column is not usable
    assert p["max_levels"] == 4 and p["levels_ge3"] == 2
    assert p["missing_share"] == round(60 / (600 * 7), 4)
    assert p["duplicate_share"] == 0.0
    dup = pd.concat([f, f.iloc[:300]], ignore_index=True)
    assert fr.profile(dup)["duplicate_share"] == round(300 / 900, 4)
    assert fr.profile(f.iloc[:0])["rows"] == 0


def test_c1_requires_rows_numeric_variation_low_missingness_and_few_duplicates():
    good = fr.profile(_frame())
    assert fr.reasons(good, "C1") == []
    assert fr.reasons({**good, "rows": 299}, "C1") == ["fewer than 300 rows"]
    assert fr.reasons({**good, "numeric": 2}, "C1") == ["fewer than 3 informative numeric columns"]
    assert fr.reasons({**good, "usable": 3}, "C1") == ["fewer than 4 informative columns"]
    assert fr.reasons({**good, "missing_share": 0.31}, "C1") == [
        "more than 30 percent of values missing"
    ]
    assert fr.reasons({**good, "duplicate_share": 0.51}, "C1") == [
        "more than half of the rows are duplicates"
    ]
    assert (
        fr.reasons(
            {
                **good,
                "rows": 300,
                "numeric": 3,
                "usable": 4,
                "missing_share": 0.30,
                "duplicate_share": 0.5,
            },
            "C1",
        )
        == []
    )  # noqa: E501


def test_c2a_requires_real_categorical_structure_and_more_rows_than_c1():
    good = fr.profile(_frame())
    assert fr.reasons(good, "C2a") == []
    assert fr.reasons({**good, "rows": 499}, "C2a") == ["fewer than 500 rows"]
    assert fr.reasons({**good, "usable": 4}, "C2a") == ["fewer than 5 informative columns"]
    assert fr.reasons({**good, "categorical": 1}, "C2a") == ["fewer than 2 categorical columns"]
    assert fr.reasons({**good, "levels_ge3": 0}, "C2a") == [
        "no categorical column with at least 3 levels"
    ]
    assert (
        fr.reasons({**good, "rows": 500, "usable": 5, "categorical": 2, "levels_ge3": 1}, "C2a")
        == []
    )


def test_reasons_accumulate_and_privacy_review_and_rights_are_reported_first():
    bad = {**fr.profile(_frame()), "rows": 10, "missing_share": 0.9}
    out = fr.reasons(bad, "C1", demographics=["Age"], licence_class="unclear")
    assert out == [
        "licence not open or research_only",
        "personal attributes listed by the publisher (privacy review pending)",
        "fewer than 300 rows",
        "more than 30 percent of values missing",
    ]
    assert (
        fr.reasons(fr.profile(_frame()), "C1", demographics=[], licence_class="research_only") == []
    )


def test_licence_text_maps_to_a_class():
    assert fr.licence_class("CC BY 4.0") == "open" and fr.licence_class("CC0 1.0") == "open"
    assert (
        fr.licence_class("CC BY-NC 4.0") == "research_only"
        and fr.licence_class("CC BY-NC-SA 4.0") == "research_only"
    )
    assert fr.licence_class("Creative Commons Attribution 4.0 International (CC BY 4.0)") == "open"
    assert (
        fr.licence_class("unknown") == "unclear"
        and fr.licence_class(None) == "unclear"
        and fr.licence_class("") == "unclear"
    )


def test_preparation_drops_constant_and_mostly_missing_columns_and_samples_by_stride():
    f = _frame(1000)
    f["gone"] = np.where(np.arange(1000) < 600, np.nan, np.arange(1000.0))  # 60 percent missing
    out, record = fr.prepare(f, max_rows=400)
    assert (
        "const" not in out
        and "gone" not in out
        and list(out.columns) == ["a", "b", "c", "d", "k1", "k2"]
    )
    assert len(out) == 334 and record["rows_in"] == 1000 and record["rows_out"] == 334
    assert record["stride"] == 3 and out.index.tolist()[:3] == [0, 1, 2]
    assert record["dropped_constant"] == ["const"] and record["dropped_missing"] == ["gone"]
    assert out["a"].iloc[1] == f["a"].iloc[3]  # every third row, from the first
    small, rec = fr.prepare(_frame(100), max_rows=400)
    assert len(small) == 100 and rec["stride"] == 1


def test_a_group_is_represented_by_its_largest_eligible_table_per_stratum():
    tables = [
        {"id": "t1", "group": "g1", "stratum": "C1", "rows": 500, "reasons": []},
        {"id": "t2", "group": "g1", "stratum": "C1", "rows": 900, "reasons": []},
        {
            "id": "t3",
            "group": "g1",
            "stratum": "C1",
            "rows": 2000,
            "reasons": ["fewer than 4 informative columns"],
        },
        {"id": "t4", "group": "g1", "stratum": "C2a", "rows": 700, "reasons": []},
        {
            "id": "t5",
            "group": "g2",
            "stratum": "C1",
            "rows": 100,
            "reasons": ["fewer than 300 rows"],
        },
        {"id": "t6", "group": "g3", "stratum": "C1", "rows": 900, "reasons": []},
        {"id": "t7", "group": "g3", "stratum": "C1", "rows": 900, "reasons": []},
    ]
    out = fr.representatives(tables)
    assert out[("g1", "C1")]["id"] == "t2" and out[("g1", "C2a")]["id"] == "t4"
    assert out[("g3", "C1")]["id"] == "t6"  # ties go to the smaller identifier
    assert out[("g2", "C1")] is None  # no eligible table: the group is rejected for this stratum
    assert sorted(out) == [("g1", "C1"), ("g1", "C2a"), ("g2", "C1"), ("g3", "C1")]


# --- assessing every audited table and registering the representatives -----------------------------  # noqa: E501


def _rows():
    return [
        {"id": "uci:1", "source": "uci:1", "schema_kind": "numeric"},
        {
            "id": "adbench:t",
            "source": "uci:1",
            "schema_kind": "numeric",
        },  # twin: same source, one table
        {"id": "uci:2", "source": "uci:2", "schema_kind": "mixed"},
        {"id": "uci:3", "source": "uci:3", "schema_kind": "numeric"},
        {"id": "uci:4", "source": "uci:4", "schema_kind": "numeric"},
        {"id": "uci:9", "source": "uci:9", "time_verified": True},
    ]


META = {
    "uci:1": {"creators": ["Ann Lee"], "area": "Biology", "demographics": []},
    "uci:2": {"creators": ["Ann Lee"], "area": "Business", "demographics": []},
    "uci:3": {"creators": ["Bo"], "area": "Engineering", "demographics": ["Age"]},
    "uci:4": {"creators": ["Cy"], "area": "Engineering", "demographics": []},
}
LICENCES = {"uci:1": "CC BY 4.0", "uci:2": "CC BY 4.0", "uci:3": "CC BY 4.0", "uci:4": "unknown"}


def _loader(source):
    return {"uci:1": _frame(600), "uci:2": _frame(700), "uci:3": _frame(800), "uci:4": _frame(900)}[
        source
    ]


def test_assess_profiles_each_source_once_and_names_the_group_stratum_and_reasons():
    tables = fr.assess(_rows(), META, LICENCES, _loader)
    assert [t["id"] for t in tables] == [
        "uci:1",
        "uci:2",
        "uci:3",
        "uci:4",
    ]  # the twin is not a second table
    first = tables[0]
    assert (
        first["group"] == "uci:1"
        and first["stratum"] == "C1"
        and first["reasons"] == []
        and first["rows"] == 600
    )
    assert first["twins"] == ["adbench:t"] and first["licence_class"] == "open"
    second = tables[1]
    assert second["group"] == "uci:1" and second["stratum"] == "C2a"  # shares a creator with uci:1
    assert tables[2]["reasons"] == [
        "personal attributes listed by the publisher (privacy review pending)"
    ]
    assert (
        tables[3]["reasons"] == ["licence not open or research_only"]
        and tables[3]["licence_class"] == "unclear"
    )
    assert tables[0]["profile"]["rows"] == 600


def test_register_creates_one_entry_and_fact_set_per_group_and_stratum_with_a_view_key():
    tables = fr.assess(_rows(), META, LICENCES, _loader)
    entries, facts, views = fr.register(tables)
    ids = [e["id"] for e in entries]
    assert ids == ["flat:uci:1:C1", "flat:uci:1:C2a", "flat:uci:3:C1", "flat:uci:4:C1"]
    ok = entries[0]
    assert ok["stratum"] == "C1" and ok["eligible"] is True and ok["licence_class"] == "open"
    assert ok["stages"]["data_acquired"] is True and ok["stages"]["structural_validation"] is True
    assert ok["upstream_status"] == "verified" and ok["publisher"] == "uci:1"
    rejected = entries[2]
    assert rejected["eligible"] is False and rejected["stages"]["structural_validation"] is False
    assert "privacy review pending" in rejected["reason"]
    assert sorted(facts) == [
        "flat:uci:1:C1",
        "flat:uci:1:C2a",
    ]  # only represented groups carry facts
    f = facts["flat:uci:1:C1"]
    assert (
        f["independent_group"] == "uci:1"
        and f["protocol_id"] == "P-TAB"
        and f["privacy"] == "handled"
    )
    assert (
        f["view"] == "flat_uci_1_C1"
        and f["units"] == 600
        and f["min_units"] == 300
        and f["first_party"] is False
    )
    assert (
        f["anomaly_origin"] == "controlled_injection"
        and f["partitions"] == "hash of the row index 70/15/15"
    )
    assert views == [
        {"key": "flat_uci_1_C1", "source": "uci:1", "table": "uci:1", "stratum": "C1"},
        {"key": "flat_uci_1_C2a", "source": "uci:2", "table": "uci:2", "stratum": "C2a"},
    ]
