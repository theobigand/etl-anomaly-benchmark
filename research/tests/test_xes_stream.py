"""Exact tests of the bounded streaming XES reader."""

import gzip
import hashlib
import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import xes_stream as xs  # noqa: E402


def _trace(case, events, extra=""):
    body = "".join(
        f'<event><string key="concept:name" value="{a}"/>'
        f'<date key="time:timestamp" value="2020-01-0{i + 1}T10:00:00.000+01:00"/>{x}</event>'
        for i, (a, x) in enumerate(events)
    )
    name = "" if case is None else f'<string key="concept:name" value="{case}"/>'
    return f"<trace>{name}{extra}{body}</trace>"


def _log(*traces, ns=False, close=True):
    head = '<log xes.version="1.0"' + (' xmlns="http://www.xes-standard.org/"' if ns else "") + ">"
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        + head
        + "".join(traces)
        + ("</log>" if close else "")
    ).encode()


def _read(data, **kw):
    return xs.read_traces(io.BytesIO(data), **kw)


def test_complete_traces_keep_case_order_event_attributes_and_trace_attributes():
    data = _log(
        _trace("c1", [("A", '<float key="amount" value="5.5"/><string key="org:resource" value="r"/>'), ("B", "")],  # noqa: E501
               extra='<int key="rank" value="3"/>'),
        _trace("c2", [("A", '<boolean key="ok" value="true"/>')]),
    )  # fmt: skip
    result = _read(data)
    assert [t["case"] for t in result.traces] == ["c1", "c2"]
    first = result.traces[0]
    assert first["attributes"] == {"concept:name": "c1", "rank": 3}
    assert first["events"][0] == {
        "concept:name": "A", "time:timestamp": "2020-01-01T10:00:00.000+01:00", "amount": 5.5, "org:resource": "r",  # noqa: E501
    }  # fmt: skip
    assert [e["concept:name"] for e in first["events"]] == ["A", "B"]  # log order
    assert result.traces[1]["events"][0]["ok"] is True
    assert result.status == {
        "stream_complete": True, "stop": "log_closed", "bytes_in": len(data), "bytes_out": len(data),  # noqa: E501
        "traces_seen": 2, "traces_kept": 2, "traces_without_case": 0, "modulo": 1,
    }  # fmt: skip


def test_namespaced_logs_are_read_like_plain_ones():
    result = _read(_log(_trace("c1", [("A", "")]), ns=True))
    assert [t["case"] for t in result.traces] == ["c1"] and result.status["stream_complete"] is True


def test_a_log_that_is_cut_inside_a_trace_keeps_only_the_complete_traces_and_says_so():
    full = _log(
        _trace("c1", [("A", "")]), _trace("c2", [("A", ""), ("B", "")]), _trace("c3", [("A", "")])
    )
    cut = full[: full.index(b"c3") + 20]  # inside the third trace
    result = _read(cut)
    assert [t["case"] for t in result.traces] == ["c1", "c2"]
    assert (
        result.status["stream_complete"] is False
        and result.status["stop"] == "input_ended_before_log_closed"
    )
    assert result.status["traces_seen"] == 2 and result.status["bytes_in"] == len(cut)
    open_log = _read(_log(_trace("c1", [("A", "")]), close=False))
    assert open_log.status["stop"] == "input_ended_before_log_closed" and len(open_log.traces) == 1


