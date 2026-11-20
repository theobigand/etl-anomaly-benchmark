"""Mixed-schema summary on hand-computed runs: loading, medians, M1 to M3, report, command."""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import typed_mixed_summary as tms  # noqa: E402

METHODS = ["knn", "lof", "ocsvm", "isolation_forest", "zscore", "iqr", "great_expectations"]


def run(ident, tier, kinds, recall, counts=10):
    types = sorted({t for by in recall.values() for t in by})
    return {
        "id": ident,
        "tier": tier,
        "carrier": {"kinds": kinds},
        "test_counts": {t: counts for t in types},
        "recall_pooled": recall,
    }


def recalls(base):
    """Recall per method: distance methods get ``base`` on every type, rules a third of it."""
    out = {}
    for m in METHODS:
        value = base if m in ("knn", "lof", "ocsvm", "isolation_forest") else base / 3
        out[m] = {"invalid_code": value, "cross_column_swap": value, "missing_value": None}
    return out


def folder(tmp_path):
    root = tmp_path / "runs"
    root.mkdir(exist_ok=True)
    spec = [
        ("uci:1", "A", {"a": "num", "b": "num"}, 0.9),
        ("uci:2", "A", {"a": "num", "b": "cat"}, 0.6),
        ("adbench:satellite", "B", {"a": "cat", "b": "cat"}, 0.3),
        ("uci:146", "B", {"a": "cat", "b": "cat"}, 0.1),
    ]
    for i, tier, kinds, base in spec:
        (root / f"{i.replace(':', '_')}.json").write_text(
            json.dumps(run(i, tier, kinds, recalls(base)))
        )
    return root


def test_load_gives_one_row_per_present_value_and_marks_numeric_only_tables(tmp_path):
    frame = tms.load(folder(tmp_path))
    assert len(frame) == 4 * len(METHODS) * 2  # the None recall is absent, not zero
    assert set(frame["type"]) == {"invalid_code", "cross_column_swap"}
    only = frame.drop_duplicates("id").set_index("id")
    assert only["numeric_only"].to_dict() == {
        "uci:1": True,
        "uci:2": False,
        "adbench:satellite": False,
        "uci:146": False,
    }
    assert only.loc["adbench:satellite", "source"] == only.loc["uci:146", "source"] == "uci:146"
    assert set(frame["test_n"]) == {10} and set(frame["tier"]) == {"A", "B"}


def test_sources_are_averaged_before_the_median(tmp_path):
    frame = tms.load(folder(tmp_path))
    averaged = tms.by_source(frame)
    sat = averaged[(averaged["source"] == "uci:146") & (averaged["method"] == "knn")]
    assert sorted(sat["recall"].round(6)) == [0.2, 0.2]  # (0.3 + 0.1) / 2 for each type
    rows = {(r["method"], r["type"]): r for r in tms.medians(frame, draws=50)}
    knn = rows[("knn", "invalid_code")]
    assert knn["sources"] == 3 and knn["median"] == pytest.approx(0.6)
    assert knn["ci"][0] <= 0.6 <= knn["ci"][1]
    zs = rows[("zscore", "invalid_code")]
    assert zs["median"] == pytest.approx(0.2)


def test_m1_correlates_detector_medians_with_the_numeric_protocol(tmp_path, monkeypatch):
    frame = tms.load(folder(tmp_path))
    reference = pd.DataFrame(
        {"invalid_code": range(7), "temporal_drift": range(7)},
        index=sorted(METHODS),
    )
    numeric = tmp_path / "numeric.json"
    numeric.write_text(json.dumps({"median": json.loads(reference.to_json(orient="split"))}))
    monkeypatch.setattr(tms, "NUMERIC", numeric)
    out = tms.m1(frame)
    names = sorted(METHODS)
    mine = [0.9 if m in ("knn", "lof", "ocsvm", "isolation_forest") else 0.3 for m in names]
    from scipy.stats import spearmanr

    expected = float(spearmanr(mine, list(range(7))).statistic)
    assert out["sources"] == 1
    assert out["per_type_rank_correlation"] == {"invalid_code": pytest.approx(expected)}
    assert out["mean"] == pytest.approx(expected)
    assert tms.m1(frame[~frame["numeric_only"]]) == {
        "per_type_rank_correlation": {},
        "mean": None,
        "sources": 0,
    }


