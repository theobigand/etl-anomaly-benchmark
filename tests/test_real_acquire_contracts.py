"""Exact limits, messages, report fields and call arguments of the public-dataset acquisition."""

import io
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest

from tests.test_real_acquire import (
    CARDIO,
    CREDIT,
    MANIFEST,
    ROOT,
    WATER,
    _cardio_writer,
    _opener,
    _payloads,
    _sha,
    _sources,
)
from verification import real_acquire as ra


def _acquire(destination, **overrides):
    arguments = dict(
        open_url=_opener(_payloads()), fetch_cardio=_cardio_writer(), limit=ra.MAX_BYTES
    )
    arguments.update(overrides)
    return ra.acquire(_sources(), MANIFEST, destination, **arguments)


def test_the_download_is_requested_with_the_limit_and_read_one_byte_past_it(tmp_path):
    seen, reads = [], []

    class Body(io.BytesIO):
        def read(self, size=-1):
            reads.append(size)
            return super().read(size)

    def open_url(url, limit):
        seen.append((url, limit))
        return Body(_payloads()[url])

    _acquire(tmp_path, open_url=open_url, limit=1000)
    assert seen == [(url, 1000) for url, _ in _sources().values()]
    assert reads == [1001, 1001]


def test_a_download_of_exactly_the_limit_is_kept_and_one_byte_more_is_refused(tmp_path):
    exact = len(CREDIT)
    only = {"credit_card": _sources()["credit_card"]}
    report = ra.acquire(
        only, MANIFEST, tmp_path, open_url=_opener(_payloads()), fetch_cardio=_cardio_writer(),
        limit=exact,
    )  # fmt: skip
    assert report["datasets"]["credit_card"]["bytes"] == exact
    with pytest.raises(ra.AcquisitionError) as refused:
        ra.acquire(
            only, MANIFEST, tmp_path / "again", open_url=_opener(_payloads()),
            fetch_cardio=_cardio_writer(), limit=exact - 1,
        )  # fmt: skip
    assert str(refused.value) == f"credit_card: the download is larger than {exact - 1} bytes"


def test_the_destination_is_created_with_its_parents_and_may_already_exist(tmp_path):
    nested = tmp_path / "a" / "b"
    _acquire(nested)
    assert (nested / "cardio.csv").is_file()
    (nested / "creditcard.csv").unlink()
    (nested / "water_quality.csv").unlink()
    (nested / "cardio.csv").unlink()
    _acquire(nested)


def test_an_existing_file_is_refused_by_name_before_anything_is_downloaded(tmp_path):
    (tmp_path / "creditcard.csv").write_bytes(b"old")
    with pytest.raises(ra.AcquisitionError) as refused:
        _acquire(tmp_path, open_url=lambda *a: pytest.fail("downloaded"))
    assert str(refused.value) == "credit_card: creditcard.csv already exists and is not overwritten"
    clean = tmp_path / "clean"
    clean.mkdir()
    (clean / "cardio.csv").write_bytes(b"old")
    with pytest.raises(ra.AcquisitionError) as refused:
        _acquire(clean)
    assert str(refused.value) == "cardio: cardio.csv already exists and is not overwritten"


def test_a_conversion_that_produces_nothing_is_refused_with_the_exact_reason(tmp_path):
    with pytest.raises(ra.AcquisitionError) as refused:
        _acquire(tmp_path, fetch_cardio=lambda destination: None)
    assert str(refused.value) == "cardio: the rebuilt file differs from the reference checksum"
    assert not (tmp_path / "cardio.csv").exists()


def test_a_wrong_download_and_a_wrong_url_state_their_exact_reason(tmp_path):
    payloads = {**_payloads(), "https://storage.googleapis.com/c.csv": b"tampered"}
    with pytest.raises(ra.AcquisitionError) as refused:
        _acquire(tmp_path, open_url=_opener(payloads))
    assert str(refused.value) == "credit_card: the download differs from the reference checksum"
    with pytest.raises(ra.AcquisitionError) as refused:
        ra.acquire({"x": ("http://example.com/a", "a.csv")}, MANIFEST, tmp_path / "z")
    assert str(refused.value) == (
        "x: http://example.com/a is not allowed (https and a listed host only)"
    )


