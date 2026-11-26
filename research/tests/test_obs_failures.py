"""Failure taxonomy, bounded retries and visible failures (#158)."""

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

TRACE = "4bf92f3577b34da6a3ce929d0e0e4736"


@pytest.fixture(autouse=True)
def clean_logging():
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    yield
    for handler in [h for h in root.handlers if h not in handlers]:
        root.removeHandler(handler)
        handler.close()
    root.setLevel(level)


def _log():
    stream = io.StringIO()
    ol.configure({"ETL_LOG_FORMAT": "json"}, stream=stream)
    oe.attach()
    return logging.getLogger("etl.failures"), stream


def _records(stream):
    return [json.loads(line) for line in stream.getvalue().splitlines()]


class Flaky:
    """Fails with ``error`` for the first ``failures`` calls, then returns ``value``."""

    def __init__(self, failures, error=None, value="ok"):
        self.calls, self.failures, self.value = 0, failures, value
        self.error = error or ConnectionError("link down")

    def __call__(self):
        self.calls += 1
        if self.calls <= self.failures:
            raise self.error
        return self.value


POLICY = of.Policy(max_attempts=3, base_delay_s=0.5, max_delay_s=30.0, deadline_s=None)


def test_the_taxonomy_covers_the_seven_classes_with_distinct_non_zero_exit_codes():
    assert set(of.CLASSES) == {
        "infrastructure",
        "processing",
        "data_quality",
        "detector",
        "inapplicability",
        "injected",
        "unexpected",
    }
    codes = [of.CLASSES[name]["exit_code"] for name in of.CLASSES]
    assert len(set(codes)) == 7 and 0 not in codes
    assert all(of.CLASSES[n]["description"] for n in of.CLASSES)


@pytest.mark.parametrize(
    ("error", "failure_class", "transient"),
    [
        (ConnectionError("x"), "infrastructure", True),
        (TimeoutError("x"), "infrastructure", True),
        (InterruptedError("x"), "infrastructure", True),
        (FileNotFoundError("x"), "infrastructure", False),
        (PermissionError("x"), "infrastructure", False),
        (MemoryError(), "infrastructure", False),
        (of.InfrastructureFailure("x"), "infrastructure", True),
        (of.InfrastructureFailure("x", transient=False), "infrastructure", False),
        (of.ProcessingFailure("x"), "processing", False),
        (of.DataQualityFailure("x"), "data_quality", False),
        (of.DetectorFailure("x"), "detector", False),
        (of.InapplicableFailure("x"), "inapplicability", False),
        (of.InjectedFailure("x"), "injected", False),
        (ValueError("x"), "unexpected", False),
        (KeyError("x"), "unexpected", False),
        (RuntimeError("x"), "unexpected", False),
    ],
)
def test_classification_is_explicit_and_an_unknown_error_is_never_a_data_anomaly(
    error, failure_class, transient
):
    assert of.classify(error) == (failure_class, transient)


def test_a_wrapped_failure_keeps_its_cause_and_its_class():
    try:
        try:
            raise ConnectionError("root")
        except ConnectionError as cause:
            raise of.InfrastructureFailure("load failed") from cause
    except of.InfrastructureFailure as error:
        assert isinstance(error.__cause__, ConnectionError)
        assert of.classify(error) == ("infrastructure", True)


def test_a_transient_failure_is_retried_with_exponential_backoff_until_it_succeeds():
    log, stream = _log()
    delays = []
    task = Flaky(2)
    result = of.run_with_retries(
        task, stage="load", policy=POLICY, idempotent=True, logger=log, sleep=delays.append
    )
    assert result == "ok" and task.calls == 3 and delays == [0.5, 1.0]
    events = _records(stream)
    assert [e["event"] for e in events] == ["stage.retrying", "stage.retrying", "stage.completed"]
    assert [e["attempt"] for e in events] == [1, 2, 3]
    assert events[0]["delay_s"] == 0.5 and events[1]["delay_s"] == 1.0
    assert events[0]["failure_class"] == "infrastructure" and events[0]["transient"] is True
    assert events[0]["retry"] is True and events[0]["max_attempts"] == 3
    assert events[0]["level"] == "WARNING" and events[0]["stage"] == "load"
    assert events[2]["final_status"] == "recovered"


