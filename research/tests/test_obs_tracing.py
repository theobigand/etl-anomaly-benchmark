"""Optional, failure-proof tracing (#161): the wrapper logic against a recording fake of the API.

The real OpenTelemetry SDK with an in-memory exporter is exercised by platform/tests (run in a
container by platform/otel_check.sh), because the SDK is an optional dependency that the governed
environment does not install.
"""

import io
import json
import logging
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import obs_events as oe  # noqa: E402
import obs_logging as ol  # noqa: E402
import obs_tracing as ot  # noqa: E402


class Context:
    def __init__(self, trace_id, valid=True):
        self.trace_id, self.is_valid = trace_id, valid


class Span:
    def __init__(self, name, parent, trace_id):
        self.name, self.parent = name, parent
        self.attributes, self.events, self.status = {}, [], None
        self.context = Context(trace_id)
        self.broken = set()

    def _check(self, what):
        if what in self.broken:
            raise RuntimeError(f"{what} broke")

    def set_attributes(self, values):
        self._check("set_attributes")
        self.attributes.update(values)

    def set_attribute(self, key, value):
        self.attributes[key] = value

    def get_span_context(self):
        self._check("get_span_context")
        return self.context

    def add_event(self, name, attributes):
        self._check("add_event")
        self.events.append((name, attributes))

    def set_status(self, status):
        self.status = status


class Fake:
    """Stands in for ``opentelemetry.trace``: a tracer whose spans nest like the real ones."""

    def __init__(self):
        self.spans, self.stack, self.broken = [], [], set()
        self.options, self.exits = [], []

    def get_tracer(self, scope):
        self.scope = scope
        return self

    def start_as_current_span(self, name, **options):
        if "start" in self.broken:
            raise RuntimeError("start broke")
        self.options.append(options)
        parent = self.stack[-1] if self.stack else None
        span = Span(name, parent, parent.context.trace_id if parent else 0xABC)
        span.broken = self.broken
        self.spans.append(span)
        return Manager(self, span)


class Manager:
    def __init__(self, api, span):
        self.api, self.span = api, span

    def __enter__(self):
        self.api.stack.append(self.span)
        return self.span

    def __exit__(self, kind, error, tb):
        self.api.stack.pop()
        self.api.exits.append((kind, error, tb))
        if "end" in self.api.broken:
            raise RuntimeError("end broke")
        return False


@pytest.fixture
def fake(monkeypatch):
    api = Fake()
    monkeypatch.setattr(ot, "trace", api)
    monkeypatch.setattr(ot, "Status", lambda code, text: (code, text))
    monkeypatch.setattr(ot, "StatusCode", type("C", (), {"ERROR": "ERROR"}))
    monkeypatch.setattr(ot, "_warned", set())
    return api


@pytest.fixture(autouse=True)
def clean_logging():
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    yield
    for handler in [h for h in root.handlers if h not in handlers]:
        root.removeHandler(handler)
    root.setLevel(level)


def test_without_the_api_the_span_does_nothing_and_the_block_runs(monkeypatch):
    monkeypatch.setattr(ot, "trace", None)
    ran = []
    with ot.span("x", a=1) as current:
        ran.append(current)
    assert ran == [None] and ot.enabled() is False


def test_the_module_imports_and_is_disabled_when_the_package_is_absent():
    assert ot.enabled() is False  # the governed environment does not install the optional group


def test_spans_nest_and_carry_their_attributes(fake):
    with ot.span("outer", protocol="P-TAB", faults=3), ot.span("inner", units=7):
        pass
    outer, inner = fake.spans
    assert inner.parent is outer and outer.parent is None
    assert outer.attributes == {"protocol": "P-TAB", "faults": 3}
    assert inner.attributes == {"units": 7}
    assert fake.scope == "etl.platform"
    assert fake.options == [{"record_exception": False, "set_status_on_exception": False}] * 2


def test_the_trace_id_is_bound_for_the_block_and_released_after(fake):
    with ot.span("outer") as current:
        assert oe.current()["trace_id"] == format(0xABC, "032x")
        with ot.span("inner"):
            assert oe.current()["trace_id"] == format(0xABC, "032x")
        assert current is fake.spans[0]
    assert "trace_id" not in oe.current()


def test_log_lines_inside_the_span_carry_the_trace_id(fake):
    stream = io.StringIO()
    ol.configure({"ETL_LOG_FORMAT": "json"}, stream=stream)
    oe.attach()
    with ot.span("work"):
        oe.emit(logging.getLogger("etl.t"), "stage.completed", stage="x")
    assert json.loads(stream.getvalue())["trace_id"] == format(0xABC, "032x")


def test_an_invalid_span_context_binds_no_trace_id(fake):
    original = fake.start_as_current_span

    def invalid(name, **options):
        manager = original(name, **options)
        manager.span.context = Context(0, valid=False)
        return manager

    fake.start_as_current_span = invalid
    with ot.span("x"):
        assert "trace_id" not in oe.current()


def test_an_error_is_marked_on_the_span_with_a_scrubbed_event_and_reraised_unchanged(fake):
    error = ValueError("cannot reach postgres://bob:s3cret@db/x")
    with pytest.raises(ValueError) as caught, ot.span("work"):
        raise error
    assert caught.value is error
    (span,) = fake.spans
    assert span.status == ("ERROR", "ValueError")
    ((name, attributes),) = span.events
    assert name == "exception" and attributes["exception.type"] == "ValueError"
    assert attributes["exception.message"] == (
        "ValueError: cannot reach postgres://[REDACTED]@db/x"
    )