def test_a_truncated_gzip_stream_yields_the_traces_decoded_before_the_cut():
    traces = [_trace(f"c{i}", [("A", ""), ("B", "")]) for i in range(400)]
    blob = gzip.compress(_log(*traces))
    result = _read(blob[: len(blob) // 2], compressed=True)
    assert 0 < len(result.traces) < 400 and result.status["stream_complete"] is False
    assert [t["case"] for t in result.traces] == [
        f"c{i}" for i in range(len(result.traces))
    ]  # a clean prefix
    assert result.status["stop"] == "input_ended_before_log_closed"
    whole = _read(blob, compressed=True)
    assert len(whole.traces) == 400 and whole.status["stream_complete"] is True
    assert whole.status["bytes_in"] == len(blob) and whole.status["bytes_out"] > len(blob)


def test_selection_by_case_hash_is_deterministic_and_counts_what_it_skips():
    data = _log(*[_trace(f"case{i}", [("A", "")]) for i in range(30)])
    a = _read(data, modulo=3)
    b = _read(data, modulo=3)
    want = [
        f"case{i}"
        for i in range(30)
        if int(hashlib.sha256(f"case{i}".encode()).hexdigest(), 16) % 3 == 0
    ]
    assert [t["case"] for t in a.traces] == want == [t["case"] for t in b.traces]
    assert (
        a.status["traces_seen"] == 30
        and a.status["traces_kept"] == len(want)
        and a.status["modulo"] == 3
    )


def test_traces_without_a_case_identifier_are_counted_and_never_kept():
    result = _read(_log(_trace(None, [("A", "")]), _trace("c2", [("A", "")])))
    assert [t["case"] for t in result.traces] == ["c2"]
    assert result.status["traces_without_case"] == 1 and result.status["traces_seen"] == 2


def test_events_without_timestamps_or_with_malformed_values_are_kept_as_read_or_rejected():
    no_time = '<trace><string key="concept:name" value="c"/><event><string key="concept:name" value="A"/></event></trace>'  # noqa: E501
    result = _read(_log(no_time))
    assert result.traces[0]["events"] == [{"concept:name": "A"}]  # a missing time stays missing
    bad = '<trace><string key="concept:name" value="c"/><event><int key="n" value="x"/></event></trace>'  # noqa: E501
    with pytest.raises(xs.XesError, match="int attribute 'n'"):
        _read(_log(bad))


def test_invalid_unsafe_and_oversized_inputs_are_refused_with_explicit_errors():
    with pytest.raises(xs.XesError, match="not well-formed XML"):
        _read(b"<log><trace></log>")
    with pytest.raises(xs.XesError, match="not XML"):
        _read(b"plain text without any tag at all")
    with pytest.raises(xs.XesError, match="DOCTYPE"):
        _read(b'<?xml version="1.0"?><!DOCTYPE log [<!ENTITY a "b">]><log/>')
    with pytest.raises(xs.XesError, match="ENTITY"):
        _read(b'<log><!ENTITY x "y"></log>')
    with pytest.raises(xs.XesError, match="not a readable gzip stream"):
        _read(b"definitely not gzip, but long enough to be read as a stream", compressed=True)


def test_the_input_and_output_limits_stop_reading_and_mark_the_stream_incomplete():
    data = gzip.compress(_log(*[_trace(f"c{i}", [("A", "")]) for i in range(2000)]))
    by_input = _read(data, compressed=True, max_in=len(data) // 4)
    assert (
        by_input.status["stop"] == "input_limit"
        and by_input.status["bytes_in"] <= len(data) // 4 + xs.CHUNK
    )
    assert 0 < len(by_input.traces) < 2000 and by_input.status["stream_complete"] is False
    by_output = _read(data, compressed=True, max_out=20_000)
    assert (
        by_output.status["stop"] == "output_limit"
        and by_output.status["bytes_out"] <= 20_000 + xs.CHUNK
    )
    by_traces = _read(data, compressed=True, max_traces=5)
    assert len(by_traces.traces) == 5 and by_traces.status["stop"] == "trace_limit"
    assert by_traces.status["stream_complete"] is False and by_traces.status["traces_kept"] == 5


def test_the_reader_does_not_keep_finished_traces_in_the_parser_tree():
    data = _log(*[_trace(f"c{i}", [("A", "")] * 3) for i in range(3000)])
    assert len(data) > 4 * xs.CHUNK
    result = _read(data)
    assert len(result.traces) == 3000 and result.status["traces_kept"] == 3000
    assert result.max_open_children < 1500  # finished traces are detached chunk by chunk


def test_error_messages_are_exact_and_name_the_offending_attribute_or_construct():
    with pytest.raises(xs.XesError) as error:
        _read(b'<?xml version="1.0"?><!DOCTYPE log [<!ENTITY a "b">]><log/>')
    assert str(error.value) == "DOCTYPE declarations are not accepted"
    with pytest.raises(xs.XesError) as error:
        _read(b'<log><!ENTITY x "y"></log>')
    assert str(error.value) == "ENTITY declarations are not accepted"
    bad_trace_attribute = (
        '<trace><int key="rank" value="x"/><string key="concept:name" value="c"/></trace>'
    )
    with pytest.raises(xs.XesError) as error:
        _read(_log(bad_trace_attribute))
    assert str(error.value) == "int attribute 'rank' has the unreadable value 'x'"
    bad_event = '<trace><string key="concept:name" value="c"/><event><float key="amt" value="1,5"/></event></trace>'  # noqa: E501
    with pytest.raises(xs.XesError) as error:
        _read(_log(bad_event))
    assert str(error.value) == "float attribute 'amt' has the unreadable value '1,5'"


def test_a_raw_zlib_stream_is_not_accepted_as_gzip_and_only_gzip_is():
    import zlib

    data = _log(_trace("c1", [("A", "")]))
    assert _read(gzip.compress(data), compressed=True).status["stream_complete"] is True
    with pytest.raises(xs.XesError, match="not a readable gzip stream"):
        _read(zlib.compress(data), compressed=True)


def test_the_limits_are_exact_at_the_boundary_and_the_counters_add_up_over_many_chunks():
    data = _log(*[_trace(f"c{i}", [("A", ""), ("B", "")]) for i in range(1500)])
    assert len(data) > 3 * xs.CHUNK
    whole = _read(data)
    assert whole.status["bytes_in"] == len(data) == whole.status["bytes_out"]
    exact = _read(data, max_in=len(data))
    assert (
        exact.status["stop"] == "log_closed" and exact.status["traces_kept"] == 1500
    )  # the limit equals the size
    short = _read(data, max_in=len(data) - 1)
    assert short.status["stop"] == "input_limit" and short.status["bytes_in"] == len(data) - 1
    assert short.status["stream_complete"] is False
    just_in = _read(data, max_in=2 * xs.CHUNK)
    assert just_in.status["bytes_in"] == 2 * xs.CHUNK and just_in.status["stop"] == "input_limit"


def test_a_declaration_split_across_two_chunks_is_still_refused():
    prefix = b'<?xml version="1.0"?>'
    filler = b" " * (xs.CHUNK - len(prefix) - 4)
    data = (
        prefix + filler + b"<!DOCTYPE log []><log/>"
    )  # the marker straddles the first chunk boundary
    assert data.index(b"<!DOCTYPE") < xs.CHUNK < data.index(b"<!DOCTYPE") + 9
    with pytest.raises(xs.XesError, match="DOCTYPE"):
        _read(data)
    entity = prefix + filler + b'<log><!ENTITY a "b"></log>'
    with pytest.raises(xs.XesError, match="ENTITY"):
        _read(entity)


def test_leading_whitespace_does_not_hide_that_a_document_is_xml_and_text_is_not():
    with pytest.raises(xs.XesError, match="not well-formed XML"):
        _read(b"   \n  <log><trace></log>")
    with pytest.raises(xs.XesError, match="not XML"):
        _read(b"   plain text   ")
    with pytest.raises(xs.XesError, match="not XML"):
        _read(b"text first <log/>")


def test_attributes_are_read_only_at_the_event_and_trace_level_not_from_nested_containers():
    nested = (
        '<trace><string key="concept:name" value="c"/><list key="tr"><string key="deep_trace" value="x"/></list>'  # noqa: E501
        '<event><string key="concept:name" value="A"/><list key="ev"><string key="deep_event" value="y"/></list>'  # noqa: E501
        "</event></trace>"
    )
    result = _read(_log(nested))
    trace = result.traces[0]
    assert trace["attributes"] == {"concept:name": "c"}
    assert trace["events"] == [{"concept:name": "A"}]


def test_a_trace_attribute_that_follows_the_events_and_an_event_outside_a_trace_are_handled():
    late = (
        '<trace><string key="concept:name" value="c"/><event><string key="concept:name" value="A"/></event>'  # noqa: E501
        '<int key="late" value="4"/></trace>'
    )
    result = _read(_log(late))
    assert result.traces[0]["attributes"] == {"concept:name": "c", "late": 4}
    assert result.traces[0]["events"] == [{"concept:name": "A"}]
    stray = '<log><event><string key="concept:name" value="x"/></event><trace><string key="concept:name" value="c"/></trace></log>'  # noqa: E501
    assert [t["case"] for t in _read(stray.encode()).traces] == ["c"]


def test_the_root_element_is_released_so_that_traces_never_pile_up_across_chunks():
    data = _log(*[_trace(f"c{i}", [("A", "")]) for i in range(9000)])
    result = _read(data)
    per_chunk = xs.CHUNK // len(_trace("c0000", [("A", "")]))
    assert 0 < result.max_open_children <= 2 * per_chunk and len(result.traces) == 9000


def test_a_cut_log_whose_size_equals_the_input_limit_ends_as_input_ended_not_as_limit():
    full = _log(_trace("c1", [("A", "")]), _trace("c2", [("A", "")]))
    cut = full[: full.index(b"c2") + 5]
    result = _read(cut, max_in=len(cut))
    assert (
        result.status["stop"] == "input_ended_before_log_closed"
    )  # nothing more to read at the limit
    assert result.status["bytes_in"] == len(cut) and [t["case"] for t in result.traces] == ["c1"]
    limited = _read(cut + b"x", max_in=len(cut))
    assert limited.status["stop"] == "input_limit"  # one more byte exists beyond the limit
    assert limited.traces and limited.status["stream_complete"] is False


def test_an_error_after_the_first_chunk_is_still_reported_as_malformed_xml_not_as_text():
    data = b"<log>" + b"a" * xs.CHUNK + b"</wrong>"
    with pytest.raises(xs.XesError, match="not well-formed XML"):
        _read(data)


def test_global_definitions_and_extensions_before_the_traces_are_not_traces():
    head = (
        '<extension name="Concept" prefix="concept" uri="http://example.org/c"/>'
        '<global scope="trace"><string key="concept:name" value="default"/></global>'
        '<global scope="event"><string key="concept:name" value="default"/></global>'
        '<classifier name="act" keys="concept:name"/>'
    )
    data = _log(head, _trace("c1", [("A", "")]), _trace("c2", [("A", ""), ("B", "")]))
    result = _read(data)
    assert [t["case"] for t in result.traces] == ["c1", "c2"]
    assert result.status["traces_seen"] == 2 and result.status["traces_without_case"] == 0
    assert [len(t["events"]) for t in result.traces] == [1, 2]
