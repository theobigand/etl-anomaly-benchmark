"""The demo entry point and logging setup behave as documented."""

import logging
from pathlib import Path

import pytest

from etl_benchmark import __main__ as entry
from etl_benchmark import config, logging_setup


def test_setup_logging_configures_the_root_logger_with_the_documented_format(monkeypatch):
    seen = {}
    monkeypatch.setattr(logging, "basicConfig", lambda **kwargs: seen.update(kwargs))
    logging_setup.setup_logging()
    assert seen == {
        "level": logging.INFO,
        "format": "%(asctime)s [%(name)s] %(levelname)s %(message)s",
        "datefmt": "%H:%M:%S",
    }
    logging_setup.setup_logging(logging.DEBUG)
    assert seen["level"] == logging.DEBUG


@pytest.fixture(autouse=True)
def _fresh_great_expectations_logger():
    logger = logging.getLogger("great_expectations")
    logger.setLevel(logging.NOTSET)
    yield
    logger.setLevel(logging.NOTSET)


def _run(monkeypatch, argv):
    calls = {}
    monkeypatch.setattr("sys.argv", ["etl_benchmark", *argv])
    monkeypatch.setattr(entry, "setup_logging", lambda: calls.setdefault("logging", True))
    monkeypatch.setattr(entry, "get_detector", lambda name: ("detector", name))
    monkeypatch.setattr(entry, "run_pipeline", lambda **kwargs: calls.update(kwargs))
    entry.main()
    return calls


def test_the_default_run_uses_the_zscore_detector_and_the_credit_card_file(monkeypatch):
    calls = _run(monkeypatch, [])
    assert calls["detector"] == ("detector", "zscore")
    assert calls["input_path"] == config.CREDIT_CARD_CSV
    assert calls["dump_dir"] == config.RESULTS_DIR and calls["logging"] is True


def test_the_selected_detector_and_input_are_passed_through(monkeypatch, tmp_path):
    source = tmp_path / "rows.csv"
    calls = _run(monkeypatch, ["--detector", "iqr", "--input", str(source)])
    assert calls["detector"] == ("detector", "iqr") and calls["input_path"] == Path(source)


def test_an_unknown_detector_is_refused_by_the_parser(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["etl_benchmark", "--detector", "nope"])
    with pytest.raises(SystemExit) as caught:
        entry.main()
    assert caught.value.code == 2 and "invalid choice" in capsys.readouterr().err


def test_the_great_expectations_logger_is_quietened(monkeypatch):
    _run(monkeypatch, [])
    assert logging.getLogger("great_expectations").level == logging.WARNING


def test_the_help_text_lists_the_documented_commands(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["etl_benchmark", "--help"])
    with pytest.raises(SystemExit):
        entry.main()
    out = " ".join(capsys.readouterr().out.split())
    assert "python -m etl_benchmark --detector iqr" in out
    assert "which detector to run (default: zscore)" in out
