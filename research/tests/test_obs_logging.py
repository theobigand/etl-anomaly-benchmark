"""Central logging configuration: format, levels, destinations, third-party bridging."""

import ast
import io
import json
import logging
import re
import sys
import warnings
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import obs_logging as ol  # noqa: E402


@pytest.fixture(autouse=True)
def clean_logging():
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    levels = {n: logging.getLogger(n).level for n in ol.THIRD_PARTY}
    yield
    for handler in [h for h in root.handlers if h not in handlers]:
        root.removeHandler(handler)
        handler.close()
    root.setLevel(level)
    for name, value in levels.items():
        logging.getLogger(name).setLevel(value)
    logging.captureWarnings(False)


def _emit(env, *records):
    stream = io.StringIO()
    ol.configure(env, stream=stream)
    log = logging.getLogger("etl.test")
    for level, message, extra in records:
        log.log(level, message, extra=extra)
    return stream.getvalue()


def test_the_defaults_are_info_console_stderr_and_warnings_captured():
    assert ol.settings({}) == {
        "level": "INFO",
        "format": "console",
        "destination": "stderr",
        "file": None,
        "third_party": "WARNING",
        "capture_warnings": True,
    }


def test_json_lines_carry_utc_level_logger_message_and_extra_fields():
    out = _emit(
        {"ETL_LOG_FORMAT": "json"},
        (logging.INFO, "stage %s done", None),
        (logging.WARNING, "slow", {"stage": "load", "rows": 12}),
    )
    first, second = (json.loads(line) for line in out.splitlines())
    assert first["message"] == "stage %s done" and first["level"] == "INFO"
    assert first["logger"] == "etl.test"
    assert first["timestamp"].endswith("Z") and "T" in first["timestamp"]
    assert (second["level"], second["stage"], second["rows"]) == ("WARNING", "load", 12)
    assert list(second)[:4] == ["timestamp", "level", "logger", "message"]


def test_a_json_record_is_one_line_and_an_exception_is_structured():
    stream = io.StringIO()
    ol.configure({"ETL_LOG_FORMAT": "json"}, stream=stream)
    try:
        raise KeyError("missing")
    except KeyError:
        logging.getLogger("etl.test").exception("failed\nunit")
    (line,) = stream.getvalue().splitlines()
    record = json.loads(line)
    assert record["message"] == "failed\nunit" and record["level"] == "ERROR"
    assert record["exception"]["type"] == "KeyError"
    assert record["exception"]["message"] == "'missing'"
    assert "Traceback" in record["exception"]["stack"]


def test_values_that_json_cannot_hold_are_written_as_text_not_dropped():
    out = _emit({"ETL_LOG_FORMAT": "json"}, (logging.INFO, "x", {"path": Path("a/b")}))
    assert json.loads(out)["path"] == "a/b"


def test_the_console_format_is_readable_and_in_utc():
    out = _emit({}, (logging.INFO, "hello", None))
    assert out.endswith("[etl.test] INFO hello\n")
    assert re.match(r"^\d\d:\d\d:\d\dZ \[etl\.test\] INFO hello\n$", out)  # HH:MM:SSZ prefix
    assert ol.ConsoleFormatter.converter(0).tm_hour == 0  # gmtime, not local time


def test_the_level_comes_from_the_environment_and_filters_records():
    out = _emit(
        {"ETL_LOG_LEVEL": "warning"},
        (logging.INFO, "hidden", None),
        (logging.WARNING, "shown", None),
        (logging.CRITICAL, "also", None),
    )
    assert "hidden" not in out and "shown" in out and "also" in out
    assert logging.getLogger().level == logging.WARNING


@pytest.mark.parametrize(
    ("env", "message"),
    [
        ({"ETL_LOG_LEVEL": "LOUD"}, "ETL_LOG_LEVEL must be one of DEBUG, INFO"),
        ({"ETL_LOG_FORMAT": "xml"}, "ETL_LOG_FORMAT must be one of console, json"),
        ({"ETL_LOG_DEST": "syslog"}, "ETL_LOG_DEST must be one of stderr, stdout, file"),
        ({"ETL_LOG_DEST": "file"}, "ETL_LOG_DEST=file needs ETL_LOG_FILE"),
        ({"ETL_LOG_CAPTURE_WARNINGS": "yes"}, "ETL_LOG_CAPTURE_WARNINGS must be 0 or 1"),
        ({"ETL_LOG_THIRD_PARTY_LEVEL": "x"}, "ETL_LOG_THIRD_PARTY_LEVEL must be one of"),
    ],
)
def test_an_invalid_setting_is_refused_by_name_never_ignored(env, message):
    with pytest.raises(ValueError, match=message):
        ol.settings(env)
    with pytest.raises(ValueError, match=message):
        ol.configure(env)


