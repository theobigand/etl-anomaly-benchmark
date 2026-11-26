"""Allowlist-first fields, secret redaction and ground-truth isolation for logs (#159)."""

import io
import json
import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import obs_events as oe  # noqa: E402
import obs_failures as of  # noqa: E402
import obs_logging as ol  # noqa: E402
import obs_redaction as orr  # noqa: E402


@pytest.fixture(autouse=True)
def clean_logging():
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    yield
    for handler in [h for h in root.handlers if h not in handlers]:
        root.removeHandler(handler)
        handler.close()
    root.setLevel(level)


def _logged(*calls):
    stream = io.StringIO()
    ol.configure({"ETL_LOG_FORMAT": "json"}, stream=stream)
    oe.attach()
    orr.attach()
    log = logging.getLogger("etl.redact")
    for call in calls:
        call(log)
    return [json.loads(line) for line in stream.getvalue().splitlines()]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("password=hunter2 next", "password=[REDACTED] next"),
        ("API_KEY: abc123", "API_KEY=[REDACTED]"),
        ("token = xyz", "token=[REDACTED]"),
        ("Authorization: Bearer abc.def-1", "Authorization=[REDACTED]"),
        ("sent Bearer abc.def-1 ok", "sent [REDACTED] ok"),
        ("db at postgres://bob:s3cret@host:5432/x", "db at postgres://[REDACTED]@host:5432/x"),
        ("key AKIAABCDEFGHIJKLMNOP end", "key [REDACTED] end"),
        ("tok ghp_" + "a" * 36 + " end", "tok [REDACTED] end"),
    ],
)
def test_secrets_are_replaced_and_the_rest_of_the_text_is_kept(text, expected):
    assert orr.scrub(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("loaded ground_truth file", "loaded [REDACTED] file"),
        ("Ground-Truth ok", "[REDACTED] ok"),
        ("y_true shape", "[REDACTED] shape"),
        ("wrote labels now", "wrote [REDACTED] now"),
        ("the label is", "the [REDACTED] is"),
        ("injected 12 faults", "[REDACTED] 12 faults"),
        ("held-out split and holdout", "[REDACTED] split and [REDACTED]"),
        ("data/injection/mask.parquet", "data/[REDACTED]/mask.parquet"),
        ("is_anomaly column", "[REDACTED] column"),
    ],
)
def test_ground_truth_vocabulary_is_replaced_in_text_and_paths(text, expected):
    assert orr.scrub(text) == expected


def test_words_that_only_contain_the_vocabulary_are_not_touched():
    assert orr.scrub("labelled tables and a labeler") == "labelled tables and a labeler"
    assert orr.scrub("plain message") == "plain message"


def test_only_allowlisted_fields_reach_the_log_and_the_rest_is_counted():
    (record,) = _logged(
        lambda log: log.info(
            "stage done",
            extra={"stage": "load", "rows": 12, "user_email": "x@y", "raw_row": {"a": 1}},
        )
    )
    assert record["stage"] == "load" and record["rows"] == 12
    assert "user_email" not in record and "raw_row" not in record
    assert record["dropped_fields"] == 2


def test_no_field_is_reported_as_dropped_when_none_was():
    (record,) = _logged(lambda log: log.info("x", extra={"stage": "load"}))
    assert "dropped_fields" not in record


def test_a_field_with_a_non_scalar_value_is_dropped_even_when_its_name_is_allowed():
    (record,) = _logged(
        lambda log: log.info("x", extra={"stage": ["a", "b"], "rows": b"bytes", "code": 0})
    )
    assert record["code"] == 0 and "stage" not in record and "rows" not in record
    assert record["dropped_fields"] == 2


def test_booleans_floats_and_none_are_kept():
    (record,) = _logged(
        lambda log: log.info("x", extra={"retry": True, "duration_ms": 1.5, "code": None})
    )
    assert (record["retry"], record["duration_ms"], record["code"]) == (True, 1.5, None)


def test_string_values_are_scrubbed_and_long_values_are_cut():
    (record,) = _logged(
        lambda log: log.info("x", extra={"stage": "token=abc123", "failure_class": "f" * 600})
    )
    assert record["stage"] == "token=[REDACTED]"
    assert record["failure_class"] == "f" * 500 + "..."
    (exact,) = _logged(lambda log: log.info("x", extra={"failure_class": "f" * 500}))
    assert exact["failure_class"] == "f" * 500


def test_the_message_is_scrubbed_after_its_arguments_are_formatted():
    (record,) = _logged(lambda log: log.info("login %s", "password=hunter2"))
    assert record["message"] == "login password=[REDACTED]"


def test_the_correlation_identifiers_and_event_fields_pass_the_allowlist():
    log_calls = []
    with oe.bind(scientific_run_id="run-7", trace_id="4bf92f3577b34da6a3ce929d0e0e4736"):
        log_calls.append(lambda log: oe.emit(log, "stage.completed", stage="load", rows=3))
        (record,) = _logged(*log_calls)
    assert record["scientific_run_id"] == "run-7" and record["event"] == "stage.completed"
    assert record["schema_version"] == 1 and record["trace_id"].startswith("4bf9")
    assert "dropped_fields" not in record


def test_an_exception_message_is_scrubbed_and_keeps_its_type_and_stack():
    def fail(log):
        try:
            raise ConnectionError("cannot reach postgres://bob:s3cret@db/x")
        except ConnectionError:
            log.exception("failed")

    (record,) = _logged(fail)
    assert record["exception"]["type"] == "ConnectionError"
    assert record["exception"]["message"] == "cannot reach postgres://[REDACTED]@db/x"
    assert (
        "s3cret" not in record["exception"]["stack"] and "Traceback" in record["exception"]["stack"]
    )


