"""Tables, figures and records of the synthetic benchmark and the severity sweep."""

import json
import logging
import re
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
import run_severity  # noqa: E402
import run_synthetic_benchmark as bench  # noqa: E402

from etl_benchmark import config  # noqa: E402
from etl_benchmark.registry import ALL_NAMES  # noqa: E402
from etl_benchmark.synthetic import ANOMALY_TYPES, FEATURE_COLUMNS, make_synthetic  # noqa: E402

STAMP = r"\d{8}_\d{6}"


def _messages(caplog, name):
    return [r.getMessage() for r in caplog.records if r.name.endswith(name)]


def _without_time(markdown):
    return "\n".join(
        line.rsplit("|", 2)[0] if "detect_s" in markdown and line.startswith("|") else line
        for line in markdown.split("\n")
    )


@pytest.fixture
def captured_figures(monkeypatch):
    """Keep every figure that the script closes so its content can be inspected."""
    figures = []
    original = plt.close

    def keep(fig=None):
        figures.append(fig)
        return original(fig)

    monkeypatch.setattr(plt, "close", keep)
    return figures


# --- run_synthetic_benchmark ------------------------------------------------


def test_combined_markdown_table_marks_missing_values_and_single_seed_spread():
    mean = pd.DataFrame({"a": [0.5, np.nan], "b": [1.0, 0.25]}, index=["m1", "m2"])
    std = pd.DataFrame({"a": [0.1234, np.nan], "b": [np.nan, 0.05]}, index=["m1", "m2"])
    assert bench._combined_md(mean, std, ["a", "b"]) == (
        "| method | a | b |\n"
        "| --- | --- | --- |\n"
        "| m1 | 0.500 ± 0.123 | 1.000 ± n/a |\n"
        "| m2 | - | 0.250 ± 0.050 |\n"
    )


def test_duplicate_reference_flags_every_copy_of_a_repeated_row():
    frame = pd.DataFrame({column: [1.0, 1.0, 2.0] for column in FEATURE_COLUMNS})
    frame["customer_id"] = [1, 1, 2]
    frame["anomaly_type"] = ["clean", "duplicate", "clean"]
    assert bench._dedup_flags_for(frame).tolist() == [True, True, False]


def test_one_split_reports_every_method_and_the_reference_rule():
    frame = make_synthetic(n_rows=300, seed=2)
    result = bench.evaluate(frame, 2)
    methods = [*ALL_NAMES, "transform_dedup"]
    assert set(result) == {"metrics", "recall", "precision"}
    for table in result.values():
        assert table.index.tolist() == methods
    assert result["recall"].columns.tolist() == ANOMALY_TYPES
    assert result["precision"].columns.tolist() == ANOMALY_TYPES
    assert pd.isna(result["metrics"].loc["transform_dedup", "detect_s"])
    assert result["metrics"].loc["zscore", "detect_s"] >= 0
    assert result["recall"].loc["transform_dedup", "duplicate"] == 1.0


def test_run_aggregates_each_table_over_seeds():
    result = bench.run([1, 2], rows=300)
    assert set(result) == {
        f"{kind}_{stat}" for kind in ("metrics", "recall", "precision") for stat in ("mean", "std")
    }
    frames = [bench.evaluate(make_synthetic(seed=s, n_rows=300), s) for s in (1, 2)]
    for kind in ("metrics", "recall", "precision"):
        both = np.stack([f[kind].to_numpy(dtype=float) for f in frames])
        expected_mean = np.nanmean(both, axis=0)
        np.testing.assert_allclose(
            result[f"{kind}_mean"].to_numpy(dtype=float)[:, :6], expected_mean[:, :6], atol=1e-12
        )
        assert result[f"{kind}_mean"].index.tolist() == [*ALL_NAMES, "transform_dedup"]


def test_run_uses_the_default_population_when_no_row_count_is_given(monkeypatch):
    seen = []
    real = bench.make_synthetic

    def spy(**kwargs):
        seen.append(kwargs)
        return real(n_rows=300, seed=kwargs["seed"])

    monkeypatch.setattr(bench, "make_synthetic", spy)
    bench.run([4], None)
    bench.run([5], 300)
    assert seen == [{"seed": 4}, {"seed": 5, "n_rows": 300}]


