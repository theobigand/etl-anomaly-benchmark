"""Write the controlled synthetic dataset to ``data/synthetic.csv``.

The file is not committed (like the other datasets); regenerate it with::

    python experiments/generate_synthetic.py            # defaults from config
    python experiments/generate_synthetic.py --rows 5000 --seed 1

It is fully deterministic for a given ``--rows``/``--rate``/``--seed``.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from etl_benchmark import config
from etl_benchmark.logging_setup import setup_logging
from etl_benchmark.synthetic import ANOMALY_TYPES, make_synthetic

log = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=config.SYNTHETIC_CSV)
    parser.add_argument("--rows", type=int, default=config.SYNTHETIC_ROWS)
    parser.add_argument("--rate", type=float, default=config.SYNTHETIC_ANOMALY_RATE)
    parser.add_argument("--seed", type=int, default=config.RANDOM_SEED)
    args = parser.parse_args()

    setup_logging()

    df = make_synthetic(n_rows=args.rows, anomaly_rate=args.rate, seed=args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)

    counts = df["anomaly_type"].value_counts()
    log.info("wrote %d rows x %d cols -> %s", len(df), df.shape[1], args.output)
    log.info("clean: %d", int(counts.get("clean", 0)))
    for name in ANOMALY_TYPES:
        log.info("  %-22s %d", name, int(counts.get(name, 0)))


if __name__ == "__main__":
    main()