def test_m2_compares_rules_with_distance_and_density_detectors(tmp_path):
    out = tms.m2(tms.load(folder(tmp_path)))
    code = out["invalid_code"]
    assert code["distance_density"] == pytest.approx(0.6)  # median of 0.9, 0.6, 0.2
    assert code["rules"] == pytest.approx(0.2)  # median of 0.3, 0.2, 0.0667
    assert set(out) == {"invalid_code", "cross_column_swap"}


def test_m3_needs_five_sources_per_tier_and_adjusts_the_p_values(tmp_path):
    assert tms.m3(tms.load(folder(tmp_path))) == {}
    rows = []
    rng = np.random.default_rng(0)
    for n in range(12):
        tier = "A" if n < 6 else "B"
        rows.append(
            {"id": f"u{n}", "source": f"s{n}", "tier": tier, "numeric_only": False,
             "method": "knn", "type": "x", "recall": float(rng.uniform(0.4, 0.6)), "test_n": 5}
        )  # fmt: skip
        rows.append(
            {**rows[-1], "method": "lof", "recall": 0.1 * (n % 3) + (0.5 if n >= 6 else 0.0)}
        )
    out = tms.m3(pd.DataFrame(rows))
    assert set(out) == {"knn", "lof"}
    for entry in out.values():
        assert entry["p_holm"] >= entry["p"] and 0 <= entry["p"] <= 1
    assert out["lof"]["median_B"] > out["lof"]["median_A"]


def test_summary_counts_tables_sources_tiers_and_types(tmp_path, monkeypatch):
    numeric = tmp_path / "n.json"
    ref = pd.DataFrame({"invalid_code": range(7)}, index=sorted(METHODS))
    numeric.write_text(json.dumps({"median": json.loads(ref.to_json(orient="split"))}))
    monkeypatch.setattr(tms, "NUMERIC", numeric)
    s = tms.summarise(folder(tmp_path))
    assert (s["datasets"], s["sources"]) == (4, 3)
    assert s["tiers"] == {"A": 2, "B": 2}
    assert s["types"] == {"invalid_code": 4, "cross_column_swap": 4}
    assert len(s["medians"]) == 2 * len(METHODS)
    assert set(s) == {"datasets", "sources", "tiers", "types", "medians", "M1", "M2", "M3"}


def test_markdown_table_and_report_layout():
    table = pd.DataFrame({"a": [0.5, 0.25]}, index=pd.Index(["knn", "zscore"], name="method"))
    assert tms._md(table) == "| method | a |\n|---|---|\n| knn | 0.5 |\n| zscore | 0.25 |"
    summary = {
        "datasets": 3,
        "sources": 2,
        "tiers": {"A": 2, "B": 1},
        "medians": [{"method": "knn", "type": "x", "median": 0.456}],
        "M1": {"mean": 0.8},
        "M2": {"x": 1},
        "M3": {"knn": {"p": 0.5}},
    }
    text = tms.report(summary)
    assert text.startswith("# Typed injection on mixed-schema and small tables\n\n3 tables from 2 ")
    assert "(tier A 2, tier B 1)." in text and "| knn | 0.46 |" in text
    assert "M1 mean rank correlation with the numeric protocol: 0.8" in text
    assert 'M2: {"x": 1}' in text and "| knn | 0.5 |" in text


def test_main_writes_summary_json_and_markdown(tmp_path, monkeypatch, capsys):
    numeric = tmp_path / "n.json"
    ref = pd.DataFrame({"invalid_code": range(7)}, index=sorted(METHODS))
    numeric.write_text(json.dumps({"median": json.loads(ref.to_json(orient="split"))}))
    monkeypatch.setattr(tms, "NUMERIC", numeric)
    out = tmp_path / "out"
    assert tms.main([str(folder(tmp_path)), "--out", str(out)]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "datasets": 4,
        "sources": 3,
        "tiers": {"A": 2, "B": 2},
    }
    assert json.loads((out / "summary.json").read_text())["datasets"] == 4
    assert (out / "summary.md").read_text().startswith("# Typed injection")


# --- contracts -------------------------------------------------------------------------------