def test_heatmap_shows_every_cell_with_its_value(tmp_path, captured_figures):
    recall = pd.DataFrame(
        np.arange(len(ANOMALY_TYPES) * 2, dtype=float).reshape(2, -1) / 12.0,
        index=["alpha", "beta"],
        columns=ANOMALY_TYPES,
    )
    recall.iloc[1, 2] = np.nan
    path = bench.render_heatmap(recall, tmp_path / "deep" / "er" / "heat.png")
    assert path == tmp_path / "deep" / "er" / "heat.png" and path.stat().st_size > 0
    fig = captured_figures[-1]
    ax, colorbar = fig.axes[0], fig.axes[1]
    assert ax.get_title() == "Mean detection rate by anomaly type (synthetic, 5 seeds)"
    assert [t.get_text() for t in ax.get_yticklabels()] == ["alpha", "beta"]
    assert [t.get_text() for t in ax.get_xticklabels()] == [
        bench._TYPE_LABELS[t] for t in ANOMALY_TYPES
    ]
    texts = sorted((t.get_position()[1], t.get_position()[0], t.get_text()) for t in ax.texts)
    expected = sorted(
        (i, j, "-" if np.isnan(v) else f"{v:.2f}")
        for i, row in enumerate(recall.to_numpy())
        for j, v in enumerate(row)
    )
    assert texts == expected
    image = ax.images[0]
    assert image.get_clim() == (0.0, 1.0) and image.get_cmap().name == "YlGnBu"
    assert colorbar.get_ylabel() == "recall on that type"
    dark = {t.get_text(): t.get_color() for t in ax.texts}
    assert dark["0.58"] == "white" and dark["0.08"] == "black"
    assert fig.get_size_inches().tolist() == [8.0, 0.7 * 2 + 1.6]


def test_command_writes_tables_figure_record_and_prints_the_report(
    tmp_path, monkeypatch, capsys, caplog
):
    out = tmp_path / "x" / "y" / "results"
    figure = tmp_path / "fig" / "heat.png"
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_synthetic_benchmark", "--seeds", "1", "2", "--rows", "300"]
        + ["--figure", str(figure), "--results-dir", str(out)],
    )
    with caplog.at_level(logging.INFO):
        bench.main()
    names = sorted(p.name for p in out.iterdir())
    assert [
        bool(re.fullmatch(p, n))
        for p, n in zip(
            sorted(
                [
                    rf"run_synthetic_{STAMP}\.json",
                    rf"synthetic_{STAMP}\.md",
                    rf"synthetic_metrics_{STAMP}\.csv",
                    rf"synthetic_precision_{STAMP}\.csv",
                    rf"synthetic_recall_{STAMP}\.csv",
                ]
            ),
            names,
            strict=True,
        )
    ] == [True] * 5
    markdown = next(out.glob("synthetic_[0-9]*.md")).read_text()
    assert markdown.startswith(
        "Synthetic dataset, 2 seeds, mean ± std on the 15% test split.\n\n### Aggregate metrics\n\n"
    )
    sections = re.split(r"\n### ", markdown)
    assert [s.split("\n", 1)[0] for s in sections[1:]] == [
        "Aggregate metrics",
        "Recall by anomaly type",
        "Precision by anomaly type (clean rows as the only negatives)",
    ]
    assert (
        "| method | precision | recall | f1 | roc_auc | pr_auc | flagged_pct | detect_s |"
        in markdown
    )
    assert "| method | " + " | ".join(ANOMALY_TYPES) + " |" in markdown
    printed = capsys.readouterr().out
    assert printed == "\n" + markdown + "\n"
    assert figure.is_file()
    stamp = re.search(STAMP, next(out.glob("run_synthetic_*.json")).name).group()
    record = json.loads(next(out.glob("run_synthetic_*.json")).read_text())
    assert record["experiment"] == "synthetic_benchmark"
    assert record["seeds"] == [1, 2]
    assert record["dataset"] == {"identity": "synthetic"}
    assert record["settings"] == {
        "rows": 300,
        "anomaly_rate_per_type": config.SYNTHETIC_ANOMALY_RATE,
        "split_ratios": [0.7, 0.15, 0.15],
        "split_strategy": "customer_identity_grouped_stratified",
        "features": FEATURE_COLUMNS,
        "detectors": ALL_NAMES,
        "calibration": "train_label_prevalence",
        "pr_auc_definition": "average_precision",
        "per_type_precision": "clean_plus_target_type",
    }
    assert record["outputs"] == [
        f"synthetic_metrics_{stamp}.csv",
        f"synthetic_recall_{stamp}.csv",
        f"synthetic_precision_{stamp}.csv",
        f"synthetic_{stamp}.md",
        str(figure),
    ]
    messages = _messages(caplog, "run_synthetic_benchmark")
    assert messages[0] == "seeds: [1, 2]"
    assert messages[-1] == f"figure -> {figure}"
    recall = pd.read_csv(next(out.glob("synthetic_recall_*.csv")), index_col="method")
    assert recall.columns.tolist() == [f"{t}_{s}" for s in ("mean", "std") for t in ANOMALY_TYPES]


