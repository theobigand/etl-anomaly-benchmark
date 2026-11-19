"""The T055 probe's pre-declared problem selection is deterministic and bounded."""

from research.neural_budget_probe import select


def test_selection_is_sorted_bounded_and_evenly_spaced():
    sizes = [100, 400, 900, 6000, 1200, 2000, 3000, 4999, 5000, 5001]
    rows = {f"p{i:02d}": n for i, n in enumerate(sizes)}
    jobs = [{"problem": k} for k in reversed(list(rows))]
    chosen = [j["problem"] for j in select(jobs, rows, count=3)]
    assert chosen == ["p01", "p04", "p06"]
    assert all(300 <= rows[c] <= 5000 for c in chosen)
    assert chosen == [j["problem"] for j in select(jobs[::-1], rows, count=3)]
