"""Bounded streaming reader for XES event logs (plain or gzip), used by the acquisition views.

Input is read sequentially in fixed chunks and fed to an incremental XML parser. Only complete
``<trace>`` elements are returned, in log order, and each finished trace is detached from the parser
tree so memory does not grow with the document. Reading stops at the end of the log, at an input,
decompressed-output or trace limit, or where the source ends. The status says which, so a prefix
is never presented as a complete log; a selection by case-name hash is deterministic but is not a
random sample of the log (it inherits the order and coverage of the prefix).

Document type declarations and entity declarations are refused, as the Python documentation
recommends for XML from outside the program.
"""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET  # noqa: S405 - DOCTYPE and ENTITY declarations are refused
import zlib
from dataclasses import dataclass, field
from typing import Any, BinaryIO

CHUNK = 65_536
MAX_IN = 2 * 1024**3
MAX_OUT = 8 * 1024**3
_TYPED = {"string", "date", "int", "float", "boolean", "id"}
_CONVERT = {"int": int, "float": float, "boolean": lambda v: v == "true"}


class XesError(Exception):
    """The input is not a readable, safe XES document."""


@dataclass
class XesResult:
    traces: list[dict[str, Any]] = field(default_factory=list)
    status: dict[str, Any] = field(default_factory=dict)
    max_open_children: int = 0


def _local(tag: str) -> str:
    return tag.rpartition("}")[2]


def _value(kind: str, key: str, text: str) -> Any:
    try:
        return _CONVERT.get(kind, str)(text)
    except ValueError as error:
        raise XesError(f"{kind} attribute {key!r} has the unreadable value {text!r}") from error


def _decoded(decoder: Any, raw: bytes) -> list[bytes]:
    """Decompress ``raw`` in pieces of at most one chunk, whatever the compression ratio."""
    pieces, pending = [], raw
    while pending:
        pieces.append(decoder.decompress(pending, CHUNK))
        pending = decoder.unconsumed_tail
    return pieces


def read_traces(
    stream: BinaryIO,
    compressed: bool = False,
    modulo: int = 1,
    max_in: int = MAX_IN,
    max_out: int = MAX_OUT,
    max_traces: int | None = None,
) -> XesResult:
    """Complete traces of an XES log from a binary stream, with a status of how reading ended."""
    decoder = zlib.decompressobj(wbits=31) if compressed else None
    parser = ET.XMLPullParser(events=("start", "end"))
    result = XesResult()
    seen = without_case = 0
    bytes_in = bytes_out = depth = trace_depth = event_depth = 0
    root = trace = event = None
    stop, tail, started = None, b"", None
    while stop is None:
        if bytes_in >= max_in:
            stop = "input_limit" if stream.read(1) else None
            if stop is None:
                break
            continue
        raw = stream.read(min(CHUNK, max_in - bytes_in))
        if not raw:
            break
        bytes_in += len(raw)
        try:
            pieces = _decoded(decoder, raw) if decoder else [raw]
        except zlib.error as error:
            raise XesError(f"not a readable gzip stream ({error})") from error
        for data in pieces:
            bytes_out += len(data)
            window = tail + data
            if b"<!DOCTYPE" in window:
                raise XesError("DOCTYPE declarations are not accepted")
            if b"<!ENTITY" in window:
                raise XesError("ENTITY declarations are not accepted")
            tail = window[-16:]
            if started is None and data.strip():
                started = data.lstrip().startswith(b"<")  # does it look like XML at all
            try:
                parser.feed(data)
                events = list(parser.read_events())
            except ET.ParseError as error:
                raise XesError(
                    f"not well-formed XML ({error})" if started else f"not XML ({error})"
                ) from error
            for kind, node in events:
                name = _local(node.tag)
                if kind == "start":
                    depth += 1
                    if depth == 1:
                        root = node
                    elif name == "trace" and trace is None:
                        trace, trace_depth = {"attributes": {}, "events": []}, depth
                    elif name == "event" and trace is not None and event is None:
                        event, event_depth = {}, depth
                    continue
                depth -= 1
                if name in _TYPED and event is not None and depth == event_depth:
                    event[node.get("key")] = _value(name, node.get("key"), node.get("value"))
                elif (
                    name in _TYPED and trace is not None and event is None and depth == trace_depth
                ):
                    trace["attributes"][node.get("key")] = _value(
                        name, node.get("key"), node.get("value")
                    )
                elif name == "event" and event is not None and depth == trace_depth:
                    trace["events"].append(event)
                    event = None
                elif name == "trace" and trace is not None and depth == trace_depth - 1:
                    seen += 1
                    case = trace["attributes"].get("concept:name")
                    if case is None:
                        without_case += 1
                    elif int(hashlib.sha256(str(case).encode()).hexdigest(), 16) % modulo == 0:
                        result.traces.append({"case": case, **trace})
                    trace = None
                    if root is not None:
                        root.remove(node)  # detach the finished trace from the tree
                        result.max_open_children = max(result.max_open_children, len(root))
                    if max_traces is not None and len(result.traces) >= max_traces:
                        stop = "trace_limit"
                elif name == "log" and depth == 0:
                    stop = "log_closed"
                if stop:
                    break
            if stop:
                break
            if bytes_out > max_out:
                stop = "output_limit"
                break
    if stop is None:
        stop = "input_ended_before_log_closed"
    result.status = {
        "stream_complete": stop == "log_closed",
        "stop": stop,
        "bytes_in": bytes_in,
        "bytes_out": bytes_out,
        "traces_seen": seen,
        "traces_kept": len(result.traces),
        "traces_without_case": without_case,
        "modulo": modulo,
    }
    return result