def test_a_first_attempt_success_logs_nothing():
    log, stream = _log()
    assert (
        of.run_with_retries(Flaky(0), stage="load", policy=POLICY, idempotent=True, logger=log)
        == "ok"
    )
    assert stream.getvalue() == ""


def test_retries_are_bounded_and_the_original_exception_is_raised_with_a_note():
    log, stream = _log()
    task = Flaky(10)
    with pytest.raises(ConnectionError, match="link down") as caught:
        of.run_with_retries(
            task, stage="load", policy=POLICY, idempotent=True, logger=log, sleep=lambda s: None
        )
    assert task.calls == 3
    assert caught.value.__notes__ == [
        "stage load failed after 3 attempts (infrastructure, exhausted)"
    ]
    events = _records(stream)
    assert [e["event"] for e in events] == ["stage.retrying", "stage.retrying", "stage.failed"]
    last = events[-1]
    assert last["level"] == "ERROR" and last["final_status"] == "exhausted"
    assert last["attempt"] == 3 and last["retry"] is False
    assert (last["stage"], last["max_attempts"]) == ("load", 3)
    assert last["exception"]["type"] == "ConnectionError"


def test_a_permanent_failure_is_not_retried():
    log, stream = _log()
    task = Flaky(10, error=of.DataQualityFailure("bad schema"))
    with pytest.raises(of.DataQualityFailure):
        of.run_with_retries(
            task, stage="validate", policy=POLICY, idempotent=True, logger=log, sleep=lambda s: None
        )
    assert task.calls == 1
    (event,) = _records(stream)
    assert event["event"] == "stage.failed" and event["final_status"] == "failed"
    assert event["failure_class"] == "data_quality" and event["transient"] is False


def test_an_unexpected_error_is_not_retried_and_is_labelled_unexpected():
    log, stream = _log()
    task = Flaky(10, error=ValueError("boom"))
    with pytest.raises(ValueError, match="boom"):
        of.run_with_retries(task, stage="score", policy=POLICY, idempotent=True, logger=log)
    (event,) = _records(stream)
    assert task.calls == 1 and event["failure_class"] == "unexpected"


def test_a_call_that_is_not_idempotent_is_never_retried():
    log, stream = _log()
    task = Flaky(1)
    with pytest.raises(ConnectionError):
        of.run_with_retries(task, stage="write", policy=POLICY, idempotent=False, logger=log)
    assert task.calls == 1
    (event,) = _records(stream)
    assert event["final_status"] == "failed" and event["transient"] is True


def test_the_delay_is_capped_and_a_deadline_stops_the_retries_early():
    log, _ = _log()
    delays = []
    capped = of.Policy(max_attempts=6, base_delay_s=4.0, max_delay_s=10.0, deadline_s=None)
    with pytest.raises(ConnectionError):
        of.run_with_retries(
            Flaky(10), stage="x", policy=capped, idempotent=True, logger=log, sleep=delays.append
        )
    assert delays == [4.0, 8.0, 10.0, 10.0, 10.0]
    clock = iter([100.0, 100.0, 105.5])
    delays.clear()
    bounded = of.Policy(max_attempts=10, base_delay_s=1.0, max_delay_s=30.0, deadline_s=6.0)
    task = Flaky(10)
    with pytest.raises(ConnectionError) as caught:
        of.run_with_retries(
            task,
            stage="x",
            policy=bounded,
            idempotent=True,
            logger=log,
            sleep=delays.append,
            clock=lambda: next(clock),
        )
    assert delays == [1.0] and task.calls == 2
    assert caught.value.__notes__[0].endswith("(infrastructure, deadline)")


def test_correlation_identifiers_reach_every_retry_and_failure_event():
    log, stream = _log()
    with oe.bind(scientific_run_id="run-7", trace_id=TRACE), pytest.raises(ConnectionError):
        of.run_with_retries(
            Flaky(10),
            stage="load",
            policy=POLICY,
            idempotent=True,
            logger=log,
            sleep=lambda s: None,
        )
    events = _records(stream)
    assert len(events) == 3
    assert all(e["scientific_run_id"] == "run-7" and e["trace_id"] == TRACE for e in events)


