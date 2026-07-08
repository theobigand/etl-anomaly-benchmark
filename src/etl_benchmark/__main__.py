from etl_benchmark import config
from etl_benchmark.logging_setup import setup_logging
from etl_benchmark.pipeline import run_pipeline


def main() -> None:
    setup_logging()
    # Demo run: one detector through the full pipeline, sorted rows dumped.
    run_pipeline(dump_dir=config.RESULTS_DIR)


if __name__ == "__main__":
    main()
