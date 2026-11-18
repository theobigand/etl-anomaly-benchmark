"""The masking diagnostic: z-score recall on univariate outliers with and without invalid rows."""

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import injection as inj  # noqa: E402
import typed_benchmark as tb  # noqa: E402
import typed_masking as tm  # noqa: E402
import typed_run as tr  # noqa: E402

from etl_benchmark import config  # noqa: E402


def _injected(seed=0):
    rng = np.random.default_rng(1)
    a = rng.normal(50, 10, 4000)
    carrier = pd.DataFrame(
        {"a": a, "b": 0.8 * a + rng.normal(0, 4, 4000), "c": rng.gamma(4, 5, 4000)}
    )
    return inj.inject(carrier, seed=seed), list(carrier.columns)


def _zscore_recall(train, test, cols, ddof):
    mean, std = train[cols].mean(), train[cols].std(ddof=ddof)
    flagged = ((test[cols] - mean).abs() / std > config.ZSCORE_THRESHOLD).any(axis=1)
    return float(flagged[test["anomaly_type"] == "univariate_outlier"].mean())


@pytest.mark.parametrize("seed", [0, 5])
def test_masking_equals_an_independent_zscore_with_and_without_the_invalid_rows(seed):
    df, cols = _injected()
    train, _val, test = tb.split(df, seed)
    got = tm.masking(df, cols, seed)
    assert set(got) == {"with_invalid_in_train", "without_invalid_in_train"}
    clean = train[train["anomaly_type"] != "invalid_format"]
    assert len(clean) < len(train)  # the invalid rows exist and are the only ones removed
    # the detector's standard deviation convention (population or sample) is not under test
    for key, part in (("with_invalid_in_train", train), ("without_invalid_in_train", clean)):
        options = [_zscore_recall(part, test, cols, ddof) for ddof in (0, 1)]
        assert any(got[key] == pytest.approx(o, abs=1e-9) for o in options), key
    assert got["with_invalid_in_train"] < got["without_invalid_in_train"]


def test_masking_scores_only_the_univariate_outlier_rows_of_the_test_split():
    df, cols = _injected()
    _train, _val, test = tb.split(df, 0)
    got = tm.masking(df, cols, 0)
    n = int((test["anomaly_type"] == "univariate_outlier").sum())
    assert n > 0 and all(abs(v * n - round(v * n)) < 1e-9 for v in got.values())


def _curated_ids(n=2):
    path = Path(tm.__file__).resolve().parents[1] / "verification/evidence/dataset_registry"
    return json.loads((path / "uci_curated.json").read_text())["kept"][:n]


def test_main_writes_one_row_per_run_file_in_sorted_order(tmp_path, monkeypatch, capsys):
    metas = _curated_ids(2)
    runs = tmp_path / "runs"
    runs.mkdir()
    for m in reversed(metas):  # written in the opposite order to prove the sorting
        (runs / f"{m['uci_id']:03d}.json").write_text(json.dumps({"uci_id": m["uci_id"]}))
    (runs / "ignored.txt").write_text("not a run")
    calls = []
    df, cols = _injected()

    carrier = df[cols]
    root = Path(tm.__file__).resolve().parents[1]
    masked = []

    def load_carrier(meta, path, seed):
        calls.append((meta["uci_id"], path, seed))
        return carrier, None

    def inject(given, seed):
        assert given is carrier and seed == config.RANDOM_SEED
        return df

    reads = []
    real_read = Path.read_text

    def spy_read(self, *a, **k):
        reads.append(self)
        return real_read(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", spy_read)
    real_masking = tm.masking
    monkeypatch.setattr(tm, "masking", lambda *a: masked.append(a[2]) or real_masking(*a))
    monkeypatch.setattr(tr, "load_carrier", load_carrier)
    monkeypatch.setattr(inj, "inject", inject)
    out = tmp_path / "masking.json"
    assert tm.main(["--runs", str(runs), "--output", str(out)]) == 0
    assert capsys.readouterr().out == "2 datasets\n"
    ids = sorted(m["uci_id"] for m in metas)
    assert [c[0] for c in calls] == ids
    assert [c[1:] for c in calls] == [(root / "data" / "pool" / f"{i}.csv", 0) for i in ids]
    assert masked == [config.RANDOM_SEED] * 2
    assert root / "verification" / "evidence" / "dataset_registry" / "uci_curated.json" in reads
    rows = json.loads(out.read_text())
    assert [r["uci_id"] for r in rows] == ids
    expected = tm.masking(df, cols, config.RANDOM_SEED)
    for row in rows:
        assert row["name"] == next(m["name"] for m in metas if m["uci_id"] == row["uci_id"])
        assert {k: row[k] for k in expected} == expected
    assert out.read_text() == json.dumps(rows, indent=1) + "\n"


@pytest.mark.parametrize("missing", ["--runs", "--output"])
def test_main_requires_the_runs_directory_and_the_output_path(tmp_path, missing, capsys):
    args = {"--runs": str(tmp_path), "--output": str(tmp_path / "o.json")}
    del args[missing]
    with pytest.raises(SystemExit) as refused:
        tm.main([x for pair in args.items() for x in pair])
    assert refused.value.code == 2 and missing in capsys.readouterr().err
    with pytest.raises(SystemExit):
        tm.main(["--help"])
    help_text = capsys.readouterr().out
    assert "Diagnostic: do invalid-format rows" in help_text
    assert re.search(r"--runs RUNS\s+typed_run output, for the ids\n", help_text)


def test_masking_splits_with_the_seed_it_is_given(monkeypatch):
    df, cols = _injected()
    seeds = []
    real = tb.split
    monkeypatch.setattr(tb, "split", lambda d, seed: seeds.append(seed) or real(d, seed))
    tm.masking(df, cols, 13)
    assert seeds == [13]