def test_the_report_has_exact_field_names_for_every_dataset(tmp_path):
    report = _acquire(tmp_path)
    assert report == {
        "method": "public-download",
        "datasets": {
            "credit_card": {
                "url": "https://storage.googleapis.com/c.csv",
                "sha256": _sha(CREDIT),
                "bytes": len(CREDIT),
            },
            "water_quality": {
                "url": "https://raw.githubusercontent.com/x/y",
                "sha256": _sha(WATER),
                "bytes": len(WATER),
            },
            "cardio": {
                "url": MANIFEST["cardio"]["source_url"],
                "sha256": _sha(CARDIO),
                "bytes": len(CARDIO),
            },
        },
    }


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://storage.googleapis.com/x", True),
        ("https://raw.githubusercontent.com/x", True),
        ("http://storage.googleapis.com/x", False),
        ("https://example.com/x", False),
        ("https://user@storage.googleapis.com/x", False),
        ("https://storage.googleapis.com@evil.example/x", False),
    ],
)
def test_only_https_urls_on_a_listed_host_without_credentials_are_allowed(url, expected):
    assert ra.allowed(url) is expected


def test_the_request_carries_the_user_agent_and_a_sixty_second_timeout():
    seen = {}

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    class Opener:
        def open(self, request, timeout=None):
            seen.update(request=request, timeout=timeout)
            return Response(b"abcdef")

    body = ra.open_url("https://storage.googleapis.com/x", 3, Opener())
    assert body.read() == b"abcd"
    assert seen["timeout"] == 60
    assert seen["request"].full_url == "https://storage.googleapis.com/x"
    assert seen["request"].get_header("User-agent") == "etl-benchmark-verification"


def test_a_redirect_is_resolved_against_the_current_url_and_forwarded_unchanged(monkeypatch):
    calls = []
    monkeypatch.setattr(
        urllib.request.HTTPRedirectHandler,
        "redirect_request",
        lambda self, *args: calls.append(args) or "next",
    )
    request = urllib.request.Request("https://storage.googleapis.com/a/b")
    handler = ra.GuardedRedirects()
    out = handler.redirect_request(request, "fp", 302, "Found", {"h": 1}, "/c")
    assert out == "next"
    assert calls == [(request, "fp", 302, "Found", {"h": 1}, "https://storage.googleapis.com/c")]


def test_the_cardio_script_runs_with_the_current_interpreter_from_the_repository(monkeypatch):
    seen = {}
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: seen.update(args=a, kwargs=k))
    ra.run_fetch_cardio(Path("anywhere"))
    assert seen["args"] == ([sys.executable, str(ROOT / "experiments" / "fetch_cardio.py")],)
    assert seen["kwargs"] == {"check": True, "capture_output": True, "cwd": ROOT}


def test_the_command_routes_its_arguments_and_reports_what_it_acquired(
    tmp_path, monkeypatch, capsys
):
    seen = {}

    def fake(sources, manifest, destination):
        seen.update(sources=sources, manifest=manifest, destination=destination)
        return {"method": "public-download", "datasets": {"b": {}, "a": {}}}

    monkeypatch.setattr(ra, "acquire", fake)
    out = tmp_path / "o" / "report.json"
    out.parent.mkdir()
    assert ra.main(["--destination", str(tmp_path / "d"), "--output", str(out)]) == 0
    assert seen["sources"] is ra.SOURCES
    assert seen["manifest"] == json.loads(ra.MANIFEST.read_text())["datasets"]
    assert seen["destination"] == tmp_path / "d" and isinstance(seen["destination"], Path)
    assert capsys.readouterr().out == ("acquired a, b; every checksum matches the manifest\n")
    document = {"method": "public-download", "datasets": {"b": {}, "a": {}}}
    assert out.read_text() == json.dumps(document, indent=2, sort_keys=True) + "\n"
    ra.main(["--output", str(out)])
    assert seen["destination"] == ra.DATA


@pytest.mark.parametrize("error", [OSError("disk"), subprocess.CalledProcessError(2, "x")])
def test_operating_system_and_conversion_failures_are_refusals_not_crashes(
    tmp_path, monkeypatch, capsys, error
):
    def fail(*args):
        raise error

    monkeypatch.setattr(ra, "acquire", fail)
    assert ra.main(["--output", str(tmp_path / "r.json")]) == 1
    assert capsys.readouterr().out.startswith("refused: ")
    assert not (tmp_path / "r.json").exists()


def test_the_output_is_required_and_the_help_is_the_module_description(capsys):
    with pytest.raises(SystemExit) as stop:
        ra.main([])
    assert stop.value.code == 2
    with pytest.raises(SystemExit):
        ra.main(["--help"])
    assert "Fetch the three research datasets" in " ".join(capsys.readouterr().out.split())
