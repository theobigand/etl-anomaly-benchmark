"""What the typed heatmaps draw: labels, cell text, colours, scale and the files written."""

import json
import sys
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

matplotlib.use("Agg")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import typed_figures as tf  # noqa: E402


def _frame():
    return pd.DataFrame(
        [[0.0, 0.5, 0.61], [1.0, np.nan, 0.6]],
        index=["zscore", "iqr"],
        columns=["missing_value", "duplicate", "unknown_type"],
    )


def test_the_drawing_uses_the_short_type_labels_and_keeps_unknown_names_as_they_are():
    fig, ax = plt.subplots()
    tf._draw(ax, _frame(), "A title")
    assert [t.get_text() for t in ax.get_xticklabels()] == ["missing", "duplicate", "unknown_type"]
    assert [t.get_text() for t in ax.get_yticklabels()] == ["zscore", "iqr"]
    assert ax.get_title() == "A title" and ax.title.get_fontsize() == 9
    assert all(t.get_rotation() == 35 and t.get_ha() == "right" for t in ax.get_xticklabels())
    plt.close(fig)


def test_the_colour_scale_runs_from_zero_to_one_on_the_yellow_green_blue_map():
    fig, ax = plt.subplots()
    tf._draw(ax, _frame(), "t")
    image = ax.images[0]
    assert image.get_clim() == (0.0, 1.0) and image.get_cmap().name == "YlGnBu"
    assert ax.get_aspect() == "auto"
    assert image.get_array().shape == (2, 3)
    plt.close(fig)


def test_each_cell_is_written_with_two_decimals_white_above_six_tenths_and_black_otherwise():
    fig, ax = plt.subplots()
    tf._draw(ax, _frame(), "t")
    cells = {(t.get_position()): t for t in ax.texts}
    assert len(ax.texts) == 6
    assert cells[(0, 0)].get_text() == "0.00" and cells[(0, 0)].get_color() == "black"
    assert cells[(1, 0)].get_text() == "0.50" and cells[(1, 0)].get_color() == "black"
    assert cells[(2, 0)].get_text() == "0.61" and cells[(2, 0)].get_color() == "white"
    assert cells[(0, 1)].get_text() == "1.00" and cells[(0, 1)].get_color() == "white"
    assert cells[(2, 1)].get_text() == "0.60" and cells[(2, 1)].get_color() == "black"
    assert cells[(1, 1)].get_text() == "nan"
    assert all(t.get_fontsize() == 6.5 for t in ax.texts)
    assert all(t.get_ha() == "center" and t.get_va() == "center" for t in ax.texts)
    plt.close(fig)


def test_the_drawing_can_leave_the_cells_unwritten():
    fig, ax = plt.subplots()
    tf._draw(ax, _frame(), "t", annotate=False)
    assert len(ax.texts) == 0
    plt.close(fig)


def _runs(folder, count=8):
    for uci_id in range(count, 0, -1):
        frame = pd.DataFrame(
            0.1 * uci_id, index=["zscore", "iqr"], columns=["missing_value", "duplicate"]
        )
        payload = {
            "uci_id": uci_id,
            "name": f"dataset-{uci_id}-" + "x" * 40,
            "recall_mean": json.loads(frame.to_json(orient="split")),
        }
        (folder / f"{uci_id}.json").write_text(json.dumps(payload))


def test_the_command_writes_the_pooled_figure_and_the_panels_in_id_order(tmp_path, monkeypatch):
    runs = tmp_path / "runs"
    runs.mkdir()
    _runs(runs)
    drawn = []
    real = tf._draw
    monkeypatch.setattr(
        tf,
        "_draw",
        lambda ax, frame, title, annotate=True: (
            drawn.append(title) or real(ax, frame, title, annotate)
        ),
    )
    saved = []
    original = plt.Figure.savefig
    monkeypatch.setattr(
        plt.Figure,
        "savefig",
        lambda self, path, dpi=None: (
            saved.append((Path(path).name, dpi)) or original(self, path, dpi=dpi)
        ),
    )
    out = tmp_path / "new" / "figures"
    assert tf.main(["--runs", str(runs), "--output", str(out)]) == 0
    assert sorted(p.name for p in out.iterdir()) == ["typed_panels.png", "typed_pooled.png"]
    assert saved == [("typed_pooled.png", 160), ("typed_panels.png", 130)]
    assert drawn[0] == "Median detection rate over 8 real datasets (typed injection)"
    assert drawn[1:] == [(f"dataset-{i}-" + "x" * 40)[:38] for i in range(1, 7)]


def test_the_panel_count_is_an_option_and_the_unused_axes_stay_blank(tmp_path, monkeypatch):
    runs = tmp_path / "runs"
    runs.mkdir()
    _runs(runs, count=4)
    drawn = []
    real = tf._draw
    monkeypatch.setattr(
        tf,
        "_draw",
        lambda ax, frame, title, annotate=True: (
            drawn.append(title) or real(ax, frame, title, annotate)
        ),
    )
    figures = []
    original = plt.close
    monkeypatch.setattr(plt, "close", lambda fig=None: figures.append(fig) or original(fig))
    assert tf.main(["--runs", str(runs), "--output", str(tmp_path / "o"), "--panels", "2"]) == 0
    assert len(drawn) == 3
    panels = figures[-1]
    assert [a.axison for a in panels.axes] == [True, True, False, False, False, False][
        : len(panels.axes)
    ]
    assert panels.get_size_inches().tolist() == pytest.approx([5.2 * 3, 3.6 * 1])
    with pytest.raises(SystemExit) as stop:
        tf.main([])
    assert stop.value.code == 2