def test_a_failure_is_logged_once_however_many_layers_report_it():
    log, stream = _log()
    with pytest.raises(of.ProcessingFailure) as caught:
        of.run_with_retries(
            Flaky(1, error=of.ProcessingFailure("x")),
            stage="inner",
            policy=POLICY,
            idempotent=True,
            logger=log,
        )
    of.log_failure(log, "outer", caught.value)
    of.log_failure(log, "outermost", caught.value)
    assert len(_records(stream)) == 1


def test_log_failure_records_an_error_raised_outside_the_retry_helper():
    log, stream = _log()
    try:
        raise of.DetectorFailure("did not converge")
    except of.DetectorFailure as error:
        of.log_failure(log, "fit", error)
    (event,) = _records(stream)
    assert event["event"] == "stage.failed" and event["failure_class"] == "detector"
    assert event["final_status"] == "failed" and event["stage"] == "fit"
    assert event["exception"]["message"] == "did not converge"


def test_base_exceptions_are_never_swallowed_or_retried():
    log, stream = _log()
    task = Flaky(5, error=KeyboardInterrupt())
    with pytest.raises(KeyboardInterrupt):
        of.run_with_retries(task, stage="x", policy=POLICY, idempotent=True, logger=log)
    assert task.calls == 1 and stream.getvalue() == ""


def test_the_policy_comes_from_the_environment_and_refuses_invalid_values():
    assert of.policy({}) == of.Policy(3, 0.5, 30.0, None)
    chosen = of.policy(
        {
            "ETL_RETRY_MAX_ATTEMPTS": "5",
            "ETL_RETRY_BASE_DELAY_S": "2",
            "ETL_RETRY_MAX_DELAY_S": "60",
            "ETL_RETRY_DEADLINE_S": "120",
        }
    )
    assert chosen == of.Policy(5, 2.0, 60.0, 120.0)
    for env, message in (
        (
            {"ETL_RETRY_MAX_ATTEMPTS": "0"},
            "^ETL_RETRY_MAX_ATTEMPTS must be an integer of at least 1; got '0'$",
        ),
        (
            {"ETL_RETRY_MAX_ATTEMPTS": "x"},
            "^ETL_RETRY_MAX_ATTEMPTS must be an integer of at least 1; got 'x'$",
        ),
        (
            {"ETL_RETRY_BASE_DELAY_S": "-1"},
            "^ETL_RETRY_BASE_DELAY_S must be a number greater than 0; got '-1'$",
        ),
        (
            {"ETL_RETRY_BASE_DELAY_S": "nan"},
            "ETL_RETRY_BASE_DELAY_S must be a number greater than 0",
        ),
        (
            {"ETL_RETRY_BASE_DELAY_S": "inf"},
            "ETL_RETRY_BASE_DELAY_S must be a number greater than 0",
        ),
        ({"ETL_RETRY_MAX_DELAY_S": "0"}, "ETL_RETRY_MAX_DELAY_S must be a number greater than 0"),
        ({"ETL_RETRY_DEADLINE_S": "0"}, "ETL_RETRY_DEADLINE_S must be a number greater than 0"),
        (
            {"ETL_RETRY_BASE_DELAY_S": "5", "ETL_RETRY_MAX_DELAY_S": "1"},
            "ETL_RETRY_MAX_DELAY_S must not be below ETL_RETRY_BASE_DELAY_S",
        ),
    ):
        with pytest.raises(ValueError, match=message):
            of.policy(env)


def test_run_guarded_returns_zero_on_success_and_the_class_exit_code_on_failure():
    log, stream = _log()
    assert of.run_guarded(lambda: None, stage="run", logger=log) == 0
    assert stream.getvalue() == ""
    cases = [
        (of.DataQualityFailure("x"), 65),
        (ConnectionError("x"), 75),
        (ValueError("x"), 70),
        (of.InapplicableFailure("x"), of.CLASSES["inapplicability"]["exit_code"]),
    ]
    for error, code in cases:

        def task(error=error):
            raise error

        assert of.run_guarded(task, stage="run", logger=log) == code
    events = _records(stream)
    assert len(events) == 4 and all(e["event"] == "run.failed" for e in events)
    assert events[0]["failure_class"] == "data_quality" and events[0]["level"] == "ERROR"
    assert (
        events[0]["final_status"] == "failed"
        and events[0]["exception"]["type"] == "DataQualityFailure"
    )


