# ruff: noqa: E402, E501
"""Mean PCA recall per anomaly type on the synthetic customer table, over the benchmark seeds, for this interpreter.

    python docs/thesis-remediation/evidence/pca_backend_recall.py [OUTPUT.json]

Run it with each interpreter to see how far the recall of the full-rank PCA depends on the linear-algebra back end.
"""

import json
import platform
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "experiments"), str(ROOT / "src"), str(ROOT)]
import numpy as np
import run_synthetic_benchmark as rsb
import scipy

from etl_benchmark import config
from etl_benchmark.synthetic import make_synthetic


def main() -> None:
    per_seed = {}
    for seed in config.BENCHMARK_SEEDS:
        recall = rsb.evaluate(make_synthetic(seed=seed), seed)["recall"].loc["pca"]
        per_seed[str(seed)] = {k: round(float(v), 4) for k, v in recall.items()}
    types = list(next(iter(per_seed.values())))
    mean = {t: round(float(np.mean([r[t] for r in per_seed.values()])), 4) for t in types}
    record = {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "blas": np.show_config(mode="dicts")["Build Dependencies"]["blas"].get("name"),
        "seeds": list(config.BENCHMARK_SEEDS),
        "pca_recall_by_seed": per_seed,
        "pca_recall_mean": mean,
    }
    text = json.dumps(record, indent=1) + "\n"
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(text)
    print(text)


if __name__ == "__main__":
    main()