def test_by_source_returns_plain_columns_not_an_index(tmp_path):
    out = tms.by_source(tms.load(folder(tmp_path)))
    assert list(out.columns) == ["source", "method", "type", "recall"]
    assert list(out.index) == list(range(len(out)))


def many_sources(n=30):
    rows = []
    for i in range(n):
        rows.append(
            {"id": f"u{i}", "source": f"s{i}", "tier": "A", "numeric_only": False,
             "method": "knn", "type": "x", "test_n": 5,
             "recall": float(np.random.default_rng(i).uniform())}
        )  # fmt: skip
    return pd.DataFrame(rows)


def test_medians_use_seed_2026_draws_2000_and_the_row_wise_median():
    frame = many_sources()
    values = tms.by_source(frame)["recall"].to_numpy()
    rng = np.random.default_rng(2026)
    boot = np.median(rng.choice(values, (2000, len(values))), axis=1)
    low, high = np.quantile(boot, [0.025, 0.975])
    [row] = tms.medians(frame)
    assert row["ci"] == [float(low), float(high)] and row["sources"] == 30
    assert row["median"] == pytest.approx(float(np.median(values)))
    assert (tms.SEED, tms.DRAWS) == (2026, 2000)
    assert tms.medians(frame, seed=1)[0]["ci"] != row["ci"]


def _numeric_reference(tmp_path, monkeypatch, columns):
    ref = pd.DataFrame(columns, index=sorted(METHODS))
    path = tmp_path / "numeric.json"
    path.write_text(json.dumps({"median": json.loads(ref.to_json(orient="split"))}))
    monkeypatch.setattr(tms, "NUMERIC", path)


def numeric_only_frame(methods, fault="invalid_code", tier="A"):
    rows = []
    for k, m in enumerate(methods):
        rows.append(
            {"id": "u1", "source": "s1", "tier": tier, "numeric_only": True,
             "method": m, "type": fault, "recall": 0.1 * (k + 1), "test_n": 5}
        )  # fmt: skip
    return pd.DataFrame(rows)


def test_m1_needs_at_least_five_detectors_in_common_and_keeps_only_shared_ones(
    tmp_path, monkeypatch
):
    _numeric_reference(tmp_path, monkeypatch, {"invalid_code": range(7)})
    five = numeric_only_frame(sorted(METHODS)[:5])
    assert set(tms.m1(five)["per_type_rank_correlation"]) == {"invalid_code"}
    four = numeric_only_frame(sorted(METHODS)[:4])
    assert tms.m1(four)["per_type_rank_correlation"] == {}
    six = numeric_only_frame(sorted(METHODS)[:5] + ["unknown_detector"])
    assert tms.m1(six)["per_type_rank_correlation"]["invalid_code"] == pytest.approx(1.0)


def test_m1_maps_the_renamed_drift_type_and_ignores_types_the_numeric_protocol_lacks(
    tmp_path, monkeypatch
):
    _numeric_reference(
        tmp_path, monkeypatch, {"temporal_drift": range(7), "invalid_code": range(7)}
    )
    frame = pd.concat(
        [
            numeric_only_frame(sorted(METHODS), "distribution_shift"),
            numeric_only_frame(sorted(METHODS), "cross_column_swap"),
        ]
    )
    out = tms.m1(frame)
    assert set(out["per_type_rank_correlation"]) == {"distribution_shift"}
    assert out["per_type_rank_correlation"]["distribution_shift"] == pytest.approx(1.0)
    assert out["mean"] == pytest.approx(1.0)


def test_m2_covers_both_categorical_fault_types_and_only_those(tmp_path):
    frame = tms.load(folder(tmp_path))
    extra = frame.assign(type="univariate_outlier", recall=0.99)
    out = tms.m2(pd.concat([frame, extra]))
    assert set(out) == {"invalid_code", "cross_column_swap"}
    assert out["cross_column_swap"]["distance_density"] == pytest.approx(0.6)


def tiered(n_a, n_b, recall_a=0.2, recall_b=0.8):
    rows = []
    for i in range(n_a + n_b):
        tier = "A" if i < n_a else "B"
        rows.append(
            {"id": f"u{i}", "source": f"s{i}", "tier": tier, "numeric_only": False,
             "method": "knn", "type": "x", "test_n": 5,
             "recall": (recall_a if tier == "A" else recall_b) + 0.01 * i}
        )  # fmt: skip
    return pd.DataFrame(rows)


