import sys

import numpy as np
import pandas as pd
import pytest

from etl_benchmark import config
from etl_benchmark.quality.deep import (
    AE1SVMDetector,
    DeepSVDDDetector,
    DIFDetector,
    LUNARDetector,
    VAEDetector,
)

pytestmark = pytest.mark.protocol

# Few epochs keep the tests fast; the registry uses the PyOD defaults.
FAST = {
    VAEDetector: {"epoch_num": 8},
    DeepSVDDDetector: {"epochs": 8},
    DIFDetector: {"n_ensemble": 5},
    AE1SVMDetector: {"epochs": 8},
    LUNARDetector: {"n_epochs": 8},
}
DEEP = list(FAST)


def _blob(n=300, seed=0):
    rng = np.random.default_rng(seed)
    x = rng.normal(0.0, 1.0, size=(n, 3))
    x[-5:] += 25.0
    return pd.DataFrame(x, columns=["a", "b", "c"])


def _build(cls, **kwargs):
    return cls(contamination=0.05, **FAST[cls], **kwargs)


@pytest.mark.parametrize("cls", DEEP)
def test_deep_detector_ranks_planted_outliers_highest(cls):
    df = _blob()
    scores = _build(cls).fit(df).score(df)
    assert scores.index.equals(df.index)
    assert scores.iloc[-5:].min() > scores.iloc[:-5].median()
    assert _build(cls).fit(df).predict(df).dtype == bool


@pytest.mark.parametrize("cls", DEEP)
def test_deep_detector_is_deterministic_for_a_seed(cls):
    df, probe = _blob(), _blob(30, seed=3)
    first = _build(cls, random_state=7).fit(df).score(probe)
    again = _build(cls, random_state=7).fit(df).score(probe)
    pd.testing.assert_series_equal(first, again)


@pytest.mark.parametrize("cls", DEEP)
def test_deep_detector_reports_the_unfitted_state_by_name(cls):
    detector = _build(cls)
    for method in (detector.predict, detector.score):
        with pytest.raises(RuntimeError, match=f"{detector.name} detector not fitted"):
            method(_blob())


@pytest.mark.parametrize("cls", DEEP)
def test_deep_detector_drops_text_and_imputes_missing_values(cls):
    df = _blob()
    df["label"] = "keep"
    df.loc[3, "a"] = np.nan
    detector = _build(cls).fit(df)
    assert detector.feature_names_ == ["a", "b", "c"]
    assert len(detector.predict(df)) == len(df)


def test_the_default_seed_is_the_project_seed():
    assert VAEDetector().random_state == config.RANDOM_SEED


def test_names_are_distinct_and_match_the_registry_keys():
    assert [cls.name for cls in DEEP] == ["vae", "deep_svdd", "dif", "ae1svm", "lunar"]


def test_settings_record_the_seed_device_and_versions():
    detector = _build(VAEDetector, random_state=5).fit(_blob())
    settings = detector.settings()
    assert settings["random_state"] == 5
    assert settings["device"] == "cpu"
    assert settings["contamination"] == 0.05
    assert {"torch", "pyod"} <= set(settings["versions"])


def test_the_fit_seeds_torch_whatever_the_global_state_was():
    import torch

    df, probe = _blob(), _blob(30, seed=3)
    torch.manual_seed(1)
    first = _build(AE1SVMDetector, random_state=11).fit(df).score(probe)  # no seed argument
    torch.manual_seed(2)
    again = _build(AE1SVMDetector, random_state=11).fit(df).score(probe)
    pd.testing.assert_series_equal(first, again)


def test_a_missing_torch_gives_an_actionable_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "torch", None)
    with pytest.raises(RuntimeError, match="needs torch"):
        _build(VAEDetector).fit(_blob())


def test_the_device_is_the_one_pyod_picks_when_none_is_fixed():
    detector = _build(AE1SVMDetector).fit(_blob())  # AE1SVM takes no device argument
    assert detector.settings()["device"] in {"cpu", "cuda"}
    assert detector.settings()["arguments"] == {"preprocessing": False, "epochs": 8}