def test_only_the_failing_span_and_its_parents_are_marked(fake):
    with pytest.raises(RuntimeError), ot.span("outer"):
        with ot.span("inner"):
            pass
        with ot.span("failing"):
            raise RuntimeError("x")
    outer, inner, failing = fake.spans
    assert inner.status is None and failing.status and outer.status


def test_a_baseexception_is_not_swallowed(fake):
    with pytest.raises(KeyboardInterrupt), ot.span("x"):
        raise KeyboardInterrupt
    assert fake.spans[0].status == ("ERROR", "KeyboardInterrupt")


def test_attributes_with_ground_truth_names_secrets_or_non_scalar_values_are_dropped_and_counted(
    fake,
):
    with ot.span("x", stage="load", ground_truth="yes", note="token=abc", rows=[1], ok=True):
        pass
    attributes = fake.spans[0].attributes
    assert attributes == {"stage": "load", "ok": True, "dropped_attributes": 3}


def test_long_text_is_cut_and_a_clean_span_has_no_drop_count(fake):
    with ot.span("x", stage="s" * 600):
        pass
    assert fake.spans[0].attributes == {"stage": "s" * 500}


def test_clean_returns_the_kept_attributes_and_the_drop_count():
    assert ot.clean({"a": 1, "b": b"x", "c": "y_true"}) == ({"a": 1}, 2)


@pytest.mark.parametrize("broken", ["start", "set_attributes", "get_span_context", "end"])
def test_a_telemetry_failure_never_changes_the_outcome_of_the_work(fake, caplog, broken):
    fake.broken.add(broken)
    ran = []
    with ot.span("x"):
        ran.append(1)
    assert ran == [1]
    assert any("tracing" in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize("broken", ["add_event", "end"])
def test_a_telemetry_failure_while_recording_an_error_keeps_the_original_exception(fake, broken):
    fake.broken.add(broken)
    with pytest.raises(ValueError, match="real"), ot.span("x"):
        raise ValueError("real")


def test_a_telemetry_failure_is_reported_once_per_kind(fake, caplog):
    fake.broken.add("set_attributes")
    for _ in range(3):
        with ot.span("x"):
            pass
    assert len([r for r in caplog.records if "attributes" in r.getMessage()]) == 1


def test_the_warning_is_scrubbed_and_names_the_failed_step(fake, caplog):
    fake.broken.add("start")
    with ot.span("x"):
        pass
    (record,) = caplog.records
    assert record.getMessage() == "tracing start failed and is ignored: RuntimeError: start broke"


def test_the_engine_stages_are_traced_without_changing_their_result(fake):
    import unit_runner as ur

    run = ur.execute(ur.fixture("P-TAB", 0), 2, 0)
    assert run == _untraced(ur)
    execute, inject, check = fake.spans
    assert (execute.name, inject.name, check.name) == (
        "unit_runner.execute",
        "unit_runner.inject",
        "unit_runner.check",
    )
    assert inject.parent is execute and check.parent is execute
    assert execute.attributes == {"protocol": "P-TAB", "faults": 2}
    assert check.attributes == {"units": run.units}


def _untraced(ur):
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(ot, "trace", None)
        return ur.execute(ur.fixture("P-TAB", 0), 2, 0)


def test_a_broken_contract_marks_the_execute_span_as_failed(fake, monkeypatch):
    import obs_failures as of
    import unit_runner as ur

    runner = ur.RUNNERS["P-TAB"]

    def sloppy(data, k, seed):
        out, rows = runner.inject(data, k, seed)
        out = out.copy()
        out.loc[out.index[0], "amount"] = -1.0
        return out, rows

    monkeypatch.setitem(ur.RUNNERS, "P-TAB", ur.Runner(**{**runner.__dict__, "inject": sloppy}))
    with pytest.raises(of.ProcessingFailure):
        ur.execute(ur.fixture("P-TAB", 0), 2, 0)
    assert fake.spans[0].status == ("ERROR", "ProcessingFailure")


def test_the_manager_is_closed_with_the_exception_it_received_and_with_nothing_on_success(fake):
    error = ValueError("v")
    with pytest.raises(ValueError), ot.span("bad"):
        raise error
    with ot.span("good"):
        pass
    (kind, seen, tb), good = fake.exits
    assert kind is ValueError and seen is error and tb is not None
    assert good == (None, None, None)


@pytest.mark.parametrize(
    ("broken", "kind"), [("get_span_context", "attributes"), ("end", "end"), ("start", "start")]
)
def test_each_failed_step_is_named_in_its_warning(fake, caplog, broken, kind):
    fake.broken.add(broken)
    with ot.span("x"):
        pass
    assert [r.getMessage() for r in caplog.records] == [
        f"tracing {kind} failed and is ignored: RuntimeError: {broken} broke"
    ]


def test_a_failure_while_marking_the_error_is_named_and_the_error_is_kept(fake, caplog):
    fake.broken.add("add_event")
    with pytest.raises(ValueError), ot.span("x"):
        raise ValueError("real")
    assert [r.getMessage() for r in caplog.records] == [
        "tracing error status failed and is ignored: RuntimeError: add_event broke"
    ]