def test_m3_needs_five_sources_in_each_tier():
    assert set(tms.m3(tiered(5, 5))) == {"knn"}
    assert tms.m3(tiered(4, 5)) == {} and tms.m3(tiered(5, 4)) == {} and tms.m3(tiered(6, 4)) == {}
    assert tms.m3(tiered(4, 9)) == {}
    out = tms.m3(tiered(6, 6))["knn"]
    assert out["median_A"] == pytest.approx(0.225) and out["median_B"] == pytest.approx(0.885)
    assert out["p_holm"] == pytest.approx(out["p"]) and out["p"] < 0.01


def test_report_text_is_exact():
    summary = {
        "datasets": 3,
        "sources": 2,
        "tiers": {"A": 2},
        "medians": [
            {"method": "knn", "type": "invalid_code", "median": 0.456},
            {"method": "zscore", "type": "invalid_code", "median": 0.1},
        ],
        "M1": {"mean": 0.8},
        "M2": {"x": 1},
        "M3": {"knn": {"p": 0.123456, "p_holm": 0.2}},
    }
    assert tms.report(summary) == (
        "# Typed injection on mixed-schema and small tables\n"
        "\n"
        "3 tables from 2 independent sources (tier A 2, tier B 0).\n"
        "\n"
        "Median recall over sources, by detector and fault type:\n"
        "\n"
        "| method | invalid_code |\n"
        "|---|---|\n"
        "| knn | 0.46 |\n"
        "| zscore | 0.1 |\n"
        "\n"
        "M1 mean rank correlation with the numeric protocol: 0.8\n"
        'M2: {"x": 1}\n'
        "\n"
        "M3 (tier B against tier A), Holm-adjusted:\n"
        "\n"
        "|  | p | p_holm |\n"
        "|---|---|---|\n"
        "| knn | 0.123 | 0.2 |\n"
    )
    assert tms._md(pd.DataFrame({"a": [1]}, index=["r"])) == "|  | a |\n|---|---|\n| r | 1 |"


def test_main_prints_the_counts_and_writes_exact_files(tmp_path, monkeypatch, capsys):
    _numeric_reference(tmp_path, monkeypatch, {"invalid_code": range(7)})
    out = tmp_path / "x" / "out"
    runs = folder(tmp_path)
    assert tms.main([str(runs), "--out", str(out)]) == 0
    printed = capsys.readouterr().out
    assert printed.endswith("\n") and json.loads(printed) == {
        "datasets": 4,
        "sources": 3,
        "tiers": {"A": 2, "B": 2},
    }
    summary = tms.summarise(folder(tmp_path))
    assert (out / "summary.json").read_text() == json.dumps(
        summary, indent=1, sort_keys=True
    ) + "\n"
    assert (out / "summary.md").read_text() == tms.report(summary)
    assert tms.PARSER.parse_args(["f", "--out", "o"]).out == Path("o")
    with pytest.raises(SystemExit):
        tms.PARSER.parse_args(["f"])


def test_the_report_counts_a_missing_tier_as_zero():
    summary = {
        "datasets": 1, "sources": 1, "tiers": {"B": 1}, "medians": [],
        "M1": {"mean": None}, "M2": {}, "M3": {},
    }  # fmt: skip
    summary["medians"] = [{"method": "knn", "type": "x", "median": 0.5}]
    summary["M3"] = {"knn": {"p": 0.5}}
    assert "(tier A 0, tier B 1)." in tms.report(summary)
    only_a = {**summary, "tiers": {"A": 1}}
    assert "(tier A 1, tier B 0)." in tms.report(only_a)


def test_writing_into_an_existing_directory_is_allowed_and_creates_missing_parents(tmp_path):
    summary = {
        "datasets": 1, "sources": 1, "tiers": {"A": 1},
        "medians": [{"method": "knn", "type": "x", "median": 0.5}],
        "M1": {"mean": None}, "M2": {}, "M3": {"knn": {"p": 0.5}},
    }  # fmt: skip
    tms.write_summary(tmp_path, summary)
    tms.write_summary(tmp_path, summary)
    nested = tmp_path / "x" / "y"
    tms.write_summary(nested, summary)
    assert json.loads((nested / "summary.json").read_text())["datasets"] == 1