def test_command_defaults_and_help(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(sys, "argv", ["run_synthetic_benchmark", "--help"])
    with pytest.raises(SystemExit):
        bench.main()
    out = capsys.readouterr().out
    assert bench.__doc__.splitlines()[0] in out
    for option in ("--seeds", "--rows", "--figure", "--results-dir"):
        assert option in out
    assert "smaller dataset for a quick run" in out
    seen = {}

    def stop(seeds, rows):
        seen.update(seeds=seeds, rows=rows)
        raise RuntimeError("stop")

    monkeypatch.setattr(bench, "run", stop)
    monkeypatch.setattr(sys, "argv", ["run_synthetic_benchmark"])
    with pytest.raises(RuntimeError, match="^stop$"):
        bench.main()
    assert seen == {"seeds": list(config.BENCHMARK_SEEDS), "rows": None}


# --- run_severity -----------------------------------------------------------


def test_severity_sweep_regenerates_the_data_for_every_severity_and_seed(monkeypatch):
    calls = []
    real = run_severity.make_synthetic

    def spy(**kwargs):
        calls.append(kwargs)
        return real(n_rows=300, seed=kwargs["seed"], severity=kwargs["severity"])

    monkeypatch.setattr(run_severity, "make_synthetic", spy)
    curves = run_severity.run([0.5, 2.0], [1, 2], None)
    assert calls == [
        {"seed": 1, "severity": 0.5},
        {"seed": 2, "severity": 0.5},
        {"seed": 1, "severity": 2.0},
        {"seed": 2, "severity": 2.0},
    ]
    assert curves.columns.tolist() == ["severity", "method", "anomaly_type", "recall"]
    assert sorted(curves.severity.unique()) == [0.5, 2.0]
    assert curves.method.unique().tolist() == [*ALL_NAMES, "transform_dedup"]
    assert curves.anomaly_type.unique().tolist() == ANOMALY_TYPES
    assert len(curves) == 2 * len(ALL_NAMES + ["x"]) * len(ANOMALY_TYPES)
    calls.clear()
    run_severity.run([1.0], [3], 300)
    assert calls == [{"seed": 3, "severity": 1.0, "n_rows": 300}]


def test_severity_recall_is_the_mean_over_seeds():
    curves = run_severity.run([1.0], [1, 2], 300)
    per_seed = [
        bench.evaluate(make_synthetic(seed=s, severity=1.0, n_rows=300), s)["recall"]
        for s in (1, 2)
    ]
    expected = (per_seed[0] + per_seed[1]) / 2
    row = curves[(curves.method == "iqr") & (curves.anomaly_type == "univariate_outlier")]
    assert row.recall.iloc[0] == pytest.approx(expected.loc["iqr", "univariate_outlier"])


def test_severity_figure_has_one_panel_per_scaled_type(tmp_path, captured_figures):
    curves = pd.DataFrame(
        [
            {"severity": s, "method": m, "anomaly_type": t, "recall": r}
            for s, r in ((2.0, 0.9), (1.0, 0.5))
            for m in ("iqr", "zscore", "transform_dedup")
            for t in run_severity.MAGNITUDE_TYPES
        ]
    )
    path = run_severity.render(curves, tmp_path / "a" / "b" / "sev.png")
    assert path.is_file()
    fig = captured_figures[-1]
    axes = fig.axes
    assert [a.get_title() for a in axes] == [
        "univariate outlier",
        "multivariate outlier",
        "temporal drift",
    ]
    assert all(a.get_xlabel() == "injection severity (1.0 = reference)" for a in axes)
    assert axes[0].get_ylabel() == "recall on that type"
    assert [t.get_text() for t in axes[-1].get_legend().get_texts()] == ["iqr", "zscore"]
    line = axes[0].get_lines()[0]
    assert line.get_xdata().tolist() == [1.0, 2.0] and line.get_ydata().tolist() == [0.5, 0.9]
    assert axes[0].get_ylim() == (-0.03, 1.03)
    assert fig._suptitle.get_text() == (
        "Detection rate by anomaly type versus injection severity (synthetic)"
    )
    assert fig.get_size_inches().tolist() == pytest.approx([12.6, 3.6])


def test_severity_command_writes_curves_figure_record_and_pivot(
    tmp_path, monkeypatch, capsys, caplog
):
    out, figure = tmp_path / "r" / "s", tmp_path / "f" / "sev.png"
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_severity", "--severities", "1", "2", "--seeds", "1", "--rows", "300"]
        + ["--figure", str(figure), "--results-dir", str(out)],
    )
    with caplog.at_level(logging.INFO):
        run_severity.main()
    csv = next(out.glob("severity_*.csv"))
    assert re.fullmatch(rf"severity_{STAMP}\.csv", csv.name)
    assert pd.read_csv(csv).columns.tolist() == ["severity", "method", "anomaly_type", "recall"]
    record = json.loads(next(out.glob("run_severity_*.json")).read_text())
    assert record["experiment"] == "synthetic_severity"
    assert record["seeds"] == [1] and record["dataset"] == {"identity": "synthetic"}
    assert record["settings"] == {
        "rows": 300,
        "severities": [1.0, 2.0],
        "split_ratios": [0.7, 0.15, 0.15],
        "split_strategy": "customer_identity_grouped_stratified",
        "calibration": "train_label_prevalence",
    }
    assert record["outputs"] == [csv.name, str(figure)]
    printed = capsys.readouterr().out
    assert printed.startswith("\n")
    assert "anomaly_type" in printed and "univariate_outlier" in printed
    assert "severity 1.00 seed 1 done" in _messages(caplog, "run_severity")
    assert _messages(caplog, "run_severity")[-1] == f"figure -> {figure}"


