"""The injected ground truth is pinned for a fixed carrier and seed: any change to a magnitude, a
group, a time or a label of the typed injection changes these digests (the archived typed runs
depend on exactly this construction)."""

import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import injection as inj  # noqa: E402


def _carrier():
    rng = np.random.default_rng(11)
    a = rng.normal(50, 10, 600)
    return pd.DataFrame(
        {
            "a": a,
            "b": 0.8 * a + rng.normal(0, 4, 600),
            "c": rng.gamma(4, 5, 600),
            "d": rng.normal(size=600),
        }
    )


def _digest(out):
    h = hashlib.sha256()
    cols = [c for c in out.columns if c not in inj.META]
    h.update(np.nan_to_num(out[cols].to_numpy(float), nan=-12345.678).round(9).tobytes())
    h.update(out["t"].astype("int64").to_numpy().tobytes())
    h.update(out["group_id"].to_numpy("int64").tobytes())
    h.update("|".join(out["anomaly_type"]).encode())
    return h.hexdigest()


def test_the_reference_severity_injection_is_unchanged():
    out = inj.inject(_carrier(), seed=3, severity=1.0)
    assert _digest(out) == "25b7c14a8380f6f25c7b22c51ac8378f2645cf46215ceafac1d082a4dc519ca7"


def test_a_doubled_severity_changes_the_magnitudes_and_the_quantile_limits_as_recorded():
    out = inj.inject(_carrier(), seed=3, severity=2.0)
    assert _digest(out) == "2fc7116b0057fff192484cf400599b8f8e715f859a6a60346d569dc2add41af9"


def test_a_carrier_with_no_non_negative_column_only_gets_scale_errors():
    carrier = _carrier()
    negative = carrier.assign(
        a=-carrier["a"], b=-carrier["b"], c=-carrier["c"], d=-carrier["d"] - 10
    )
    out = inj.inject(negative, seed=3)
    assert _digest(out) == "9b9c672848ade99627ccf573260e67245f07a14b018cbd1ec864549f6b1aaec8"


def test_the_row_count_limit_is_six_blocks_of_at_least_fifteen_rows():
    rng = np.random.default_rng(0)

    def table(rows):
        return pd.DataFrame(rng.normal(size=(rows, 4)), columns=list("abcd"))

    assert len(inj.inject(table(90), seed=1)) == 90 + 15
    with pytest.raises(inj.NotEligible) as refused:
        inj.inject(table(89), seed=1)
    assert str(refused.value) == "too few rows for six anomaly groups"
