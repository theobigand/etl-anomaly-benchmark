"""Download the cardiotocography anomaly dataset and write ``data/cardio.csv``.

The source is the ``cardio`` dataset as packaged for anomaly-detection
benchmarking (an ``.npz`` with an ``X`` feature matrix and a ``y`` label
where 1 marks the anomaly). It is small (1{,}831 rows), already
standardised, and genuinely imbalanced (9.6% anomalies), which is the
regime the detectors are designed for.

    python experiments/fetch_cardio.py
"""

from __future__ import annotations

import io
import logging
import urllib.request

import numpy as np
import pandas as pd

from etl_benchmark import config
from etl_benchmark.atomic import atomic_path
from etl_benchmark.logging_setup import setup_logging

log = logging.getLogger(__name__)

URL = "https://raw.githubusercontent.com/Minqi824/ADBench/main/adbench/datasets/Classical/6_cardio.npz"


def main() -> None:
    setup_logging()
    log.info("downloading %s", URL)
    with urllib.request.urlopen(URL, timeout=30) as resp:  # noqa: S310 - fixed https URL
        payload = resp.read()

    npz = np.load(io.BytesIO(payload))
    x, y = npz["X"], npz["y"].astype(int)
    frame = pd.DataFrame(x, columns=[f"f{i:02d}" for i in range(x.shape[1])])
    frame["label"] = y

    config.CARDIO_CSV.parent.mkdir(parents=True, exist_ok=True)
    with atomic_path(config.CARDIO_CSV) as partial:
        frame.to_csv(partial, index=False)
    log.info(
        "wrote %d rows x %d cols -> %s (%d anomalies, %.1f%%)",
        len(frame),
        frame.shape[1],
        config.CARDIO_CSV,
        int(y.sum()),
        100 * y.mean(),
    )


if __name__ == "__main__":
    main()
