"""Exact tests of the readiness assessment of flat tabular (C1) and categorical (C2a) tables."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

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


# --- the command: reads the catalogue and the pinned tables and rewrites the evidence ---------------  # noqa: E501


def _tree(tmp_path):
    import hashlib
    import json

    root = tmp_path
    (root / "research").mkdir()
    (root / "src").mkdir()
    (root / "data" / "pool").mkdir(parents=True)
    (root / "data" / "uci_wave2").mkdir(parents=True)
    evidence = root / "verification" / "evidence" / "dataset_registry_v2"
    evidence.mkdir(parents=True)
    (root / "verification" / "evidence" / "dataset_registry").mkdir(parents=True)
    frames = {1: _frame(600), 2: _frame(700), 3: _frame(650)}
    shas = {}
    for n, f in frames.items():
        folder = "pool" if n < 3 else "uci_wave2"
        path = root / "data" / folder / f"{n}.csv"
        f.to_csv(path, index=False)
        shas[n] = hashlib.sha256(path.read_bytes()).hexdigest()
    (root / "data" / "pool" / "4.csv").write_text(
        "a,b\n1,2\n"
    )  # a table whose checksum does not match
    pool = {"rows": [
        {"uci_id": 1, "licence": "CC BY 4.0", "sha256": shas[1]},
        {"uci_id": 2, "licence": "CC BY 4.0", "sha256": shas[2]},
        {"uci_id": 4, "licence": "CC BY 4.0", "sha256": "0" * 64}]}  # fmt: skip
    (root / "verification/evidence/dataset_registry/uci_pool.json").write_text(json.dumps(pool))
    (evidence / "uci_wave2_selection.json").write_text(
        json.dumps({"chosen": [{"uci_id": 3, "licence": "CC BY-NC 4.0"}]})
    )
    (evidence / "uci_wave2_manifest.json").write_text(
        json.dumps({"tables": [{"uci_id": 3, "sha256": shas[3]}]})
    )
    meta = {
        str(i): {"creators": [f"P{i}"], "area": "Biology", "name": f"T{i}", "demographics": []}
        for i in (1, 2, 3, 4)
    }
    meta["2"]["creators"] = ["P1"]  # tables 1 and 2 share a creator
    (evidence / "uci_metadata_cache.json").write_text(json.dumps(meta))
    (evidence / "acquired_sources.json").write_text(
        json.dumps({"entries": [{"id": "other", "stratum": "C3"}, {"id": "flat:old:C1"}]})
    )
    (evidence / "readiness_facts.json").write_text(
        json.dumps({"facts": {"other": {"x": 1}, "flat:old:C1": {"y": 2}}})
    )
    rows = [
        {"id": "uci:1", "source": "uci:1", "schema_kind": "numeric"},
        {"id": "uci:2", "source": "uci:2", "schema_kind": "mixed"},
        {"id": "uci:3", "source": "uci:3", "schema_kind": "numeric"},
        {"id": "uci:4", "source": "uci:4", "schema_kind": "numeric"},
        {"id": "uci:5", "source": "uci:5", "schema_kind": "numeric"},  # no file on disk
        {"id": "natural:x", "source": "natural:x", "schema_kind": "numeric"},
    ]
    return root, evidence, rows


def test_main_writes_the_selection_replaces_only_flat_entries_and_reports_missing_and_changed_files(
    tmp_path, monkeypatch, capsys
):
    import json

    import dataset_catalog as dc

    root, evidence, rows = _tree(tmp_path)
    monkeypatch.setattr(dc, "stratum_rows", lambda: rows)
    monkeypatch.setattr(fr, "__file__", str(root / "research" / "flat_readiness.py"))
    assert fr.main(["--dir", str(evidence)]) == 0
    selection = json.loads((evidence / "flat_selection.json").read_text())
    assert [t["id"] for t in selection["tables"]] == ["uci:1", "uci:2", "uci:3"]
    assert selection["without_file"] == ["uci:5"] and selection["checksum_mismatch"] == ["uci:4"]
    assert [v["key"] for v in selection["views"]] == [
        "flat_uci_1_C1",
        "flat_uci_1_C2a",
        "flat_uci_3_C1",
    ]
    third = selection["tables"][2]
    assert third["licence_class"] == "research_only" and third["reasons"] == []
    acquired = json.loads((evidence / "acquired_sources.json").read_text())
    assert [e["id"] for e in acquired["entries"]] == [
        "other",
        "flat:uci:1:C1",
        "flat:uci:1:C2a",
        "flat:uci:3:C1",
    ]
    facts = json.loads((evidence / "readiness_facts.json").read_text())["facts"]
    assert sorted(facts) == ["flat:uci:1:C1", "flat:uci:1:C2a", "flat:uci:3:C1", "other"]
    assert facts["other"] == {"x": 1}
    assert capsys.readouterr().out == "3 tables, 3 group entries, 3 represented, 3 views\n"
    text = (evidence / "flat_selection.json").read_text()
    assert text == json.dumps(selection, indent=1, sort_keys=True) + "\n"
    with pytest.raises(SystemExit):
        fr.main(["--help"])


def test_assess_and_register_produce_exactly_the_documented_records():
    meta = {**META, "uci:1": {**META["uci:1"], "name": "Alpha"}}
    tables = fr.assess(_rows(), meta, LICENCES, _loader)
    assert tables[0] == {
        "id": "uci:1", "source": "uci:1", "group": "uci:1", "stratum": "C1", "twins": ["adbench:t"], "rows": 600,  # noqa: E501
        "profile": {"categorical": 2, "columns": 7, "constant": 1, "duplicate_share": 0.0, "levels_ge3": 2,  # noqa: E501
                    "max_levels": 4, "missing_share": 0.0, "numeric": 4, "rows": 600, "usable": 6},
        "licence": "CC BY 4.0", "licence_class": "open", "area": "Biology", "name": "Alpha", "reasons": [],  # noqa: E501
    }  # fmt: skip
    entries, facts, views = fr.register(fr.assess(_rows(), meta, LICENCES, _loader))
    assert entries[0] == {
        "id": "flat:uci:1:C1", "family": "uci:1", "publisher": "uci:1", "stratum": "C1", "licence_class": "open",  # noqa: E501
        "eligible": True, "system": "uci:1", "upstream_status": "verified", "protocols": "P-TAB",
        "reason": "representative table uci:1 (Alpha): 600 rows, 6 informative columns, licence CC BY 4.0",  # noqa: E501
        "stages": {"collection_implemented": True, "data_acquired": True, "discovered": True,
                   "licence_verified": "licence stated on the repository page of the table",
                   "ready_for_experiments": False, "structural_validation": True},
    }  # fmt: skip
    assert (
        entries[2]["reason"]
        == "no eligible table: uci:3: personal attributes listed by the publisher (privacy review pending)"  # noqa: E501
    )
    assert (
        entries[2]["stages"]["structural_validation"] is False and entries[2]["eligible"] is False
    )
    assert facts["flat:uci:1:C1"] == {
        "anomaly_origin": "controlled_injection",
        "baseline_properties": ["600 rows and 6 informative columns in the representative table",
                                "0.0 share of missing values", "1 audited table(s) in this group and stratum"],  # noqa: E501
        "first_party": False, "independent_group": "uci:1", "min_units": 300,
        "partitions": "hash of the row index 70/15/15", "privacy": "handled", "protocol_id": "P-TAB",  # noqa: E501
        "units": 600, "view": "flat_uci_1_C1",
    }  # fmt: skip
    assert facts["flat:uci:1:C2a"]["min_units"] == 500 and facts["flat:uci:1:C2a"]["units"] == 700
    assert len(views) == 2


def test_licence_text_edge_cases_and_the_profile_of_missing_and_empty_columns():
    assert (
        fr.licence_class("creative commons attribution 4.0") == "open"
        and fr.licence_class("cc by 4.0") == "open"
    )
    assert fr.licence_class(None) == "unclear" and fr.licence_class("CC BY-NC") == "research_only"
    f = pd.DataFrame(
        {
            "a": [1.0, np.nan, 3.0, 4.0],
            "b": [np.nan, np.nan, np.nan, np.nan],
            "c": ["x", "y", None, "x"],
        }
    )
    p = fr.profile(f)
    assert p["constant"] == 1 and p["usable"] == 2 and p["numeric"] == 1 and p["categorical"] == 1
    assert p["max_levels"] == 2 and p["levels_ge3"] == 0  # a missing value is not a level
    assert p["missing_share"] == round(6 / 12, 4)
    empty = fr.profile(pd.DataFrame({"a": []}))
    assert empty["rows"] == 0 and empty["missing_share"] == 0.0 and empty["duplicate_share"] == 0.0
    assert empty["max_levels"] == 0
    two = pd.DataFrame({"a": [1, 2, 3], "b": [1, 1, 1]})
    assert (
        fr.profile(two)["constant"] == 1
    )  # a column with one value is constant, with two it is not
    assert fr.profile(pd.DataFrame({"a": [1, 2]}))["constant"] == 0


def test_preparation_keeps_missing_values_in_kept_columns_and_the_exact_dropped_lists():
    f = pd.DataFrame(
        {
            "a": [1.0, 2.0, np.nan, 4.0],
            "b": [np.nan, np.nan, np.nan, 1.0],
            "c": [5] * 4,
            "d": [1, 2, 3, 4],
        }
    )
    out, record = fr.prepare(f)
    assert (
        list(out.columns) == ["a", "d"] and out["a"].isna().sum() == 1
    )  # a is 25 percent missing: kept
    assert record == {
        "rows_in": 4,
        "rows_out": 4,
        "stride": 1,
        "dropped_constant": ["b", "c"],
        "dropped_missing": [],
    }
    half = pd.DataFrame(
        {"a": [1.0, np.nan, np.nan, 4.0, 5.0], "b": [1.0, 2.0, np.nan, np.nan, np.nan]}
    )
    kept, rec = fr.prepare(half)
    assert list(kept.columns) == ["a"] and rec["dropped_missing"] == [
        "b"
    ]  # b is 60 percent missing
    exactly = pd.DataFrame({"a": [1.0, 2.0, 3.0, 4.0], "b": [1.0, 2.0, np.nan, np.nan]})
    assert list(fr.prepare(exactly)[0].columns) == ["a", "b"]  # exactly 50 percent missing is kept
    assert (
        fr.prepare(_frame(10), max_rows=10)[1]["stride"] == 1
        and fr.prepare(_frame(11), max_rows=10)[1]["stride"] == 2
    )


def test_the_representative_choice_is_none_for_a_group_whose_only_tables_are_ineligible():
    tables = [{"id": "x", "group": "g", "stratum": "C1", "rows": 5, "reasons": ["r"]}]
    assert fr.representatives(tables) == {("g", "C1"): None}
    mixed = [{"id": "a", "group": "g", "stratum": "C1", "rows": 5, "reasons": ["r"]},
             {"id": "b", "group": "g", "stratum": "C1", "rows": 3, "reasons": []}]  # fmt: skip
    assert fr.representatives(mixed)[("g", "C1")]["id"] == "b"


def test_main_uses_the_default_evidence_folder_and_writes_canonical_json(tmp_path, monkeypatch):
    import json

    import dataset_catalog as dc

    root, evidence, rows = _tree(tmp_path)
    monkeypatch.setattr(dc, "stratum_rows", lambda: rows)
    monkeypatch.setattr(fr, "__file__", str(root / "research" / "flat_readiness.py"))
    assert fr.main([]) == 0  # no --dir: the evidence folder next to the package
    for name in ("acquired_sources.json", "readiness_facts.json", "flat_selection.json"):
        text = (evidence / name).read_text()
        assert text == json.dumps(json.loads(text), indent=1, sort_keys=True) + "\n"
    assert json.loads((evidence / "flat_selection.json").read_text())["checksum_mismatch"] == [
        "uci:4"
    ]


def test_a_table_is_found_in_the_pool_folder_before_the_wave_two_folder_and_the_stratum_order_is_stable():  # noqa: E501
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        (root / "data" / "pool").mkdir(parents=True)
        (root / "data" / "uci_wave2").mkdir(parents=True)
        assert fr._has_file(lambda s: (_ for _ in ()).throw(FileNotFoundError(s)), "uci:1") is False
        assert fr._has_file(lambda s: root, "uci:1") is True


def test_reasons_of_several_tables_are_joined_with_semicolons_and_commas_in_the_rejection_text():
    tables = [
        {"id": "a", "source": "a", "group": "g", "stratum": "C1", "rows": 10, "licence": "x", "licence_class": "open",  # noqa: E501
         "name": "A", "profile": {"usable": 1, "missing_share": 0.0}, "reasons": ["r1", "r2"]},
        {"id": "b", "source": "b", "group": "g", "stratum": "C1", "rows": 20, "licence": "x", "licence_class": "open",  # noqa: E501
         "name": "B", "profile": {"usable": 1, "missing_share": 0.0}, "reasons": ["r3"]},
    ]  # fmt: skip
    entries, facts, views = fr.register(tables)
    assert entries[0]["reason"] == "no eligible table: a: r1, r2; b: r3"
    assert facts == {} and views == []


def test_a_source_missing_from_the_metadata_has_no_area_name_or_demographics():
    tables = fr.assess(_rows()[:1], {}, {"uci:1": "CC BY 4.0"}, _loader)
    assert tables[0]["area"] is None and tables[0]["name"] is None and tables[0]["reasons"] == []
    assert tables[0]["group"] == "uci:1"


def test_a_column_with_one_value_and_missing_values_is_constant_and_prepare_subsamples_at_stride_two():  # noqa: E501
    f = pd.DataFrame({"a": [1.0, np.nan, 1.0, np.nan], "b": [1, 2, 3, 4]})
    assert fr.profile(f)["constant"] == 1 and fr.prepare(f)[1]["dropped_constant"] == ["a"]
    out, record = fr.prepare(_frame(11), max_rows=10)
    assert record["stride"] == 2 and len(out) == 6 and record["rows_out"] == 6
    assert out["a"].iloc[1] == _frame(11)["a"].iloc[2]
    three, rec3 = fr.prepare(_frame(25), max_rows=10)
    assert rec3["stride"] == 3 and len(three) == 9
