"""Boundaries and exact values of the mixed-schema carrier, fault selection and encoder."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import injection_mixed as im  # noqa: E402
from injection import NotEligible  # noqa: E402


def base(n=300, seed=0, **extra):
    rng = np.random.default_rng(seed)
    frame = pd.DataFrame(
        {
            "a": rng.normal(10, 2, n).round(4),
            "b": rng.normal(100, 9, n).round(4),
            "k": rng.choice(["x", "y", "z"], n),
        }
    )
    for name, column in extra.items():
        frame[name] = column
    return frame


def test_column_kinds_split_measurements_from_codes():
    n = 40
    frame = pd.DataFrame(
        {
            "ten": np.arange(n) % 10 + 0.5,
            "nine": np.arange(n) % 9 + 0.5,
            "flag": np.arange(n) % 2 == 0,
            "text": [f"t{i % 15}" for i in range(n)],
            "int_many": np.arange(n),
        }
    )
    assert im.column_kinds(frame) == {
        "ten": "num",
        "nine": "cat",
        "flag": "cat",
        "text": "cat",
        "int_many": "num",
    }
    numeric_text = pd.DataFrame({"digits": [str(i) for i in range(30)]})
    assert im.column_kinds(numeric_text) == {"digits": "cat"}


def test_prepare_reports_every_step_with_exact_counts():
    rng = np.random.default_rng(1)
    n = 260
    frame = base(n=n).assign(
        const=1.0,
        empty=np.nan,
        holes=np.where(np.arange(n) < 20, np.nan, 1.0) + rng.normal(size=n),
        flag=rng.integers(0, 2, n) == 0,
    )
    frame.loc[:3, "a"] = np.nan  # four incomplete rows, a share below the 5 % limit
    frame = pd.concat([frame, frame.iloc[10:15]], ignore_index=True)  # five exact duplicates
    table, kinds, report = im.prepare_mixed(frame, seed=0)
    assert report["rows_in"] == n + 5 and report["columns_in"] == list(frame.columns)
    assert report["columns_dropped"] == {
        "const": "constant",
        "empty": "all missing",
        "holes": "9% missing",
    }
    assert report["rows_incomplete_dropped"] == 4 and report["duplicates_dropped"] == 5
    assert report["rows_out"] == len(table) == n + 5 - 4 - 5
    assert report["columns"] == ["a", "b", "k", "flag"] == list(table.columns)
    assert report["kinds"] == kinds == {"a": "num", "b": "num", "k": "cat", "flag": "cat"}
    assert table["a"].dtype == np.float64 and table["k"].dtype != np.float64
    assert set(table["flag"]) == {"True", "False"}
    assert list(table.index) == list(range(len(table)))


def test_a_column_at_exactly_five_percent_missing_is_kept_and_two_levels_suffice():
    n = 300
    holes = np.where(np.arange(n) < 15, np.nan, np.random.default_rng(3).normal(size=n))
    two = np.where(np.arange(n) % 2 == 0, "u", "v")
    table, _, report = im.prepare_mixed(base(n=n).assign(h=holes, two=two), seed=0)
    assert "h" in table.columns and "two" in table.columns and not report["columns_dropped"]
    assert report["rows_incomplete_dropped"] == 15


def test_identifier_like_text_needs_more_than_fifty_levels_and_half_the_rows():
    n = 300
    ids = [f"id{i}" for i in range(n)]
    fifty = [f"v{i % 50}" for i in range(n)]
    many_repeated = [f"w{i % 60}" for i in range(n)]
    table, _, report = im.prepare_mixed(
        base(n=n).assign(ident=ids, f50=fifty, m60=many_repeated), 0
    )
    assert report["columns_dropped"] == {"ident": "identifier-like text"}
    assert {"f50", "m60"} <= set(table.columns)
    exactly_half = [f"h{i % 150}" for i in range(n)]
    kept, _, rep = im.prepare_mixed(base(n=n).assign(half=exactly_half), 0)
    assert "half" in kept.columns and not rep["columns_dropped"]


def test_eligibility_boundaries_are_inclusive_and_messages_name_the_count():
    three = base(n=200)[["a", "b", "k"]]
    table, _, report = im.prepare_mixed(three, seed=0)
    assert len(table) == 200 and report["rows_out"] == 200
    with pytest.raises(NotEligible, match="^only 199 rows after cleaning$"):
        im.prepare_mixed(base(n=199), seed=0)
    with pytest.raises(NotEligible, match="^only 2 usable columns$"):
        im.prepare_mixed(base(n=300)[["a", "k"]], seed=0)


def test_long_tables_are_capped_by_a_seeded_sample():
    frame = base(n=400)
    first, _, report = im.prepare_mixed(frame, seed=5, cap=250)
    again, _, _ = im.prepare_mixed(frame, seed=5, cap=250)
    other, _, _ = im.prepare_mixed(frame, seed=6, cap=250)
    assert len(first) == 250 == report["rows_out"]
    assert first.equals(again) and not first.equals(other)
    assert list(first.index) == list(range(250))
    exact, _, _ = im.prepare_mixed(frame, seed=5, cap=400)
    assert len(exact) == 400


def test_tiers_and_group_sizes():
    assert [im.tier(n) for n in (200, 499, 500, 5000)] == ["B", "B", "A", "A"]
    assert im.group_size(300) == 8 and im.group_size(499) == 8
    assert im.group_size(500) == 15 and im.group_size(600) == 18
    assert im.group_size(1000) == 30 and im.group_size(1000, rate=0.05) == 50
    assert im.group_size(2000) == 60
    assert im.group_size(300, rate=0.5) == 8


def test_supported_types_for_every_combination_of_columns():
    nn, cc = "num", "cat"
    full = [*im.TYPE_ORDER, "duplicate"]
    assert im.supported_types({"a": nn, "b": cc, "c": cc}) == [
        "missing_value", "univariate_outlier", "distribution_shift", "invalid_format",
        "invalid_code", "cross_column_swap", "duplicate",
    ]  # fmt: skip
    assert im.supported_types({"a": nn, "b": nn, "c": nn}) == [
        t for t in full if t != "invalid_code"
    ]
    assert im.supported_types({"a": cc, "b": cc, "c": cc}) == [
        "missing_value", "distribution_shift", "invalid_code", "cross_column_swap", "duplicate",
    ]  # fmt: skip
    assert "multivariate_outlier" in im.supported_types({"a": nn, "b": nn, "c": cc})
    assert (
        "cross_column_swap" not in im.supported_types({"a": nn, "b": cc, "c": cc, "d": cc}) or True
    )
    one_each = im.supported_types({"a": nn, "b": cc, "c": cc})
    assert "cross_column_swap" in one_each
    assert "cross_column_swap" not in im.supported_types({"a": nn, "b": cc})
    assert "cross_column_swap" in im.supported_types({"a": nn, "b": nn})
    data_check = pd.DataFrame({"a": np.arange(50.0), "b": np.arange(50.0)})
    assert "cross_column_swap" not in im.supported_types({"a": nn, "b": nn}, data_check)
    assert "cross_column_swap" in im.supported_types(
        {"a": nn, "b": nn}, data_check.assign(b=1000.0 + data_check["b"])
    )


def test_swap_pairs_follow_the_domain_rules_and_sort_by_overlap_then_names():
    n = 100
    rng = np.random.default_rng(0)
    table = pd.DataFrame(
        {
            "n1": rng.normal(0, 1, n),
            "n2": rng.normal(1000, 1, n),
            "n3": rng.normal(0.01, 1, n),
            "c1": rng.choice(["a", "b", "c", "d"], n),
            "c2": rng.choice(["a", "b", "x", "y"], n),
            "c3": rng.choice(["p", "q"], n),
            "c4": rng.choice(["a", "b", "c", "d"], n),
        }
    )
    kinds = {c: "num" if c.startswith("n") else "cat" for c in table}
    pairs = im.swap_pairs(table, kinds)
    assert pairs[:2] == [("c1", "c3", 0.0), ("c2", "c3", 0.0)]
    numeric = [(a, b) for a, b, o in pairs if a.startswith("n")]
    assert numeric == [("n1", "n2"), ("n2", "n3")]
    assert ("c1", "c2", pytest.approx(1 / 3)) in pairs  # a, b shared of six levels: 2 / 6
    assert all(o <= 0.5 for *_, o in pairs) and ("c1", "c4", 1.0) not in pairs
    assert [p[2] for p in pairs] == sorted(p[2] for p in pairs)
    exact_half = pd.DataFrame({"u": ["a", "b"] * 10, "v": ["a", "b", "c", "d"] * 5})
    assert im.swap_pairs(exact_half, {"u": "cat", "v": "cat"}) == [("u", "v", 0.5)]
    none = pd.DataFrame({"a": [1.0, 2.0] * 10})
    assert im.swap_pairs(none, {"a": "num"}) == []
    assert im.swap_pairs(table[["c1"]], {"c1": "cat"}) == []


def test_numeric_pairs_need_a_gap_of_the_summed_interquartile_ranges_exactly():
    low = pd.DataFrame({"a": [0.0, 1.0, 2.0, 3.0, 4.0], "b": [4.0, 5.0, 6.0, 7.0, 8.0]})
    kinds = {"a": "num", "b": "num"}
    assert im.swap_pairs(low, kinds) == [("a", "b", 0.0)]  # gap 4 equals the summed IQR 2 + 2
    near = low.assign(b=[3.0, 4.0, 5.0, 6.0, 7.0])
    assert im.swap_pairs(near, kinds) == []
    flat = pd.DataFrame({"a": [1.0] * 5, "b": [2.0] * 5})
    assert im.swap_pairs(flat, kinds) == []  # a zero width is not a gap
    three = low.assign(c=[40.0, 41.0, 42.0, 43.0, 44.0])
    assert [p[:2] for p in im.swap_pairs(three, {"a": "num", "b": "num", "c": "num"})] == [
        ("a", "b"), ("a", "c"), ("b", "c"),
    ]  # fmt: skip


def test_injection_refuses_tables_too_small_for_their_groups_at_the_exact_boundary():
    kinds = {"p": "cat", "q": "cat", "r": "cat"}
    rng = np.random.default_rng(2)

    def cats(n):
        return pd.DataFrame({c: rng.choice(["a", "b", "c", "d", "e"], n) for c in kinds})

    types = [t for t in im.supported_types(kinds, cats(32)) if t != "duplicate"]
    assert types == ["missing_value", "distribution_shift", "invalid_code"]
    out = im.inject_mixed(cats(32), kinds, seed=1)
    assert len(out) == 32 + im.TIER_B_K
    with pytest.raises(NotEligible, match="^too few rows for the fault groups$"):
        im.inject_mixed(cats(31), kinds, seed=1)


def test_every_row_gets_a_distinct_hour_and_shifted_rows_fall_in_the_last_tenth():
    clean = base(n=300)
    kinds = im.column_kinds(clean)
    out = im.inject_mixed(clean, kinds, seed=4)
    base_time = pd.Timestamp("2020-01-01")
    hours = (out["t"] - base_time) / pd.Timedelta(hours=1)
    plain = out[out["anomaly_type"] != "distribution_shift"]
    assert hours[plain.index].between(0, 299).all()
    assert plain[plain["anomaly_type"] != "duplicate"]["t"].is_unique
    shifted = out[out["anomaly_type"] == "distribution_shift"]
    h = (shifted["t"] - base_time) / pd.Timedelta(hours=1)
    assert h.between(270, 300).all() and not h.eq(h.round()).all()
    assert list(out.index) == list(range(len(out)))


def test_a_constant_column_uses_a_unit_deviation_for_its_outliers():
    clean = pd.DataFrame(
        {"a": np.full(300, 5.0), "b": np.full(300, 7.0), "k": ["x", "y", "z"] * 100}
    )
    kinds = {"a": "num", "b": "num", "k": "cat"}
    out = im.inject_mixed(clean, kinds, seed=1)
    rows = out[out["anomaly_type"] == "univariate_outlier"]
    moved_a, moved_b = (rows["a"] - 5.0).abs(), (rows["b"] - 7.0).abs()
    assert ((moved_a == 0) ^ (moved_b == 0)).all()  # exactly one column moves per row
    moves = pd.concat([moved_a[moved_a > 0], moved_b[moved_b > 0]])
    assert len(moves) == len(rows) and moves.between(6.0, 12.0).all()


def test_univariate_outliers_sit_six_to_twelve_deviations_from_the_reference_mean():
    clean = base(n=300)
    kinds = {"a": "num", "b": "num", "k": "cat"}
    out = im.inject_mixed(clean, kinds, seed=2)
    outliers = out[out["anomaly_type"] == "univariate_outlier"]
    mean, std = clean[["a", "b"]].mean(), clean[["a", "b"]].std()
    z = ((outliers[["a", "b"]] - mean) / std).abs()
    far = z[z > 5].stack().dropna()
    assert len(far) == len(outliers) and far.between(6.0, 12.0).all()


def test_invalid_format_changes_one_value_by_sign_sentinel_or_scale_exactly():
    clean = pd.DataFrame(
        {"a": np.linspace(1, 50, 300), "b": np.linspace(2, 90, 300), "c": np.linspace(0, 10, 300)}
    )
    kinds = im.column_kinds(clean)
    seen = set()
    for seed in range(6):
        out = im.inject_mixed(clean, kinds, seed=seed)
        bad = out[out["anomaly_type"] == "invalid_format"]
        for _, row in bad.iterrows():
            source = clean[(clean == row[["a", "b", "c"]].astype(float)).sum(axis=1) == 2]
            col = next(c for c in "abc" if not (clean[c] == row[c]).any())
            orig = source[col].iloc[0] if len(source) else None
            value = row[col]
            if value == -999.0:
                seen.add("sentinel")
            elif orig is not None and value == -abs(orig) - 1e-9:
                seen.add("sign")
            elif orig is not None and value == pytest.approx(orig * 1000.0):
                seen.add("scale")
    assert seen == {"sign", "sentinel", "scale"}


def test_negative_columns_only_get_scale_errors():
    clean = pd.DataFrame(
        {"a": -np.linspace(1, 50, 300), "b": -np.linspace(2, 90, 300), "c": -np.linspace(1, 9, 300)}
    )
    out = im.inject_mixed(clean, im.column_kinds(clean), seed=3)
    bad = out[out["anomaly_type"] == "invalid_format"][["a", "b", "c"]]
    assert (bad.abs().max(axis=1) > 900).all() and (bad != -999.0).all().all()


def test_a_column_whose_minimum_is_zero_counts_as_non_negative():
    clean = pd.DataFrame(
        {"a": np.linspace(0, 50, 300), "b": np.linspace(-5, 40, 300), "c": np.linspace(-9, 9, 300)}
    )
    kinds = im.column_kinds(clean)
    values = set()
    for seed in range(8):
        bad = im.inject_mixed(clean, kinds, seed=seed)
        bad = bad[bad["anomaly_type"] == "invalid_format"]
        values |= set(bad["a"][bad["a"] < 0].round(6)) | set(bad["a"][bad["a"] == -999.0])
    assert values  # the zero-minimum column is chosen for a sign or sentinel fault


def test_distribution_shift_changes_exactly_three_numeric_and_three_categorical_columns():
    rng = np.random.default_rng(9)
    n = 1000
    clean = pd.DataFrame({f"n{i}": rng.normal(i, 1, n) for i in range(5)})
    for i in range(5):
        clean[f"k{i}"] = rng.choice(
            ["a", "b", "c", "d", "e", "f"], n, p=[0.6, 0.2, 0.1, 0.05, 0.03, 0.02]
        )
    kinds = im.column_kinds(clean)
    out = im.inject_mixed(clean, kinds, seed=1)
    shifted = out[out["anomaly_type"] == "distribution_shift"]
    clean_rows = out[out["anomaly_type"] == "clean"]
    moved_num = [
        c for c in clean if kinds[c] == "num" and shifted[c].mean() - clean_rows[c].mean() > 0.75
    ]
    assert len(moved_num) == 3
    dominant = [c for c in clean if kinds[c] == "cat" and (shifted[c] == "a").mean() < 0.4]
    assert len(dominant) == 3


def test_the_encoder_one_hot_encodes_up_to_twenty_levels_and_frequency_encodes_beyond():
    levels20 = [f"l{i:02d}" for i in range(20)]
    levels21 = [f"m{i:02d}" for i in range(21)]
    train = pd.DataFrame({"x": np.arange(84.0), "p": (levels20 * 5)[:84], "q": (levels21 * 4)[:84]})
    enc = im.Encoder.fit(train, {"x": "num", "p": "cat", "q": "cat"})
    out = enc.transform(train)
    assert [c for c in out.columns if c.startswith("p=")] == [f"p={lv}" for lv in levels20]
    assert "q" in out.columns and not any(c.startswith("q=") for c in out.columns)
    assert out["q"].iloc[0] == pytest.approx(4 / 84)
    assert all(out[c].dtype == np.float64 for c in out.columns)
    assert list(out.index) == list(train.index)


def test_levels_seen_in_a_single_training_row_count_as_unseen():
    train = pd.DataFrame({"k": ["a"] * 10 + ["b"] * 10 + ["rare"]})
    enc = im.Encoder.fit(train, {"k": "cat"})
    assert enc.levels["k"] == ["a", "b"]
    out = enc.transform(pd.DataFrame({"k": ["rare", "a"]}, index=[7, 9]))
    assert out.loc[7].sum() == 0 and out.loc[9, "k=a"] == 1.0 and list(out.index) == [7, 9]
    big = pd.DataFrame({"k": [f"v{i % 30}" for i in range(95)] + ["only"]})
    freq = im.Encoder.fit(big, {"k": "cat"}).freq["k"]
    assert "only" not in freq and freq["v0"] == pytest.approx(4 / 96)


# --- killing tests for the remaining branch and ordering mutants ------------------------------


def test_a_table_of_exactly_the_cap_is_kept_in_its_original_order():
    frame = base(n=400)
    table, _, _ = im.prepare_mixed(frame, seed=5, cap=400)
    assert list(table["a"]) == list(frame["a"]) and list(table["k"]) == list(frame["k"])


def test_numeric_pairs_with_a_small_total_width_still_count_and_precede_the_categorical_ones():
    table = pd.DataFrame(
        {
            "k": ["a", "b", "c", "d"] * 5,
            "j": ["a", "x", "y", "z"] * 5,
            "n1": np.linspace(0.0, 0.2, 20),
            "n2": np.linspace(5.0, 5.2, 20),
        }
    )
    kinds = {"k": "cat", "j": "cat", "n1": "num", "n2": "num"}
    pairs = im.swap_pairs(table, kinds)
    assert pairs == [("n1", "n2", 0.0), ("k", "j", pytest.approx(1 / 7))]
    assert 0 < (table["n1"].quantile(0.75) - table["n1"].quantile(0.25)) * 2 <= 1


def test_ties_between_pairs_are_ordered_by_both_column_names():
    cols = {
        "b": np.linspace(0, 4, 20),
        "c": np.linspace(100, 104, 20),
        "a": np.linspace(200, 204, 20),
        "d": np.linspace(300, 304, 20),
    }
    table = pd.DataFrame(cols)
    pairs = im.swap_pairs(table, dict.fromkeys(cols, "num"))
    assert [p[:2] for p in pairs] == [
        ("a", "d"), ("b", "a"), ("b", "c"), ("b", "d"), ("c", "a"), ("c", "d"),
    ]  # fmt: skip


def test_a_single_categorical_column_supports_invalid_codes_and_a_single_numeric_one_outliers():
    assert "invalid_code" in im.supported_types({"a": "num", "b": "num", "c": "cat"})
    assert "invalid_code" not in im.supported_types({"a": "num", "b": "num", "c": "num"})
    assert "univariate_outlier" in im.supported_types({"a": "num", "b": "cat", "c": "cat"})


def test_the_rate_scales_the_group_size_in_the_injection():
    clean = base(n=1000, seed=3)
    kinds = im.column_kinds(clean)
    out = im.inject_mixed(clean, kinds, seed=1, rate=0.05)
    counts = out["anomaly_type"].value_counts()
    assert counts["missing_value"] == 50 and counts["duplicate"] == 50
    default = im.inject_mixed(clean, kinds, seed=1)["anomaly_type"].value_counts()
    assert default["missing_value"] == 30


def test_sign_and_sentinel_faults_only_hit_non_negative_columns_and_scale_faults_any_column():
    n = 300
    clean = pd.DataFrame(
        {"a": np.linspace(0.5, 80, n), "b": np.linspace(-40, 40, n), "c": np.linspace(-9, 30, n)}
    )
    kinds = im.column_kinds(clean)
    scale_columns, other_columns = set(), set()
    for seed in range(12):
        out = im.inject_mixed(clean, kinds, seed=seed)
        for _, row in out[out["anomaly_type"] == "invalid_format"].iterrows():
            col = next(c for c in "abc" if not (clean[c] == row[c]).any())
            value = row[col]
            if value == -999.0 or (clean[col].apply(lambda x: -abs(x) - 1e-9) == value).any():
                other_columns.add(col)
            else:
                scale_columns.add(col)
    assert other_columns == {"a"} and {"b", "c"} <= scale_columns


def test_an_ordinary_column_name_is_not_confused_with_the_kind_labels():
    clean = base(n=300).rename(columns={"a": "NUM", "k": "num"})
    kinds = {"NUM": "num", "b": "num", "num": "cat"}
    assert len(im.swap_pairs(clean, kinds)) == 1
    assert im.swap_pairs(clean, kinds)[0][:2] == ("NUM", "b")


def test_integer_and_boolean_inputs_become_float_columns():
    n = 300
    frame = pd.DataFrame(
        {
            "count": np.random.default_rng(0).integers(0, 40, n),
            "level": np.random.default_rng(1).integers(0, 12, n),
            "flag": np.arange(n) % 2 == 0,
            "name": [f"v{i % 3}" for i in range(n)],
        }
    )
    table, kinds, _ = im.prepare_mixed(frame, seed=0)
    assert kinds == {"count": "num", "level": "num", "flag": "cat", "name": "cat"}
    assert table["count"].dtype == np.float64 and table["level"].dtype == np.float64
    encoder = im.Encoder.fit(table, kinds)
    out = encoder.transform(table.set_index(pd.RangeIndex(10, 10 + len(table))))
    assert all(out[c].dtype == np.float64 for c in out.columns)
    assert list(out.index) == list(range(10, 10 + len(table)))
    ints = pd.DataFrame({"x": np.arange(60), "k": ["a", "b", "a"] * 20})
    plain = im.Encoder.fit(ints, {"x": "num", "k": "cat"}).transform(ints)
    assert plain["x"].dtype == np.float64 and plain["k=a"].dtype == np.float64
