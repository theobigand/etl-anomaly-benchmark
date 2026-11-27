"""obs_tracing against the real OpenTelemetry SDK with an in-memory exporter (#161).

Runs in a container (platform/otel_check.sh) where the optional dependency group is installed;
the governed environment does not install it. No dataset is read and no detector runs.
"""

import sys
import time
from pathlib import Path

import pytest
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "research"))
import obs_events as oe  # noqa: E402
import obs_tracing as ot  # noqa: E402

EXPORTER = InMemorySpanExporter()
trace.set_tracer_provider(TracerProvider())
trace.get_tracer_provider().add_span_processor(SimpleSpanProcessor(EXPORTER))


@pytest.fixture(autouse=True)
def clear():
    EXPORTER.clear()


def test_the_api_is_found_and_tracing_is_enabled():
    assert ot.enabled() is True


def test_spans_nest_with_the_right_parents_and_one_trace():
    with ot.span("outer", protocol="P-TAB"), ot.span("inner", units=3):
        pass
    inner, outer = EXPORTER.get_finished_spans()
    assert (outer.name, inner.name) == ("outer", "inner")
    assert inner.parent.span_id == outer.context.span_id and outer.parent is None
    assert inner.context.trace_id == outer.context.trace_id
    assert dict(outer.attributes) == {"protocol": "P-TAB"} and dict(inner.attributes) == {
        "units": 3
    }


def test_an_error_sets_the_error_status_and_a_scrubbed_exception_event():
    with pytest.raises(ValueError), ot.span("work"):
        raise ValueError("cannot reach postgres://bob:s3cret@db/x")
    (span,) = EXPORTER.get_finished_spans()
    assert span.status.status_code == StatusCode.ERROR and span.status.description == "ValueError"
    (event,) = span.events
    assert event.name == "exception"
    assert "s3cret" not in event.attributes["exception.message"]
    assert "[REDACTED]" in event.attributes["exception.message"]


def test_a_clean_span_is_unset_not_error():
    with ot.span("fine"):
        pass
    assert EXPORTER.get_finished_spans()[0].status.status_code == StatusCode.UNSET


def test_the_trace_id_bound_in_the_logs_is_the_trace_id_of_the_span():
    with ot.span("x") as current:
        assert oe.current()["trace_id"] == format(current.get_span_context().trace_id, "032x")
    assert "trace_id" not in oe.current()


def test_unsafe_attributes_are_dropped_and_counted():
    with ot.span("x", stage="load", ground_truth="a", note="token=abc"):
        pass
    attributes = dict(EXPORTER.get_finished_spans()[0].attributes)
    assert attributes == {"stage": "load", "dropped_attributes": 2}


def test_the_work_is_unchanged_and_fast_when_the_export_backend_is_down():
    provider = TracerProvider()
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint="http://127.0.0.1:9/v1/traces", timeout=1))
    )
    previous = trace.get_tracer_provider()
    ot.trace.get_tracer = provider.get_tracer
    try:
        started = time.monotonic()
        results = []
        for n in range(50):
            with ot.span("stage", n=n):
                results.append(n * n)
        elapsed = time.monotonic() - started
        assert results == [n * n for n in range(50)]
        assert elapsed < 1.0
        provider.shutdown()
    finally:
        ot.trace.get_tracer = previous.get_tracer
