# ruff: noqa: E501
"""The typed heatmaps command: which files it writes, how big, from which runs, and its options."""

import json
import sys
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
import pytest

matplotlib.use("Agg")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import typed_figures as tf  # noqa: E402

TYPES = ["missing_value", "duplicate"]


def _run(folder, uci_id, name, values):
    frame = pd.DataFrame(values, index=["zscore", "iqr"], columns=TYPES)
    (folder / f"{uci_id}.json").write_text(
        json.dumps(
            {
                "uci_id": uci_id,
                "name": name,
                "recall_mean": json.loads(frame.to_json(orient="split")),
            }
        )
    )


@pytest.fixture
def runs(tmp_path):
    folder = tmp_path / "runs"
    folder.mkdir()
    _run(folder, 30, "third", [[0.3, 0.3], [0.3, 0.3]])
    _run(folder, 10, "first", [[0.1, 0.5], [0.9, np.nan]])
    _run(folder, 20, "second", [[0.5, 0.1], [0.3, 0.7]])
    return folder


@pytest.fixture
def drawn(monkeypatch):
    seen = {"draw": [], "subplots": [], "save": [], "axis": []}
    real = tf.plt.subplots

    def subplots(*args, **kwargs):
        seen["subplots"].append((args, kwargs))
        fig, ax = real(*args, **kwargs)
        original = fig.savefig
        fig.savefig = lambda path, **kw: (
            seen["save"].append((Path(path).name, kw)) or original(path, **kw)
        )
        return fig, ax

    monkeypatch.setattr(tf.plt, "subplots", subplots)
    monkeypatch.setattr(
        tf,
        "_draw",
        lambda ax, frame, title, annotate=True: seen["draw"].append((frame.copy(), title)),
    )
    return seen


def test_the_colour_scale_stays_zero_to_one_for_values_that_do_not_span_it():
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    tf._draw(ax, pd.DataFrame([[0.2, 0.4], [0.3, 0.5]]), "t")
    assert ax.images[0].get_clim() == (0.0, 1.0)
    plt.close(fig)


def test_the_pooled_figure_is_the_median_over_datasets_ignoring_missing_cells(
    runs, tmp_path, drawn
):
    out = tmp_path / "out"
    assert tf.main(["--runs", str(runs), "--output", str(out)]) == 0
    median, title = drawn["draw"][0]
    assert title == "Median detection rate over 3 real datasets (typed injection)"
    assert median.index.tolist() == ["zscore", "iqr"] and median.columns.tolist() == TYPES
    assert median.to_numpy().tolist() == [[0.3, 0.3], [0.3, 0.5]]


def test_the_panels_follow_the_uci_order_are_cut_to_the_requested_count_and_titled_by_name(
    runs, tmp_path, drawn
):
    tf.main(["--runs", str(runs), "--output", str(tmp_path / "o"), "--panels", "2"])
    panels = drawn["draw"][1:]
    assert [title for _, title in panels] == ["first", "second"]
    assert panels[0][0].loc["iqr", TYPES[0]] == 0.9


def test_long_names_are_cut_to_thirty_eight_characters(runs, tmp_path, drawn):
    _run(runs, 5, "x" * 50, [[0.1, 0.1], [0.1, 0.1]])
    tf.main(["--runs", str(runs), "--output", str(tmp_path / "o"), "--panels", "1"])
    assert drawn["draw"][1][1] == "x" * 38


def test_the_default_is_six_panels_in_a_grid_of_three_columns(tmp_path, drawn):
    folder = tmp_path / "runs"
    folder.mkdir()
    for i in range(8):
        _run(folder, i, f"d{i}", [[0.5, 0.5], [0.5, 0.5]])
    tf.main(["--runs", str(folder), "--output", str(tmp_path / "o")])
    assert len(drawn["draw"]) == 1 + 6
    args, kwargs = drawn["subplots"][1]
    assert args == (2, 3) and kwargs["squeeze"] is False
    assert kwargs["figsize"] == pytest.approx((5.2 * 3, 3.6 * 2))
    folder2 = tmp_path / "runs2"
    folder2.mkdir()
    for i in range(4):
        _run(folder2, i, f"d{i}", [[0.5, 0.5], [0.5, 0.5]])
    drawn["subplots"].clear()
    tf.main(["--runs", str(folder2), "--output", str(tmp_path / "o2"), "--panels", "4"])
    assert drawn["subplots"][1][0] == (2, 3) and drawn["subplots"][1][1][
        "figsize"
    ] == pytest.approx((15.6, 7.2))


def test_the_pooled_figure_is_seven_by_five_at_160_dpi_and_the_panels_130_dpi(
    runs, tmp_path, drawn
):
    tf.main(["--runs", str(runs), "--output", str(tmp_path / "o")])
    assert drawn["subplots"][0] == ((), {"figsize": (7, 5)})
    assert drawn["save"] == [("typed_pooled.png", {"dpi": 160}), ("typed_panels.png", {"dpi": 130})]


def test_unused_panel_slots_are_switched_off_and_used_ones_on(runs, tmp_path, monkeypatch):
    states = {}
    real = tf.plt.subplots

    def subplots(*args, **kwargs):
        fig, ax = real(*args, **kwargs)
        if not isinstance(ax, np.ndarray) or ax.ndim == 2:
            states["axes"] = ax
        return fig, ax

    monkeypatch.setattr(tf.plt, "subplots", subplots)
    tf.main(["--runs", str(runs), "--output", str(tmp_path / "o")])
    axes = states["axes"].ravel()
    assert [bool(a.axison) for a in axes] == [True, True, True]
    tf.main(["--runs", str(runs), "--output", str(tmp_path / "p"), "--panels", "1"])
    flat = states["axes"].ravel()
    assert [bool(a.axison) for a in flat] == [True, False, False]


def test_both_figures_are_written_into_a_new_or_existing_folder_and_closed(runs, tmp_path):
    out = tmp_path / "deep" / "out"
    matplotlib.pyplot.close("all")
    assert tf.main(["--runs", str(runs), "--output", str(out)]) == 0
    assert sorted(p.name for p in out.iterdir()) == ["typed_panels.png", "typed_pooled.png"]
    assert tf.main(["--runs", str(runs), "--output", str(out)]) == 0
    assert matplotlib.pyplot.get_fignums() == []


def test_the_options_are_required_and_described(capsys):
    for argv in (["--output", "o"], ["--runs", "r"]):
        with pytest.raises(SystemExit) as stop:
            tf.main(argv)
        assert stop.value.code == 2
    with pytest.raises(SystemExit):
        tf.main(["--help"])
    text = " ".join(capsys.readouterr().out.split())
    assert (
        "Heatmaps of the typed-injection results: pooled median and six panels chosen by UCI id."
        in text
    )
