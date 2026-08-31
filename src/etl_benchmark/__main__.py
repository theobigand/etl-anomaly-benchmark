"""Pipeline demo: run one detector through the full ETL pipeline.

python -m etl_benchmark                       # Z-score (default)
python -m etl_benchmark --detector iqr
python -m etl_benchmark --detector great_expectations
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from etl_benchmark import config
from etl_benchmark.logging_setup import setup_logging
from etl_benchmark.pipeline import run_pipeline
from etl_benchmark.registry import ALL_NAMES, get_detector


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--detector",
        choices=ALL_NAMES,
        default="zscore",
        help="which detector to run (default: zscore)",
    )
    parser.add_argument("--input", type=Path, default=config.CREDIT_CARD_CSV)
    args = parser.parse_args()

    setup_logging()
    logging.getLogger("great_expectations").setLevel(logging.WARNING)

    # Demo run: one detector through the full pipeline, sorted rows dumped.
    run_pipeline(
        input_path=args.input,
        detector=get_detector(args.detector),
        dump_dir=config.RESULTS_DIR,
    )


if __name__ == "__main__":
    main()