def test_a_record_without_an_exception_is_left_without_one():
    (record,) = _logged(lambda log: log.info("x"))
    assert "exception" not in record


def test_attach_is_idempotent_and_leaves_foreign_handlers_alone():
    root = logging.getLogger()
    foreign = logging.NullHandler()
    root.addHandler(foreign)
    try:
        ol.configure({}, stream=io.StringIO())
        for _ in range(3):
            orr.attach()
        (ours,) = [h for h in root.handlers if getattr(h, ol.MARK, False)]
        assert sum(isinstance(f, orr.RedactionFilter) for f in ours.filters) == 1
        assert foreign.filters == []
    finally:
        root.removeHandler(foreign)


def test_the_filter_runs_after_the_correlation_filter_whatever_the_attach_order():
    ol.configure({}, stream=io.StringIO())
    orr.attach()
    oe.attach()
    (ours,) = [h for h in logging.getLogger().handlers if getattr(h, ol.MARK, False)]
    kinds = [type(f) for f in ours.filters]
    assert kinds.index(oe.CorrelationFilter) < kinds.index(orr.RedactionFilter)


def test_the_leakage_audit_finds_names_paths_attributes_and_ids_that_reveal_ground_truth():
    findings = orr.audit(
        {
            "event": "fault.injected",
            "ground_truth_path": "x",
            "stage": "load",
            "artifact_id": "labels-v2",
            "path": "data/holdout/x.csv",
            "note": "token=abc",
        }
    )
    assert findings == [
        "event: 'fault.injected' names a ground-truth concept",
        "ground_truth_path: field name names a ground-truth concept",
        "artifact_id: 'labels-v2' names a ground-truth concept",
        "path: 'data/holdout/x.csv' names a ground-truth concept",
        "note: 'token=abc' contains a secret",
    ]
    assert orr.audit({"event": "stage.completed", "stage": "load", "rows": 3}) == []


def test_the_platform_vocabulary_reveals_nothing_about_ground_truth():
    assert orr.audit_vocabulary() == []
    assert orr.audit_vocabulary(events=["run.started", "fault.injected"], identifiers=["x"]) == [
        "event 'fault.injected' names a ground-truth concept"
    ]
    assert orr.audit_vocabulary(events=[], identifiers=["label_id"]) == [
        "identifier 'label_id' names a ground-truth concept"
    ]


def test_every_allowlisted_name_passes_its_own_audit():
    assert [n for n in sorted(orr.ALLOWED) if orr.GROUND_TRUTH_NAME.search(n)] == []


def test_an_exception_flag_outside_an_exception_and_a_stack_are_handled():
    (record,) = _logged(lambda log: log.error("x", exc_info=True))
    assert "exception" not in record
    entry = logging.LogRecord("n", logging.INFO, "p", 1, "m", None, None)
    entry.stack_info = "frame token=abc"
    orr.RedactionFilter().filter(entry)
    assert entry.stack_info == "frame token=[REDACTED]"


def test_a_scrubbed_stack_has_no_trailing_newline():
    def fail(log):
        try:
            raise ValueError("boom")
        except ValueError:
            log.exception("failed")

    (record,) = _logged(fail)
    assert record["exception"]["stack"].endswith("ValueError: boom")


@pytest.mark.parametrize(
    "word", ["ground_truth", "y_true", "is_anomaly", "fault_mask", "injected", "held-out", "labels"]
)
def test_no_ground_truth_word_survives_in_any_part_of_the_json_line(word):
    def fail(log):
        try:
            raise RuntimeError(f"bad {word}")
        except RuntimeError:
            log.exception(f"failed {word}", extra={"stage": f"s {word}", word: 1})

    out = io.StringIO()
    ol.configure({"ETL_LOG_FORMAT": "json"}, stream=out)
    oe.attach()
    orr.attach()
    with oe.bind(artifact_id=f"a-{word}".replace("_", "-").replace("held-out", "heldout")):
        fail(logging.getLogger("etl.leak"))
        oe.emit(logging.getLogger("etl.leak"), "stage.completed", stage=f"path/{word}/x")
    assert not orr.GROUND_TRUTH.search(out.getvalue()), out.getvalue()


def test_the_retry_and_failure_events_of_obs_failures_pass_the_allowlist_whole():
    attempts = []

    def flaky():
        attempts.append(1)
        if len(attempts) < 3:
            raise ConnectionError("link down")

    stream = io.StringIO()
    ol.configure({"ETL_LOG_FORMAT": "json"}, stream=stream)
    oe.attach()
    orr.attach()
    log = logging.getLogger("etl.retry")
    policy = of.Policy(3, 0.5, 30.0, None)
    of.run_with_retries(
        flaky, stage="load", policy=policy, idempotent=True, logger=log, sleep=lambda s: None
    )
    with pytest.raises(ConnectionError):
        of.run_with_retries(
            lambda: (_ for _ in ()).throw(ConnectionError("x")),
            stage="load",
            policy=of.Policy(2, 0.5, 30.0, None),
            idempotent=True,
            logger=log,
            sleep=lambda s: None,
        )
    records = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert [r["event"] for r in records][:3] == [
        "stage.retrying",
        "stage.retrying",
        "stage.completed",
    ]
    assert all("dropped_fields" not in r for r in records)
    assert records[0]["delay_s"] == 0.5 and records[0]["transient"] is True
