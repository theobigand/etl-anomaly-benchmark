from etl_benchmark.logging_setup import setup_logging
from etl_benchmark.pipeline import run


def main() -> None:
    setup_logging()
    run()


if __name__ == "__main__":
    main()
