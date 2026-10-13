import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
import run_curves  # noqa: E402


def test_curves_use_identity_disjoint_synthetic_split(monkeypatch):
    seen = []
    original = run_curves._split_synthetic

    def observe(frame, seed):
        parts = original(frame, seed)
        seen.append(parts)
        return parts

    monkeypatch.setattr(run_curves, "_split_synthetic", observe)
    run_curves._split_synth(42)
    assert len(seen) == 1
    train, val, test = seen[0]
    assert set(train.customer_id).isdisjoint(val.customer_id)
    assert set(train.customer_id).isdisjoint(test.customer_id)
