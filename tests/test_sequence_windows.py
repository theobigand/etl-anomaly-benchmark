import numpy as np
import pandas as pd
import pytest

from etl_benchmark.quality.windows import causal_windows, scores_to_events
from etl_benchmark.split import chronological_split

pytestmark = pytest.mark.protocol


def _frame(n=10):
    return pd.DataFrame(
        {"time": pd.date_range("2024-01-01", periods=n, freq="h"), "v": np.arange(n, dtype=float)}
    )


def test_each_event_gets_the_window_of_its_own_past_edge_padded_with_the_first_row():
    windows, order = causal_windows(_frame(6), "time", ["v"], size=3)
    assert windows.shape == (6, 3, 1)
    assert windows[:, :, 0].tolist() == [
        [0, 0, 0],
        [0, 0, 1],
        [0, 1, 2],
        [1, 2, 3],
        [2, 3, 4],
        [3, 4, 5],
    ]
    assert order.tolist() == [0, 1, 2, 3, 4, 5]


def test_a_window_never_contains_a_later_row():
    frame = _frame(12)
    before, _ = causal_windows(frame, "time", ["v"], size=4)
    changed = frame.copy()
    changed.loc[8:, "v"] += 100.0
    after, _ = causal_windows(changed, "time", ["v"], size=4)
    np.testing.assert_array_equal(before[:8], after[:8])
    assert not np.array_equal(before[8:], after[8:])


def test_window_order_follows_time_not_input_order_and_ties_keep_input_order():
    frame = _frame(6).iloc[::-1].reset_index(drop=True)
    windows, order = causal_windows(frame, "time", ["v"], size=2)
    assert frame["v"].to_numpy()[order].tolist() == [0, 1, 2, 3, 4, 5]
    assert windows[:, -1, 0].tolist() == [0, 1, 2, 3, 4, 5]
    tied = pd.DataFrame({"time": pd.Timestamp("2024-01-01"), "v": [5.0, 3.0, 4.0]})
    _, tied_order = causal_windows(tied, "time", ["v"], size=2)
    assert tied_order.tolist() == [0, 1, 2]


def test_scores_return_to_the_original_row_index_whatever_the_input_order():
    frame = _frame(6).iloc[[3, 0, 5, 1, 4, 2]]
    windows, order = causal_windows(frame, "time", ["v"], size=2)
    scores = scores_to_events(windows[:, -1, 0] * 10.0, order, frame.index)
    assert scores.index.equals(frame.index)
    assert scores.to_dict() == {i: frame.loc[i, "v"] * 10.0 for i in frame.index}


def test_windows_built_per_partition_never_reach_into_another_partition():
    frame = _frame(40)
    train, val, test = chronological_split(frame, "time")
    windows, _ = causal_windows(test, "time", ["v"], size=5)
    assert set(np.unique(windows)) <= set(test["v"])
    assert windows.min() >= test["v"].min()
    assert test["v"].min() > train["v"].max() and test["v"].min() > val["v"].max()


def test_multiple_features_keep_their_columns_and_order():
    frame = _frame(4).assign(w=lambda f: f["v"] * -1)
    windows, _ = causal_windows(frame, "time", ["w", "v"], size=2)
    assert windows.shape == (4, 2, 2)
    assert windows[3].tolist() == [[-2.0, 2.0], [-3.0, 3.0]]


def test_a_window_of_one_is_the_event_itself():
    windows, _ = causal_windows(_frame(5), "time", ["v"], size=1)
    assert windows.shape == (5, 1, 1)
    assert windows[:, 0, 0].tolist() == [0, 1, 2, 3, 4]


def test_many_ties_keep_the_input_order():
    tied = pd.DataFrame({"time": pd.Timestamp("2024-01-01"), "v": np.arange(100.0)})
    _, order = causal_windows(tied, "time", ["v"], size=2)
    assert order.tolist() == list(range(100))


@pytest.mark.parametrize("size", [0, -1, 1.5, True])
def test_window_length_must_be_a_positive_integer(size):
    with pytest.raises(ValueError, match="^window size must be a positive integer$"):
        causal_windows(_frame(5), "time", ["v"], size=size)


def test_unusable_inputs_are_rejected_before_windowing():
    frame = _frame(5)
    with pytest.raises(ValueError, match="^missing timestamp column 'later'$"):
        causal_windows(frame, "later", ["v"], size=2)
    with pytest.raises(ValueError, match="^missing feature column$"):
        causal_windows(frame, "time", ["absent"], size=2)
    with pytest.raises(ValueError, match="^feature columns must be finite$"):
        causal_windows(frame.assign(v=np.nan), "time", ["v"], size=2)
    with pytest.raises(ValueError, match="^invalid timestamp$"):
        causal_windows(frame.assign(time="oops"), "time", ["v"], size=2)
    with pytest.raises(ValueError, match="^scores and positions must have the same length$"):
        scores_to_events(np.zeros(3), np.arange(2), pd.RangeIndex(2))