def test_run_guarded_does_not_log_a_failure_the_inner_layer_already_logged():
    log, stream = _log()

    def task():
        of.run_with_retries(
            Flaky(10, error=of.ProcessingFailure("x")),
            stage="inner",
            policy=POLICY,
            idempotent=True,
            logger=log,
        )

    assert of.run_guarded(task, stage="run", logger=log) == of.CLASSES["processing"]["exit_code"]
    assert [e["event"] for e in _records(stream)] == ["stage.failed"]


def test_run_guarded_lets_the_exit_signals_through_and_returns_integer_results():
    log, _ = _log()
    assert of.run_guarded(lambda: 3, stage="run", logger=log) == 3
    for signal_error in (KeyboardInterrupt, SystemExit):

        def task(signal_error=signal_error):
            raise signal_error()

        with pytest.raises(signal_error):
            of.run_guarded(task, stage="run", logger=log)


def test_the_new_event_names_are_registered_in_the_schema():
    assert oe.EVENTS["stage.retrying"][0] == "WARNING"
    assert oe.EVENTS["run.failed"][0] == "ERROR"


def test_an_infrastructure_failure_keeps_its_message():
    assert str(of.InfrastructureFailure("link down")) == "link down"


def test_the_policy_accepts_its_minimums_and_refuses_text_that_is_not_a_number():
    chosen = of.policy(
        {
            "ETL_RETRY_MAX_ATTEMPTS": "1",
            "ETL_RETRY_BASE_DELAY_S": "2",
            "ETL_RETRY_MAX_DELAY_S": "2",
        }
    )
    assert chosen == of.Policy(1, 2.0, 2.0, None)
    with pytest.raises(
        ValueError, match="^ETL_RETRY_BASE_DELAY_S must be a number greater than 0; got 'abc'$"
    ):
        of.policy({"ETL_RETRY_BASE_DELAY_S": "abc"})
    with pytest.raises(
        ValueError, match="^ETL_RETRY_MAX_DELAY_S must not be below ETL_RETRY_BASE_DELAY_S$"
    ):
        of.policy({"ETL_RETRY_BASE_DELAY_S": "5", "ETL_RETRY_MAX_DELAY_S": "1"})


def test_log_failure_defaults_to_a_single_attempt():
    log, stream = _log()
    of.log_failure(log, "fit", of.DetectorFailure("x"))
    (event,) = _records(stream)
    assert (event["attempt"], event["max_attempts"]) == (1, 1)


def test_a_deadline_that_is_met_exactly_still_allows_the_retry():
    log, _ = _log()
    delays = []
    policy = of.Policy(max_attempts=3, base_delay_s=1.0, max_delay_s=30.0, deadline_s=3.0)
    clock = iter([100.0, 100.0, 101.0])
    with pytest.raises(ConnectionError):
        of.run_with_retries(
            Flaky(10),
            stage="x",
            policy=policy,
            idempotent=True,
            logger=log,
            sleep=delays.append,
            clock=lambda: next(clock),
        )
    assert delays == [1.0, 2.0]


def test_the_terminal_event_names_the_stage_and_the_attempt_limit_and_the_note_counts():
    log, stream = _log()
    with pytest.raises(of.DataQualityFailure) as caught:
        of.run_with_retries(
            Flaky(1, error=of.DataQualityFailure("x")),
            stage="validate",
            policy=POLICY,
            idempotent=True,
            logger=log,
        )
    assert caught.value.__notes__ == [
        "stage validate failed after 1 attempt (data_quality, failed)"
    ]
    (event,) = _records(stream)
    assert (event["stage"], event["attempt"], event["max_attempts"]) == ("validate", 1, 3)


def test_a_recovery_after_one_retry_is_reported_with_its_stage_and_limits():
    log, stream = _log()
    of.run_with_retries(
        Flaky(1), stage="load", policy=POLICY, idempotent=True, logger=log, sleep=lambda s: None
    )
    retry, done = _records(stream)
    assert done["event"] == "stage.completed" and done["attempt"] == 2
    assert (done["stage"], done["max_attempts"], done["final_status"]) == ("load", 3, "recovered")
    assert retry["event"] == "stage.retrying"


def test_run_guarded_names_its_stage_in_the_failure_event():
    log, stream = _log()
    of.run_guarded(lambda: 1 / 0, stage="nightly", logger=log)
    (event,) = _records(stream)
    assert event["stage"] == "nightly" and event["failure_class"] == "unexpected"
