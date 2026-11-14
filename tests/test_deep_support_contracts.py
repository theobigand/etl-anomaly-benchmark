"""Contracts of the deep-detector wrapper and its representation helper."""

from importlib.metadata import version

import numpy as np
import pandas as pd
import pytest
import torch  # noqa: E402

from etl_benchmark.quality import deep  # noqa: E402
from etl_benchmark.quality import ml as ml_module  # noqa: E402
from etl_benchmark.quality._torch_models import FitScalerDIF  # noqa: E402


@pytest.mark.parametrize(("available", "device"), [(True, "cuda"), (False, "cpu")])
def test_the_default_device_follows_cuda_availability(monkeypatch, available, device):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: available)
    assert deep._default_device() == device


def test_the_selected_columns_reach_the_base_detector():
    assert deep.VAEDetector(columns=["a", "b"])._user_columns == ["a", "b"]
    assert deep.VAEDetector()._user_columns is None


def test_the_stored_settings_have_exact_names_the_fixed_device_and_installed_versions(monkeypatch):
    monkeypatch.setattr(deep, "_default_device", lambda: "sentinel")
    fixed = deep.VAEDetector().settings()
    assert set(fixed) == {"contamination", "random_state", "device", "arguments", "versions"}
    assert fixed["device"] == "cpu"
    assert fixed["versions"] == {
        "torch": version("torch"),
        "pyod": version("pyod"),
        "numpy": np.__version__,
    }
    assert deep.DeepSVDDDetector().settings()["device"] == "sentinel"


def test_fitting_swallows_progress_written_straight_to_the_output_stream(monkeypatch, capsys):
    def noisy(self, df):
        import sys

        sys.stdout.write("epoch 10 loss 0.5\n")
        return self

    monkeypatch.setattr(ml_module.PyODDetector, "fit", noisy)
    detector = deep.VAEDetector()
    assert detector.fit(pd.DataFrame({"a": [0.0, 1.0]})) is detector
    assert capsys.readouterr().out == ""


class _Stub:
    batch_size = 4
    device = "cpu"


def test_the_representation_is_computed_in_batches_and_standardised_with_the_fit_rows():
    sizes = []

    def net(batch):
        sizes.append(len(batch))
        return batch * 2.0

    stub = _Stub()
    fit_rows = torch.arange(20, dtype=torch.float32).reshape(10, 2)
    first = FitScalerDIF._deep_representation(stub, net, fit_rows)
    assert sizes == [4, 4, 2]
    scalers = stub.__dict__["_representation_scalers"]
    assert list(scalers) == [id(net)]
    new_rows = torch.tensor([[100.0, 100.0]])
    second = FitScalerDIF._deep_representation(stub, net, new_rows)
    assert stub.__dict__["_representation_scalers"] is scalers
    assert np.allclose(second, np.tanh(scalers[id(net)].transform(np.array([[200.0, 200.0]]))))
    assert first.shape == (10, 2)