def test_severity_defaults_and_row_count_in_the_record(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["run_severity", "--help"])
    with pytest.raises(SystemExit):
        run_severity.main()
    out = capsys.readouterr().out
    assert "Detection rate versus injection severity" in out
    for option in ("--severities", "--seeds", "--rows", "--figure", "--results-dir"):
        assert option in out
    seen = {}

    def stop(severities, seeds, rows):
        seen.update(severities=severities, seeds=seeds, rows=rows)
        raise RuntimeError("stop")

    monkeypatch.setattr(run_severity, "run", stop)
    monkeypatch.setattr(sys, "argv", ["run_severity"])
    with pytest.raises(RuntimeError, match="^stop$"):
        run_severity.main()
    assert seen == {"severities": [0.5, 1.0, 2.0, 3.0, 5.0], "seeds": [42, 1, 2], "rows": None}


# --- additional contracts: split identity, figure styling, options ------------


def test_synthetic_partitions_are_pinned_for_the_published_tables():
    # The identity-grouped split decides which customers are scored in every
    # published synthetic number; a change must come with a replay.
    import hashlib

    parts = bench._split_synthetic(make_synthetic(n_rows=600, seed=3), 3)
    text = "|".join(",".join(map(str, part.customer_id.tolist())) for part in parts)
    assert hashlib.sha256(text.encode()).hexdigest() == (
        "24d4c99b91c5be14b31e4855e57b9113e2708fbd09af4be4fcf5427b78a4277b"
    )
    assert [len(part) for part in parts] == [432, 93, 93]
    assert all(part.index.equals(pd.RangeIndex(len(part))) for part in parts)


def test_per_type_scores_keep_clean_rows_as_the_only_extra_negatives():
    types = pd.Series(["clean", "clean", "missing_value", "duplicate", "duplicate"])
    flags = pd.Series([False, True, True, True, False])
    recall, precision = bench._per_type(flags, types)
    assert recall["missing_value"] == 1.0 and precision["missing_value"] == 0.5
    assert recall["duplicate"] == 0.5 and precision["duplicate"] == 0.5
    assert np.isnan(recall["temporal_drift"]) and np.isnan(precision["temporal_drift"])
    none_flagged = pd.Series([False] * 5)
    recall, precision = bench._per_type(none_flagged, types)
    assert recall["duplicate"] == 0.0 and precision["duplicate"] == 0.0


