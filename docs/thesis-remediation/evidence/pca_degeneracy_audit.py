# ruff: noqa: E402, E501
"""Which PCA results of the study rest on a full-rank reconstruction (scores are rounding noise)?

    python docs/thesis-remediation/evidence/pca_degeneracy_audit.py [OUTPUT.json]

`PCAReconstruction` keeps the components that explain 95 % of the variance of the standardised features. When that rule keeps
every component, the reconstruction is exact and every score is floating-point noise (about 1e-32), so the ranking, the
threshold and every metric derived from them depend on the linear-algebra back end. For each table the study uses, this
counts the features, the components kept and the median score, and writes one JSON record with the library versions. The pool
tables are read as the typed-injection study reads them; they are not tracked, so the record is the evidence.
"""

import json
import platform
import sys
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "experiments"), str(ROOT / "src"), str(ROOT / "research"), str(ROOT)]
import injection
import multi_schema as ms
import pandas as pd
import scipy
import sklearn
import uci_loader

from etl_benchmark.datasets import DATASETS
from etl_benchmark.quality.ml import PCADetector
from etl_benchmark.synthetic import FEATURE_COLUMNS, make_synthetic


def kept(frame: pd.DataFrame) -> dict:
    detector = PCADetector(contamination=0.05).fit(frame)
    model = next(v for v in vars(detector).values() if hasattr(v, "pca_"))
    scores = np.asarray(detector.score(frame), float)
    features = len(detector.feature_names_)
    components = int(model.pca_.n_components_)
    return {
        "features": features,
        "components": components,
        "full_rank": components == features,
        "median_score": float(np.median(scores)),
    }


def main() -> None:
    tables: dict[str, dict] = {}
    tables["synthetic customer"] = kept(make_synthetic(seed=42)[FEATURE_COLUMNS])
    for spec in ms.SCHEMAS.values():
        tables[f"schema {spec.name}"] = kept(ms.make(spec, 3000, 1)[ms.features(spec)])
    for name in ("credit_card", "cardio", "water_quality"):
        spec = DATASETS[name]
        tables[f"real {name}"] = kept(spec.features(spec.load()))
    carriers = {}
    for path in sorted((ROOT / "data" / "pool").glob("*.csv"), key=lambda p: int(p.stem)):
        try:
            clean, _ = injection.prepare(uci_loader.read_table(path), seed=42)
        except injection.NotEligible:
            continue
        except Exception as error:
            carriers[path.stem] = {"error": repr(error)[:80]}
            continue
        carriers[path.stem] = kept(clean)
    usable = {k: v for k, v in carriers.items() if "error" not in v}
    record = {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "scikit-learn": sklearn.__version__,
        "blas": np.show_config(mode="dicts")["Build Dependencies"]["blas"].get("name"),
        "tables": tables,
        "typed_injection_carriers": {
            "eligible": len(usable),
            "full_rank": sorted(k for k, v in usable.items() if v["full_rank"]),
            "detail": carriers,
        },
    }
    text = json.dumps(record, indent=1, sort_keys=True) + "\n"
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(text)
    print(text)


if __name__ == "__main__":
    main()
