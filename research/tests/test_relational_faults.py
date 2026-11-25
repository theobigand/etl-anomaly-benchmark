"""Referential-integrity operator on small synthetic relational fixtures."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import relational_faults as rf  # noqa: E402


def _tables():
    customers = pd.DataFrame({"cid": range(1, 11), "name": list("abcdefghij")})
    orders = pd.DataFrame(
        {
            "oid": range(100, 120),
            "cid": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] * 2,
            "note": ["x"] * 20,
        }
    )
    return {"customers": customers, "orders": orders}


FK = rf.ForeignKey("orders", ("cid",), "customers", ("cid",))


def test_a_clean_table_has_no_orphan_and_counts_the_asserted_references():
    assert rf.natural_orphans(FK, _tables()) == {"rows": 20, "asserted": 20, "orphans": 0}


def test_natural_orphans_are_counted_and_null_references_assert_nothing():
    tables = _tables()
    tables["orders"].loc[0, "cid"] = 999  # natural orphan
    tables["orders"]["cid"] = tables["orders"]["cid"].astype("float")
    tables["orders"].loc[1, "cid"] = np.nan  # no reference
    assert rf.natural_orphans(FK, tables) == {"rows": 20, "asserted": 19, "orphans": 1}


def test_orphan_share_is_over_asserted_references_and_zero_without_any():
    tables = _tables()
    rows = tables["orders"].copy()
    rows.loc[:3, "cid"] = 500
    assert rf.orphan_share(FK, tables, rows) == pytest.approx(4 / 20)
    rows["cid"] = np.nan
    assert rf.orphan_share(FK, tables, rows) == 0.0


def test_injection_breaks_the_requested_share_and_labels_exactly_those_rows():
    tables = _tables()
    rows = tables["orders"]
    out, mask = rf.inject_orphans(FK, tables, rows, 2, np.random.default_rng(0))
    assert mask.sum() == 10  # 0.5 of 20 rows
    assert (~rf.reference_state(FK, tables, out)["resolved"].to_numpy() == mask).all()
    assert out.loc[~mask].equals(rows.loc[~mask])  # untouched rows are identical
    assert (out.loc[mask, "cid"] > 10).all()  # absent from the parent
    assert out.loc[mask, "cid"].is_unique  # distinct, as tuples would need to be
    assert list(out.columns) == list(rows.columns)


def test_the_severity_grid_and_the_minimum_of_one_row():
    assert rf.SEVERITY == (0.05, 0.2, 0.5)
    tables = _tables()
    rows = tables["orders"].iloc[:4]
    for level, expected in ((0, 1), (1, 1), (2, 2)):
        _, mask = rf.inject_orphans(FK, tables, rows, level, np.random.default_rng(0))
        assert mask.sum() == expected


def test_the_source_is_not_modified_and_the_draw_is_deterministic():
    tables = _tables()
    before = tables["orders"].copy()
    a = rf.inject_orphans(FK, tables, tables["orders"], 1, np.random.default_rng(7))
    b = rf.inject_orphans(FK, tables, tables["orders"], 1, np.random.default_rng(7))
    assert tables["orders"].equals(before)
    assert a[0].equals(b[0]) and (a[1] == b[1]).all()
    c = rf.inject_orphans(FK, tables, tables["orders"], 1, np.random.default_rng(8))
    assert not (a[1] == c[1]).all()


def test_natural_orphans_stay_unlabelled_and_are_never_the_injected_rows():
    tables = _tables()
    tables["orders"].loc[:2, "cid"] = 999
    out, mask = rf.inject_orphans(FK, tables, tables["orders"], 2, np.random.default_rng(3))
    assert not mask[:3].any()  # already broken: not a candidate
    assert (out.loc[:2, "cid"] == 999).all()
    assert rf.orphan_share(FK, tables, out) == pytest.approx((3 + mask.sum()) / 20)


def test_without_a_resolvable_reference_there_is_nothing_to_break():
    tables = _tables()
    rows = tables["orders"].assign(cid=999)
    with pytest.raises(ValueError, match="^no row has a resolvable reference to break$"):
        rf.inject_orphans(FK, tables, rows, 0, np.random.default_rng(0))


def test_a_composite_key_resolves_as_a_tuple():
    parent = pd.DataFrame({"a": [1, 1, 2], "b": [1, 2, 1]})
    child = pd.DataFrame({"a": [1, 1, 2, 2], "b": [1, 2, 1, 2]})  # (2, 2) does not exist
    fk = rf.ForeignKey("c", ("a", "b"), "p", ("a", "b"))
    tables = {"p": parent, "c": child}
    assert rf.natural_orphans(fk, tables)["orphans"] == 1
    out, mask = rf.inject_orphans(fk, tables, child, 2, np.random.default_rng(0))
    assert mask.sum() == 2 and not mask[3]
    assert rf.natural_orphans(fk, {"p": parent, "c": out})["orphans"] == 3
    assert (out.loc[mask, "a"] == child.loc[mask, "a"]).all()  # only the last column changes


def test_a_partly_null_composite_reference_asserts_nothing():
    parent = pd.DataFrame({"a": [1], "b": [1]})
    child = pd.DataFrame({"a": [1.0, 7.0], "b": [np.nan, 1.0]})
    fk = rf.ForeignKey("c", ("a", "b"), "p", ("a", "b"))
    state = rf.reference_state(fk, {"p": parent, "c": child})
    assert state["asserted"].tolist() == [False, True]
    assert state["resolved"].tolist() == [False, False]


def test_text_keys_get_text_orphans_and_a_junction_table_has_two_independent_keys():
    tags = pd.DataFrame({"tid": ["t1", "t2", "t3"]})
    items = pd.DataFrame({"iid": [1, 2, 3]})
    junction = pd.DataFrame({"iid": [1, 2, 3, 1], "tid": ["t1", "t2", "t3", "t2"]})
    tables = {"tags": tags, "items": items, "j": junction}
    fk_tag = rf.ForeignKey("j", ("tid",), "tags", ("tid",))
    fk_item = rf.ForeignKey("j", ("iid",), "items", ("iid",))
    out, mask = rf.inject_orphans(fk_tag, tables, junction, 2, np.random.default_rng(0))
    assert out.loc[mask, "tid"].str.startswith("orphan-").all()
    assert rf.natural_orphans(fk_item, {**tables, "j": out})["orphans"] == 0  # other key intact
    assert rf.natural_orphans(fk_tag, {**tables, "j": out})["orphans"] == mask.sum()


def _polymorphic():
    people = pd.DataFrame({"id": [1, 2, 3]})
    groups = pd.DataFrame({"id": [10, 20]})
    rows = pd.DataFrame(
        {
            "kind": ["person", "group", "person", "other", "group", "person"],
            "ref": [1, 10, 2, 5, 99, 3],
        }
    )
    fk = rf.ForeignKey(
        "rows", ("ref",), type_column="kind",
        targets={"person": ("people", ("id",)), "group": ("groups", ("id",))},
    )  # fmt: skip
    return fk, {"people": people, "groups": groups, "rows": rows}


def test_a_polymorphic_reference_resolves_against_the_parent_its_type_names():
    fk, tables = _polymorphic()
    state = rf.reference_state(fk, tables)
    assert state["asserted"].tolist() == [True, True, True, False, True, True]  # 'other': no parent
    assert state["resolved"].tolist() == [True, True, True, False, False, True]
    assert rf.natural_orphans(fk, tables) == {"rows": 6, "asserted": 5, "orphans": 1}


def test_a_polymorphic_injection_breaks_only_resolved_rows_with_a_value_in_no_parent():
    fk, tables = _polymorphic()
    out, mask = rf.inject_orphans(fk, tables, tables["rows"], 2, np.random.default_rng(0))
    assert not mask[3] and not mask[4]  # unmapped type and natural orphan are not candidates
    assert (out.loc[mask, "ref"] > 20).all()  # above every parent id, whichever table
    assert rf.natural_orphans(fk, {**tables, "rows": out})["orphans"] == 1 + mask.sum()


def test_a_foreign_key_must_be_well_formed():
    with pytest.raises(
        ValueError, match="^a foreign key needs a parent with as many columns as the child$"
    ):
        rf.ForeignKey("c", ("a", "b"), "p", ("a",))
    with pytest.raises(
        ValueError, match="^a foreign key needs a parent with as many columns as the child$"
    ):
        rf.ForeignKey("c", ("a",))
    with pytest.raises(ValueError, match="^a polymorphic reference needs at least one target$"):
        rf.ForeignKey("c", ("a",), type_column="k")


def test_the_state_keeps_the_index_of_the_delivered_rows():
    tables = _tables()
    rows = tables["orders"].iloc[5:9]
    assert list(rf.reference_state(FK, tables, rows).index) == [5, 6, 7, 8]


def test_a_polymorphic_row_with_a_null_reference_asserts_nothing_even_for_a_known_type():
    fk, tables = _polymorphic()
    rows = tables["rows"].astype({"ref": "float"})
    rows.loc[0, "ref"] = np.nan  # type 'person', no reference
    state = rf.reference_state(fk, tables, rows)
    assert not state.loc[0, "asserted"] and not state.loc[0, "resolved"]
    assert state.loc[2, "asserted"]


def test_the_orphan_value_is_the_next_one_above_the_parent_and_text_rows_are_otherwise_kept():
    tables = _tables()
    out, mask = rf.inject_orphans(
        FK, tables, tables["orders"].iloc[:1], 2, np.random.default_rng(0)
    )
    assert out["cid"].tolist() == [11] and mask.tolist() == [True]
    tags = {
        "tags": pd.DataFrame({"tid": ["t1", "t2"]}),
        "j": pd.DataFrame({"tid": ["t1", "t2", "t1", "t2"]}),
    }
    fk = rf.ForeignKey("j", ("tid",), "tags", ("tid",))
    out, mask = rf.inject_orphans(fk, tags, tags["j"], 1, np.random.default_rng(0))
    assert out.loc[~mask, "tid"].tolist() == tags["j"].loc[~mask, "tid"].tolist()
    assert mask.sum() == 1 and out.loc[mask, "tid"].tolist() == ["orphan-0"]