def test_per_type_reports_misaligned_indices_in_its_own_words():
    with pytest.raises(ValueError, match="^flags and anomaly_type must have the same index$"):
        bench._per_type(pd.Series([True], index=[1]), pd.Series(["clean"], index=[2]))


def test_evaluation_scores_every_method_on_the_test_rows_after_fitting_on_train(
    monkeypatch, tracking_detector, caplog
):
    frame = make_synthetic(n_rows=300, seed=2)
    train, _, test = bench._split_synthetic(frame, 2)
    monkeypatch.setattr(bench, "all_detectors", lambda **_: [tracking_detector])
    with caplog.at_level(logging.INFO):
        result = bench.evaluate(frame, 2)
    pd.testing.assert_frame_equal(
        tracking_detector.fit_input, train[FEATURE_COLUMNS].reset_index(drop=True)
    )
    pd.testing.assert_frame_equal(
        tracking_detector.predict_input, test[FEATURE_COLUMNS].reset_index(drop=True)
    )
    assert result["metrics"]["detect_s"].dtype == float
    assert _messages(caplog, "run_synthetic_benchmark") == [
        "  seed 2: tracking done",
        "  seed 2: transform_dedup done",
    ]


def test_csv_files_keep_mean_and_spread_columns_for_every_table(tmp_path, monkeypatch):
    out = tmp_path / "r"
    monkeypatch.setattr(
        sys,
        "argv",
        ["run_synthetic_benchmark", "--seeds", "1", "--rows", "300", "--results-dir", str(out)]
        + ["--figure", str(tmp_path / "h.png")],
    )
    bench.main()
    metrics = pd.read_csv(next(out.glob("synthetic_metrics_*.csv")), index_col="method")
    columns = ["precision", "recall", "f1", "roc_auc", "pr_auc", "flagged_pct", "detect_s"]
    assert metrics.columns.tolist() == [f"{c}_mean" for c in columns] + [
        f"{c}_std" for c in columns
    ]
    precision = pd.read_csv(next(out.glob("synthetic_precision_*.csv")), index_col="method")
    assert precision.columns.tolist() == [f"{t}_mean" for t in ANOMALY_TYPES] + [
        f"{t}_std" for t in ANOMALY_TYPES
    ]
    text = next(out.glob("synthetic_[0-9]*.md")).read_text()
    assert "\n### Recall by anomaly type\n\n| method |" in text
    assert (
        "\n### Precision by anomaly type (clean rows as the only negatives)\n\n| method |" in text
    )


def test_command_options_are_forwarded_and_described(tmp_path, monkeypatch, capsys):
    seen = {}

    def spy(seeds, rows):
        seen.update(seeds=seeds, rows=rows)
        return {}

    monkeypatch.setattr(bench, "run", spy)
    monkeypatch.setattr(sys, "argv", ["run_synthetic_benchmark", "--rows", "321", "--seeds", "8"])
    with pytest.raises(KeyError):
        bench.main()
    assert seen == {"seeds": [8], "rows": 321}
    monkeypatch.setattr(sys, "argv", ["run_synthetic_benchmark", "--help"])
    with pytest.raises(SystemExit):
        bench.main()
    text = " ".join(capsys.readouterr().out.split())
    assert re.search(r"(^|\s)smaller dataset for a quick run(\s|$)", text)