def test_configure_replaces_its_own_handler_and_keeps_foreign_ones():
    root = logging.getLogger()
    foreign = logging.NullHandler()
    root.addHandler(foreign)
    try:
        for _ in range(3):
            ol.configure({}, stream=io.StringIO())
        ours = [h for h in root.handlers if getattr(h, ol.MARK, False)]
        assert len(ours) == 1 and foreign in root.handlers
    finally:
        root.removeHandler(foreign)


def test_a_file_destination_creates_the_folder_and_writes_json(tmp_path):
    target = tmp_path / "logs" / "run.jsonl"
    env = {"ETL_LOG_DEST": "file", "ETL_LOG_FILE": str(target), "ETL_LOG_FORMAT": "json"}
    ol.configure(env)
    logging.getLogger("etl.test").info("to file")
    for handler in logging.getLogger().handlers:
        handler.flush()
    assert json.loads(target.read_text().splitlines()[0])["message"] == "to file"


def test_stdout_and_stderr_destinations_use_the_process_streams(capsys):
    ol.configure({"ETL_LOG_DEST": "stdout"})
    logging.getLogger("etl.test").info("on stdout")
    captured = capsys.readouterr()
    assert "on stdout" in captured.out and captured.err == ""
    ol.configure({})
    logging.getLogger("etl.test").info("on stderr")
    captured = capsys.readouterr()
    assert "on stderr" in captured.err and captured.out == ""


def test_third_party_loggers_are_quietened_and_the_level_is_configurable():
    ol.configure({"ETL_LOG_LEVEL": "DEBUG"}, stream=io.StringIO())
    for name in ol.THIRD_PARTY:
        assert logging.getLogger(name).level == logging.WARNING
    ol.configure({"ETL_LOG_THIRD_PARTY_LEVEL": "error"}, stream=io.StringIO())
    assert logging.getLogger("great_expectations").level == logging.ERROR


def test_a_library_logging_through_the_standard_package_reaches_the_handler():
    out = _emit({"ETL_LOG_FORMAT": "json", "ETL_LOG_LEVEL": "INFO"})
    stream = io.StringIO()
    ol.configure({"ETL_LOG_FORMAT": "json"}, stream=stream)
    logging.getLogger("great_expectations.core").warning("from a library")
    logging.getLogger("great_expectations.core").info("quiet")
    lines = stream.getvalue().splitlines()
    assert out == "" and len(lines) == 1 and json.loads(lines[0])["message"] == "from a library"


def test_warnings_are_routed_into_the_logger_unless_disabled():
    original = warnings.showwarning
    stream = io.StringIO()
    ol.configure({"ETL_LOG_FORMAT": "json"}, stream=stream)
    with warnings.catch_warnings():
        warnings.simplefilter("always")
        warnings.warn("careful", UserWarning, stacklevel=1)
    record = json.loads(stream.getvalue().splitlines()[0])
    assert record["logger"] == "py.warnings" and "careful" in record["message"]
    ol.configure({"ETL_LOG_CAPTURE_WARNINGS": "0"}, stream=io.StringIO())
    assert warnings.showwarning is original  # capture off restores the standard hook


def test_configure_returns_the_settings_it_applied():
    assert ol.configure({"ETL_LOG_LEVEL": "error"}, stream=io.StringIO())["level"] == "ERROR"


def test_the_module_needs_only_the_standard_library():
    tree = ast.parse((Path(__file__).resolve().parents[1] / "obs_logging.py").read_text())
    imported = {
        (n.names[0].name if isinstance(n, ast.Import) else n.module).split(".")[0]
        for n in ast.walk(tree)
        if isinstance(n, ast.Import | ast.ImportFrom)
    }
    # mutmut's trampoline adds its own import to a mutated copy; it is not part of the module
    assert imported - {"mutmut"} <= set(sys.stdlib_module_names) | {"__future__"}


def test_non_ascii_text_is_kept_readable_in_json_and_in_files(tmp_path):
    out = _emit({"ETL_LOG_FORMAT": "json"}, (logging.INFO, "écart 42°", None))
    assert "écart 42°" in out
    target = tmp_path / "run.log"
    ol.configure({"ETL_LOG_DEST": "file", "ETL_LOG_FILE": str(target), "ETL_LOG_FORMAT": "json"})
    logging.getLogger("etl.test").info("écart")
    for handler in logging.getLogger().handlers:
        handler.flush()
    assert "écart" in target.read_bytes().decode("utf-8")


def test_the_file_handler_appends_and_the_message_formats_its_arguments(tmp_path):
    target = tmp_path / "run.log"
    env = {"ETL_LOG_DEST": "file", "ETL_LOG_FILE": str(target), "ETL_LOG_FORMAT": "json"}
    for number in (1, 2):
        ol.configure(env)
        logging.getLogger("etl.test").info("run %d", number)
    lines = [json.loads(line) for line in target.read_text().splitlines()]
    assert [line["message"] for line in lines] == ["run 1", "run 2"]