def test_command_uses_the_configured_directory_and_quiets_noisy_loggers(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RESULTS_DIR", tmp_path / "configured")
    monkeypatch.setattr(bench, "PAPER_FIGURE", tmp_path / "paper" / "heat.png")
    monkeypatch.setattr(sys, "argv", ["run_synthetic_benchmark", "--seeds", "1", "--rows", "300"])
    logging.getLogger("great_expectations").setLevel(logging.NOTSET)
    logging.getLogger("matplotlib").setLevel(logging.NOTSET)
    bench.main()
    bench.main()
    assert (tmp_path / "paper" / "heat.png").is_file()
    assert len(list((tmp_path / "configured").glob("run_synthetic_*.json"))) >= 1
    assert logging.getLogger("great_expectations").level == logging.WARNING
    assert logging.getLogger("matplotlib").level == logging.WARNING
    from datetime import UTC, datetime

    name = next((tmp_path / "configured").glob("synthetic_metrics_*.csv")).name
    written = datetime.strptime(re.search(STAMP, name).group(), "%Y%m%d_%H%M%S")
    assert abs((datetime.now(UTC).replace(tzinfo=None) - written).total_seconds()) < 300


def test_heatmap_text_style_and_boundary_colour(tmp_path, captured_figures):
    from PIL import Image

    recall = pd.DataFrame([[0.55, 0.56] + [0.1] * 4], index=["m"], columns=ANOMALY_TYPES)
    path = bench.render_heatmap(recall, tmp_path / "h.png")
    ax = captured_figures[-1].axes[0]
    by_text = {t.get_text(): t for t in ax.texts}
    assert by_text["0.55"].get_color() == "black" and by_text["0.56"].get_color() == "white"
    assert {t.get_fontsize() for t in ax.texts} == {9.0}
    assert {(t.get_ha(), t.get_va()) for t in ax.texts} == {("center", "center")}
    assert ax.get_aspect() == "auto"
    assert ax.images[0].get_clim() == (0.0, 1.0)
    assert Image.open(path).info["dpi"] == pytest.approx((150, 150), abs=0.5)


# --- run_severity: figure styling and options -----------------------------------


def test_severity_lines_and_reference_marker_follow_the_style(tmp_path, captured_figures):
    from matplotlib.colors import to_hex
    from PIL import Image

    curves = pd.DataFrame(
        [
            {"severity": s, "method": m, "anomaly_type": t, "recall": 0.5}
            for s in (1.0, 2.0)
            for m in ("a", "b")
            for t in run_severity.MAGNITUDE_TYPES
        ]
    )
    out = tmp_path / "ready"
    out.mkdir()
    path = run_severity.render(curves, out / "s.png")  # existing directory is fine
    fig = captured_figures[-1]
    ax = fig.axes[0]
    solid = [line for line in ax.get_lines() if line.get_linestyle() == "-"]
    palette = plt.get_cmap("tab10")
    assert [line.get_marker() for line in solid] == ["o", "o"]
    assert [line.get_markersize() for line in solid] == [3.0, 3.0]
    assert [line.get_linewidth() for line in solid] == [1.4, 1.4]
    assert [to_hex(line.get_color()) for line in solid] == [to_hex(palette(0)), to_hex(palette(1))]
    marker = [line for line in ax.get_lines() if line.get_linestyle() == "--"]
    assert len(marker) == 1 and list(marker[0].get_xdata()) == [1.0, 1.0]
    assert marker[0].get_linewidth() == 0.8 and to_hex(marker[0].get_color()) == to_hex("0.7")
    legend = fig.axes[-1].get_legend()
    assert legend._loc == 4 and {t.get_fontsize() for t in legend.get_texts()} == {7.0}
    assert Image.open(path).info["dpi"] == pytest.approx((150, 150), abs=0.5)
    assert len(fig.axes) == 3


def test_severity_command_options_are_described_and_applied(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(config, "RESULTS_DIR", tmp_path / "configured")
    monkeypatch.setattr(run_severity, "PAPER_FIGURE", tmp_path / "paper" / "sev.png")
    monkeypatch.setattr(
        sys, "argv", ["run_severity", "--severities", "1", "2", "--seeds", "1", "--rows", "300"]
    )
    logging.getLogger("great_expectations").setLevel(logging.NOTSET)
    logging.getLogger("matplotlib").setLevel(logging.NOTSET)
    run_severity.main()
    run_severity.main()
    assert (tmp_path / "paper" / "sev.png").is_file()
    csv = sorted((tmp_path / "configured").glob("severity_*.csv"))[0]
    assert csv.read_text().splitlines()[1].count(",") == 3  # no index column
    assert logging.getLogger("great_expectations").level == logging.WARNING
    assert logging.getLogger("matplotlib").level == logging.WARNING
    from datetime import UTC, datetime

    written = datetime.strptime(re.search(STAMP, csv.name).group(), "%Y%m%d_%H%M%S")
    assert abs((datetime.now(UTC).replace(tzinfo=None) - written).total_seconds()) < 300
    curves = pd.read_csv(csv)
    wide = curves[curves["anomaly_type"].isin(run_severity.MAGNITUDE_TYPES)].pivot_table(
        index=["anomaly_type", "method"], columns="severity", values="recall"
    )
    assert capsys.readouterr().out.endswith("\n" + wide.round(3).to_string() + "\n")


def test_severity_rows_default_to_none_and_help_is_standalone(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["run_severity", "--help"])
    with pytest.raises(SystemExit):
        run_severity.main()
    assert "--rows ROWS" in " ".join(capsys.readouterr().out.split())
