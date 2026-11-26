import hashlib
import json
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import acquisition as aq  # noqa: E402

SPEC = {
    "id": "demo",
    "licence_class": "open",
    "hosts": ["example.org"],
    "min_interval": 0.0,
    "retries": 2,
    "max_bytes": 100,
}


def test_a_fetch_is_snapshotted_with_checksum_times_and_never_overwritten(tmp_path):
    calls = []

    def opener(url, limit):
        calls.append(url)
        return b'{"a": 1}'

    snap = aq.Snapshot(tmp_path, SPEC, "2026-11-21", opener=opener, sleep=lambda s: None)
    entry = snap.fetch("https://example.org/x.json", "x.json", observed="2026-11-20")
    assert entry["sha256"] == hashlib.sha256(b'{"a": 1}').hexdigest()
    assert entry["observed"] == "2026-11-20" and entry["collected"]
    assert (tmp_path / "demo" / "2026-11-21" / "raw" / "x.json").read_bytes() == b'{"a": 1}'
    again = snap.fetch("https://example.org/x.json", "x.json", observed="2026-11-20")
    assert again == entry and len(calls) == 1  # idempotent: a stored file is not fetched again
    manifest = json.loads((tmp_path / "demo" / "2026-11-21" / "manifest.json").read_text())
    assert [f["name"] for f in manifest["files"]] == ["x.json"]
    other = aq.Snapshot(tmp_path, SPEC, "2026-11-22", opener=opener, sleep=lambda s: None)
    other.fetch("https://example.org/x.json", "x.json", observed=None)
    assert (tmp_path / "demo" / "2026-11-21").exists()  # a new snapshot never touches the old one


def test_disallowed_hosts_oversized_bodies_and_restricted_sources_are_refused(tmp_path):
    snap = aq.Snapshot(tmp_path, SPEC, "s", opener=lambda u, n: b"x", sleep=lambda s: None)
    with pytest.raises(aq.AcquisitionError, match="host"):
        snap.fetch("https://evil.net/x", "x", observed=None)
    with pytest.raises(aq.AcquisitionError, match="https"):
        snap.fetch("http://example.org/x", "x", observed=None)
    big = aq.Snapshot(tmp_path, SPEC, "t", opener=lambda u, n: b"x" * 101, sleep=lambda s: None)
    with pytest.raises(aq.AcquisitionError, match="larger"):
        big.fetch("https://example.org/x", "x", observed=None)
    for klass in ("unclear", "restricted"):
        with pytest.raises(aq.AcquisitionError, match="licence"):
            aq.Snapshot(tmp_path, {**SPEC, "licence_class": klass}, "s")
    with pytest.raises(aq.AcquisitionError, match="name"):
        snap.fetch("https://example.org/x", "../escape", observed=None)


def test_transient_failures_are_retried_a_bounded_number_of_times_with_the_interval_kept(tmp_path):
    waits, attempts = [], []

    def flaky(url, limit):
        attempts.append(1)
        if len(attempts) < 3:
            raise OSError("boom")
        return b"ok"

    spec = {**SPEC, "min_interval": 1.5, "retries": 2}
    snap = aq.Snapshot(tmp_path, spec, "s", opener=flaky, sleep=waits.append)
    assert snap.fetch("https://example.org/a", "a", observed=None)["bytes"] == 2
    assert len(attempts) == 3 and all(w >= 1.5 for w in waits) and len(waits) >= 2
    dead = aq.Snapshot(
        tmp_path,
        spec,
        "u",
        opener=lambda u, n: 1 / 0 if False else (_ for _ in ()).throw(OSError("x")),
        sleep=waits.append,
    )
    with pytest.raises(aq.AcquisitionError, match="after 3 attempts"):
        dead.fetch("https://example.org/b", "b", observed=None)


def test_pages_stop_at_the_page_budget_or_when_a_page_is_empty(tmp_path):
    pages = {0: [1, 2], 1: [3], 2: []}
    got = list(aq.paginate(lambda i: pages.get(i, []), max_pages=5))
    assert got == [[1, 2], [3]]
    assert len(list(aq.paginate(lambda i: [i], max_pages=3))) == 3


def test_a_changed_stored_file_is_detected_when_the_snapshot_is_verified(tmp_path):
    snap = aq.Snapshot(tmp_path, SPEC, "s", opener=lambda u, n: b"abc", sleep=lambda s: None)
    snap.fetch("https://example.org/a", "a", observed=None)
    assert snap.verify() == []
    (tmp_path / "demo" / "s" / "raw" / "a").write_bytes(b"abd")
    assert snap.verify() == ["a"]


def test_a_plan_lists_fixed_files_then_numbered_pages():
    spec = {
        "files": [{"url": "https://example.org/f", "name": "f", "observed": None}],
        "pages": {
            "url": "https://example.org/p?skip={skip}&page={n1}",
            "name": "p{n}.json",
            "count": 2,
            "size": 100,
        },
    }
    got = aq.plan(spec)
    assert [r["name"] for r in got] == ["f", "p0.json", "p1.json"]
    assert got[2]["url"] == "https://example.org/p?skip=100&page=2"


def test_a_second_stage_requests_the_distinct_ids_found_in_the_first_stage_files(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "w0.json").write_text(
        json.dumps(
            {"results": [{"a": [{"id": "A2"}, {"id": "A1"}]}, {"a": [{"id": "A1"}, {"id": None}]}]}
        )
    )
    (raw / "w1.json").write_text(json.dumps({"results": [{"a": [{"id": "A3"}]}]}))
    stage = {
        "from": "w*.json",
        "path": "results.a.id",
        "batch": 2,
        "url": "https://example.org/e?ids={ids}",
        "name": "e{n}.json",
        "join": "|",
    }
    got = aq.expand(stage, raw)
    assert [r["name"] for r in got] == ["e0.json", "e1.json"]
    assert got[0]["url"] == "https://example.org/e?ids=A1|A2" and got[1]["url"].endswith("ids=A3")
    assert aq.expand({**stage, "path": "results.zzz"}, raw) == []


def test_short_ids_drop_the_url_prefix(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "w.json").write_text(
        json.dumps({"results": [{"id": "https://x.org/W2"}, {"id": "https://x.org/W1"}]})
    )
    stage = {"from": "w.json", "path": "results.id", "batch": 5, "url": "https://e.org/?i={ids}",
             "name": "e{n}", "join": "|", "short": True}  # fmt: skip
    assert aq.expand(stage, raw)[0]["url"] == "https://e.org/?i=W1|W2"


def test_explicit_page_numbers_replace_the_count():
    spec = {
        "pages": {
            "url": "https://e.org/?p={n1}",
            "name": "p{n}",
            "count": 99,
            "size": 1,
            "numbers": [7, 3],
        }
    }
    assert [r["url"] for r in aq.plan(spec)] == ["https://e.org/?p=8", "https://e.org/?p=4"]


# --- exact behaviour: manifests, retries, limits, paths, planning, expansion, command line --------


def test_the_manifest_and_the_stored_file_have_exactly_the_documented_content(tmp_path):
    calls = []

    def opener(url, limit):
        calls.append((url, limit))
        return b"abc"

    snap = aq.Snapshot(tmp_path, SPEC, "snap1", opener=opener, sleep=lambda s: None)
    entry = snap.fetch("https://example.org/a/b.json", "dir/b.json", observed="2024-01")
    assert calls == [("https://example.org/a/b.json", 100)]
    assert set(entry) == {"name", "url", "sha256", "bytes", "collected", "observed"}
    assert entry["name"] == "dir/b.json" and entry["url"] == "https://example.org/a/b.json"
    assert entry["bytes"] == 3 and entry["observed"] == "2024-01"
    assert entry["collected"].endswith("+00:00") and "T" in entry["collected"]
    manifest_path = tmp_path / "demo" / "snap1" / "manifest.json"
    text = manifest_path.read_text()
    manifest = json.loads(text)
    assert manifest == {"source": "demo", "snapshot": "snap1", "files": [entry]}
    assert text == json.dumps(manifest, indent=1, sort_keys=True) + "\n"
    assert (tmp_path / "demo" / "snap1" / "raw" / "dir" / "b.json").read_bytes() == b"abc"
    # a second file in the same directory and a second file in a new directory both work
    snap.fetch("https://example.org/c", "dir/c.json", observed=None)
    snap.fetch("https://example.org/d", "d.json", observed=None)
    assert [f["name"] for f in json.loads(manifest_path.read_text())["files"]] == [
        "dir/b.json",
        "dir/c.json",
        "d.json",
    ]


def test_directories_have_the_exact_documented_names(tmp_path):
    snap = aq.Snapshot(tmp_path, SPEC, "s9", opener=lambda u, n: b"x", sleep=lambda s: None)
    assert snap.raw == tmp_path / "demo" / "s9" / "raw"
    assert str(snap.manifest_path).endswith("demo/s9/manifest.json")
    assert snap.snapshot_id == "s9" and snap.directory == tmp_path / "demo" / "s9"
    snap.fetch("https://example.org/x", "x", observed=None)
    assert sorted(p.name for p in (tmp_path / "demo" / "s9").iterdir()) == ["manifest.json", "raw"]


def test_retries_back_off_exponentially_and_report_the_last_error(tmp_path):
    waits = []
    errors = [OSError("one"), OSError("two"), OSError("three")]

    def failing(url, limit):
        raise errors.pop(0)

    spec = {**SPEC, "min_interval": 1.0, "retries": 2}
    snap = aq.Snapshot(tmp_path, spec, "r", opener=failing, sleep=waits.append)
    with pytest.raises(aq.AcquisitionError) as info:
        snap.fetch("https://example.org/a", "a", observed=None)
    # pacing before each attempt (1.0) and then 2, 4, 8 after each failure
    assert waits == [1.0, 2.0, 1.0, 4.0, 1.0, 8.0]
    assert "three" in str(info.value) and "after 3 attempts" in str(info.value)
    assert "https://example.org/a" in str(info.value)


def test_a_body_exactly_at_the_limit_is_accepted_and_one_byte_more_is_not(tmp_path):
    at_limit = aq.Snapshot(
        tmp_path, SPEC, "a", opener=lambda u, n: b"x" * 100, sleep=lambda s: None
    )
    assert at_limit.fetch("https://example.org/x", "x", observed=None)["bytes"] == 100
    over = aq.Snapshot(tmp_path, SPEC, "b", opener=lambda u, n: b"x" * 101, sleep=lambda s: None)
    with pytest.raises(aq.AcquisitionError, match="larger than 100 bytes"):
        over.fetch("https://example.org/x", "x", observed=None)


def test_the_error_messages_name_the_url_the_host_and_the_file(tmp_path):
    snap = aq.Snapshot(tmp_path, SPEC, "m", opener=lambda u, n: b"x", sleep=lambda s: None)
    with pytest.raises(aq.AcquisitionError) as host:
        snap.fetch("https://evil.net/x", "x", observed=None)
    assert "https://evil.net/x" in str(host.value) and "demo" in str(host.value)
    with pytest.raises(aq.AcquisitionError) as scheme:
        snap.fetch("http://example.org/x", "x", observed=None)
    assert str(scheme.value) == "http://example.org/x: https only"
    with pytest.raises(aq.AcquisitionError) as name:
        snap.fetch("https://example.org/x", "a b", observed=None)
    assert "'a b'" in str(name.value)
    for bad in ("../x", "/abs", "a//b", ".hidden", "a/../b"):
        with pytest.raises(aq.AcquisitionError):
            snap.fetch("https://example.org/x", bad, observed=None)
    for good in ("a", "a.json", "a_b-c.1", "d/e/f.csv"):
        snap.fetch("https://example.org/x", good, observed=None)
    with pytest.raises(aq.AcquisitionError) as klass:
        aq.Snapshot(tmp_path, {**SPEC, "licence_class": "restricted"}, "s")
    assert str(klass.value) == "licence class 'restricted' is not collectable"
    for ok in ("open", "research_only"):
        aq.Snapshot(tmp_path, {**SPEC, "licence_class": ok}, "s")


def test_planning_keeps_every_field_of_fixed_files_and_pages():
    spec = {
        "files": [{"url": "https://e.org/f", "name": "f", "observed": "2024", "extra": 1}],
        "pages": {
            "url": "https://e.org/p?n={n}&n1={n1}&skip={skip}",
            "name": "p{n}.json",
            "count": 2,
            "size": 50,
            "observed": "2023",
        },
    }
    got = aq.plan(spec)
    assert got[0] == {"url": "https://e.org/f", "name": "f", "observed": "2024", "extra": 1}
    assert got[1] == {
        "url": "https://e.org/p?n=0&n1=1&skip=0",
        "name": "p0.json",
        "observed": "2023",
    }
    assert got[2] == {
        "url": "https://e.org/p?n=1&n1=2&skip=50",
        "name": "p1.json",
        "observed": "2023",
    }
    assert aq.plan({}) == []
    nopages = aq.plan({"pages": {"url": "https://e.org/{n}", "name": "{n}", "count": 1, "size": 1}})
    assert nopages[0]["observed"] is None
    numbers = {
        "url": "https://e.org/?p={n}",
        "name": "x{n}",
        "count": 9,
        "size": 10,
        "numbers": [4],
    }
    assert aq.plan({"pages": numbers})[0]["url"] == "https://e.org/?p=4"


def test_expansion_walks_lists_and_objects_and_keeps_observed(tmp_path):
    raw = tmp_path
    (raw / "a.json").write_text(
        json.dumps({"r": [{"x": [{"id": "https://h/A/2"}, {"id": "https://h/A/1"}]}]})
    )
    (raw / "b.json").write_text(json.dumps({"r": [{"x": {"id": "https://h/A/3"}}]}))
    stage = {
        "from": "*.json",
        "path": "r.x.id",
        "batch": 10,
        "url": "https://e.org/?i={ids}",
        "name": "e{n}",
        "join": ",",
        "observed": "2023",
    }
    full = aq.expand(stage, raw)
    assert full == [
        {
            "url": "https://e.org/?i=https://h/A/1,https://h/A/2,https://h/A/3",
            "name": "e0",
            "observed": "2023",
        }
    ]
    short = aq.expand({**stage, "short": True}, raw)
    assert short[0]["url"] == "https://e.org/?i=1,2,3"  # only the last path segment is kept
    assert (
        aq.expand({k: v for k, v in stage.items() if k != "observed"}, raw)[0]["observed"] is None
    )
    deep = tmp_path / "d"
    deep.mkdir()
    (deep / "a.json").write_text(json.dumps({"r": [{"x": [{"id": "a/b/c"}]}]}))
    assert aq.expand({**stage, "short": True}, deep)[0]["url"] == "https://e.org/?i=c"
    (deep / "a.json").write_text(json.dumps({"r": [1, None, {"x": None}, {"y": 1}]}))
    assert aq.expand(stage, deep) == []
    (deep / "a.json").write_text(json.dumps({"r": [{"x": [{"id": None}, {"id": "k"}]}]}))
    assert aq.expand(stage, deep)[0]["url"] == "https://e.org/?i=k"


def test_open_url_sends_the_user_agent_and_reads_at_most_limit_plus_one(monkeypatch):
    seen = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self, n):
            seen["read"] = n
            return b"data"

    def fake(request, timeout):
        seen["agent"] = request.get_header("User-agent")
        seen["url"] = request.full_url
        seen["timeout"] = timeout
        return Response()

    monkeypatch.setattr(aq, "_opener", lambda hosts, url: types.SimpleNamespace(open=fake))
    assert aq.open_url("https://example.org/z", 10) == b"data"
    assert seen == {
        "agent": aq.USER_AGENT,
        "url": "https://example.org/z",
        "timeout": 120,
        "read": 11,
    }
    assert aq.USER_AGENT == "etl-benchmark-acquisition (academic research)"


def test_the_command_line_fetches_pages_then_stages_and_reports_the_count(
    tmp_path, monkeypatch, capsys
):
    sources = tmp_path / "sources.json"
    spec = {
        **SPEC,
        "id": "cli",
        "files": [{"url": "https://example.org/f", "name": "f.json", "observed": None}],
        "pages": {"url": "https://example.org/p{n}", "name": "p{n}.json", "count": 1, "size": 1},
        "stages": [
            {
                "from": "p*.json",
                "path": "ids",
                "batch": 5,
                "url": "https://example.org/s?i={ids}",
                "name": "s{n}.json",
                "join": "|",
            }
        ],
    }
    sources.write_text(json.dumps({"sources": [spec, {**SPEC, "id": "other"}]}))
    monkeypatch.setattr(aq, "SOURCES", sources)
    monkeypatch.setattr(aq, "open_url", lambda url, limit: b'{"ids": ["a", "b"]}')
    real = aq.Snapshot.__init__

    def init(self, root, spec, snapshot_id, opener=aq.open_url, sleep=aq.time.sleep):
        real(
            self,
            root,
            spec,
            snapshot_id,
            opener=lambda u, n: b'{"ids": ["a", "b"]}',
            sleep=lambda s: None,
        )

    monkeypatch.setattr(aq.Snapshot, "__init__", init)
    assert aq.main(["cli", "--snapshot", "t1", "--root", str(tmp_path / "out")]) == 0
    assert capsys.readouterr().out == "cli/t1: 3 files, mismatches []\n"
    raw = tmp_path / "out" / "cli" / "t1" / "raw"
    assert sorted(p.name for p in raw.iterdir()) == ["f.json", "p0.json", "s0.json"]
    import pytest as _pytest

    with _pytest.raises(SystemExit):
        aq.main(["cli"])  # the snapshot id is required


def test_short_ids_without_a_slash_stay_whole(tmp_path):
    (tmp_path / "a.json").write_text(json.dumps({"r": [{"id": "A2"}, {"id": "A1"}]}))
    stage = {"from": "a.json", "path": "r.id", "batch": 9, "url": "https://e.org/?i={ids}",
             "name": "e{n}", "join": "|", "short": True}  # fmt: skip
    assert aq.expand(stage, tmp_path)[0]["url"] == "https://e.org/?i=A1|A2"


def test_the_command_line_keeps_observation_times_uses_its_default_root_and_adds_the_source_path(
    tmp_path, monkeypatch, capsys
):
    import sys

    spec = {
        **SPEC,
        "id": "cli2",
        "files": [{"url": "https://example.org/f", "name": "f.json", "observed": "2020-01"}],
        "pages": {
            "url": "https://example.org/p{n}",
            "name": "p{n}.json",
            "count": 1,
            "size": 1,
            "observed": "2021",
        },
        "stages": [
            {
                "from": "p*.json",
                "path": "ids",
                "batch": 5,
                "url": "https://example.org/s?i={ids}",
                "name": "s{n}.json",
                "join": "|",
                "observed": "2022",
            }
        ],
    }
    sources = tmp_path / "sources.json"
    sources.write_text(json.dumps({"sources": [spec]}))
    monkeypatch.setattr(aq, "SOURCES", sources)
    monkeypatch.setattr(aq, "DEFAULT_ROOT", tmp_path / "default")
    real = aq.Snapshot.__init__

    def init(self, root, spec, snapshot_id, opener=aq.open_url, sleep=aq.time.sleep):
        real(
            self,
            root,
            spec,
            snapshot_id,
            opener=lambda u, n: b'{"ids": ["z"]}',
            sleep=lambda s: None,
        )

    monkeypatch.setattr(aq.Snapshot, "__init__", init)
    before = list(sys.path)
    assert aq.main(["cli2", "--snapshot", "t"]) == 0
    assert sys.path[0].endswith("/src") and sys.path[1:] == before
    sys.path[:] = before
    manifest = json.loads((tmp_path / "default" / "cli2" / "t" / "manifest.json").read_text())
    observed = {f["name"]: f["observed"] for f in manifest["files"]}
    assert observed == {"f.json": "2020-01", "p0.json": "2021", "s0.json": "2022"}
    spec_without_stages = {k: v for k, v in spec.items() if k != "stages"}
    sources.write_text(json.dumps({"sources": [spec_without_stages]}))
    assert aq.main(["cli2", "--snapshot", "u", "--root", str(tmp_path / "other")]) == 0
    sys.path[:] = before
    assert "cli2/u: 2 files" in capsys.readouterr().out
    import pytest as _pytest

    with _pytest.raises(SystemExit):
        aq.main(["--help"])
    assert "Lightweight, reproducible acquisition" in capsys.readouterr().out


# --- bounded range acquisition and gzip prefixes ------------------------------------------------

RANGE_SPEC = {**SPEC, "max_bytes": 50}


def _partial(start, body, total, status=206):
    end = start + len(body) - 1
    return {"status": status, "content_range": f"bytes {start}-{end}/{total}", "body": body}


def test_a_range_fetch_stores_the_fragment_with_its_exact_range_and_the_source_size(tmp_path):
    calls = []

    def range_opener(url, start, length):
        calls.append((url, start, length))
        return _partial(start, b"x" * length, 1000)

    snap = aq.Snapshot(tmp_path, RANGE_SPEC, "r", range_opener=range_opener, sleep=lambda s: None)
    entry = snap.fetch_range(
        "https://example.org/big.gz", "head.gz", start=0, length=40, observed="2024"
    )
    assert calls == [("https://example.org/big.gz", 0, 40)]
    assert entry["partial"] is True and entry["range"] == [0, 39] and entry["total_bytes"] == 1000
    assert entry["bytes"] == 40 and entry["sha256"] == hashlib.sha256(b"x" * 40).hexdigest()
    assert (
        entry["observed"] == "2024"
        and entry["name"] == "head.gz"
        and entry["url"].endswith("big.gz")
    )
    assert (tmp_path / "demo" / "r" / "raw" / "head.gz").read_bytes() == b"x" * 40
    manifest = json.loads((tmp_path / "demo" / "r" / "manifest.json").read_text())
    assert manifest["files"] == [entry]
    again = snap.fetch_range(
        "https://example.org/big.gz", "head.gz", start=0, length=40, observed="2024"
    )
    assert again == entry and len(calls) == 1  # a stored fragment is not fetched again
    assert snap.verify() == []
    mid = snap.fetch_range(
        "https://example.org/big.gz", "mid.gz", start=100, length=10, observed=None
    )
    assert mid["range"] == [100, 109]


def test_a_range_fetch_rejects_servers_that_ignore_the_range_or_answer_inconsistently(tmp_path):
    def snap_with(opener):
        return aq.Snapshot(tmp_path, RANGE_SPEC, "r", range_opener=opener, sleep=lambda s: None)

    def fetch(snap, start=10, length=20):
        return snap.fetch_range(
            "https://example.org/f", "f", start=start, length=length, observed=None
        )

    with pytest.raises(aq.AcquisitionError, match="did not honour the range"):
        fetch(snap_with(lambda u, s, n: {"status": 200, "content_range": None, "body": b"x" * 20}))
    with pytest.raises(aq.AcquisitionError, match="Content-Range"):
        fetch(snap_with(lambda u, s, n: {"status": 206, "content_range": None, "body": b"x" * 20}))
    with pytest.raises(aq.AcquisitionError, match="offset"):
        fetch(snap_with(lambda u, s, n: _partial(5, b"x" * 20, 100)))
    with pytest.raises(aq.AcquisitionError, match="length"):
        fetch(
            snap_with(
                lambda u, s, n: {
                    "status": 206,
                    "content_range": "bytes 10-40/100",
                    "body": b"x" * 20,
                }
            )
        )
    with pytest.raises(aq.AcquisitionError, match="larger than 50 bytes"):
        fetch(snap_with(lambda u, s, n: _partial(10, b"x" * 60, 100)), length=60)
    with pytest.raises(aq.AcquisitionError, match="malformed"):
        fetch(
            snap_with(
                lambda u, s, n: {
                    "status": 206,
                    "content_range": "items 10-29/100",
                    "body": b"x" * 20,
                }
            )
        )
    with pytest.raises(aq.AcquisitionError, match="host"):
        aq.Snapshot(tmp_path, RANGE_SPEC, "r").fetch_range(
            "https://evil.net/f", "f", start=0, length=1, observed=None
        )
    with pytest.raises(aq.AcquisitionError, match="length"):
        fetch(snap_with(lambda u, s, n: _partial(0, b"", 10)), start=0, length=0)
    with pytest.raises(aq.AcquisitionError, match="length"):
        fetch(snap_with(lambda u, s, n: _partial(0, b"", 10)), start=-1, length=5)
    unknown = snap_with(
        lambda u, s, n: {"status": 206, "content_range": "bytes 10-29/*", "body": b"x" * 20}
    )
    assert fetch(unknown)["total_bytes"] is None  # a server that does not know the total size


def test_range_requests_retry_with_pacing_and_report_the_last_error(tmp_path):
    waits, errors = [], [OSError("a"), OSError("b"), OSError("c")]

    def failing(url, start, length):
        raise errors.pop(0)

    snap = aq.Snapshot(
        tmp_path,
        {**RANGE_SPEC, "min_interval": 1.0, "retries": 2},
        "r",
        range_opener=failing,
        sleep=waits.append,
    )
    with pytest.raises(aq.AcquisitionError, match="after 3 attempts"):
        snap.fetch_range("https://example.org/f", "f", start=0, length=5, observed=None)
    assert waits == [1.0, 2.0, 1.0, 4.0, 1.0, 8.0]


def test_the_real_range_opener_sends_a_range_header_and_reads_at_most_length_plus_one(monkeypatch):
    seen = {}

    class Response:
        status = 206
        headers = {"Content-Range": "bytes 5-9/100"}

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self, n):
            seen["read"] = n
            return b"abcde"

    def fake(request, timeout):
        seen["range"] = request.get_header("Range")
        seen["agent"] = request.get_header("User-agent")
        seen["timeout"] = timeout
        return Response()

    monkeypatch.setattr(aq, "_opener", lambda hosts, url: types.SimpleNamespace(open=fake))
    out = aq.open_range("https://example.org/f", 5, 5)
    assert out == {"status": 206, "content_range": "bytes 5-9/100", "body": b"abcde"}
    assert seen == {"range": "bytes=5-9", "agent": aq.USER_AGENT, "timeout": 120, "read": 6}


def test_gzip_prefixes_return_only_complete_lines_and_say_whether_the_stream_ended():
    import gzip

    text = "".join(f'{{"n": {i}}}\n' for i in range(100)).encode()
    blob = gzip.compress(text)
    full = aq.gzip_prefix_lines(blob, max_output=10**6)
    assert len(full["lines"]) == 100 and full["complete"] is True and full["lines"][0] == '{"n": 0}'
    cut = aq.gzip_prefix_lines(blob[: len(blob) // 2], max_output=10**6)
    assert cut["complete"] is False and 0 < len(cut["lines"]) < 100
    assert cut["lines"] == [f'{{"n": {i}}}' for i in range(len(cut["lines"]))]  # a clean prefix
    assert all(line.endswith("}") for line in cut["lines"])  # a torn last line is dropped
    small = aq.gzip_prefix_lines(blob, max_output=50)
    assert small["complete"] is False and 0 < len(small["lines"]) <= 5
    assert small["output_bytes"] <= 50 + 64
    empty = aq.gzip_prefix_lines(gzip.compress(b""), max_output=10)
    assert empty == {"lines": [], "complete": True, "output_bytes": 0}
    with pytest.raises(aq.AcquisitionError, match="gzip"):
        aq.gzip_prefix_lines(b"not gzip at all, but long enough to be read", max_output=10)
    no_newline = aq.gzip_prefix_lines(gzip.compress(b"abc"), max_output=100)
    assert (
        no_newline["lines"] == ["abc"] and no_newline["complete"] is True
    )  # the last line of a complete stream


def test_the_command_line_fetches_configured_ranges_and_reports_them(tmp_path, monkeypatch, capsys):
    spec = {
        **SPEC,
        "id": "rng",
        "ranges": [
            {
                "url": "https://example.org/big",
                "name": "head",
                "start": 0,
                "length": 4,
                "observed": "2019",
            }
        ],
    }
    sources = tmp_path / "sources.json"
    sources.write_text(json.dumps({"sources": [spec]}))
    monkeypatch.setattr(aq, "SOURCES", sources)
    real = aq.Snapshot.__init__

    def init(
        self,
        root,
        spec,
        snapshot_id,
        opener=aq.open_url,
        sleep=aq.time.sleep,
        range_opener=aq.open_range,
    ):
        real(self, root, spec, snapshot_id, opener=opener, sleep=lambda s: None,
             range_opener=lambda u, s, n: _partial(s, b"abcd", 99))  # fmt: skip

    monkeypatch.setattr(aq.Snapshot, "__init__", init)
    assert aq.main(["rng", "--snapshot", "s", "--root", str(tmp_path / "out")]) == 0
    assert capsys.readouterr().out == "rng/s: 1 files, mismatches []\n"
    manifest = json.loads((tmp_path / "out" / "rng" / "s" / "manifest.json").read_text())
    assert manifest["files"][0]["range"] == [0, 3] and manifest["files"][0]["observed"] == "2019"


# --- safe extraction of one archive member -------------------------------------------------------


def _zip(path, members):
    import zipfile

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return path


def test_listing_an_archive_reports_members_with_both_sizes_without_reading_data(tmp_path):
    path = _zip(tmp_path / "a.zip", {"d/": b"", "d/x.csv": b"a,b\n" * 100, "y.txt": b"hello"})
    listing = aq.zip_members(path)
    assert [m["name"] for m in listing] == ["d/", "d/x.csv", "y.txt"]
    by = {m["name"]: m for m in listing}
    assert by["y.txt"]["bytes"] == 5 and by["d/x.csv"]["bytes"] == 400
    assert by["d/x.csv"]["compressed"] < 400 and by["d/"]["directory"] is True
    assert by["y.txt"]["directory"] is False


def test_extraction_writes_one_member_under_the_destination_and_returns_its_checksum(tmp_path):
    path = _zip(tmp_path / "a.zip", {"d/x.csv": b"a,b\n1,2\n"})
    out = aq.extract_member(path, "d/x.csv", tmp_path / "out", max_bytes=100, max_ratio=1000)
    assert out["path"] == tmp_path / "out" / "x.csv" and out["path"].read_bytes() == b"a,b\n1,2\n"
    assert out["sha256"] == hashlib.sha256(b"a,b\n1,2\n").hexdigest() and out["bytes"] == 8
    assert out["member"] == "d/x.csv"


def test_extraction_refuses_unsafe_oversized_compressed_bomb_and_missing_members(tmp_path):
    import zipfile

    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil, "w") as archive:
        archive.writestr("../escape.txt", b"x")
        archive.writestr("/abs.txt", b"x")
    for name in ("../escape.txt", "/abs.txt"):
        with pytest.raises(aq.AcquisitionError, match="unsafe member"):
            aq.extract_member(evil, name, tmp_path / "out", max_bytes=100, max_ratio=1000)
    assert not (tmp_path / "escape.txt").exists()
    big = _zip(tmp_path / "big.zip", {"big.bin": b"0" * 10_000})
    with pytest.raises(aq.AcquisitionError, match="larger than 5000 bytes"):
        aq.extract_member(big, "big.bin", tmp_path / "out", max_bytes=5000, max_ratio=10**6)
    with pytest.raises(aq.AcquisitionError, match="compression ratio"):
        aq.extract_member(big, "big.bin", tmp_path / "out", max_bytes=10**6, max_ratio=10)
    with pytest.raises(aq.AcquisitionError, match="no member"):
        aq.extract_member(big, "nope.bin", tmp_path / "out", max_bytes=100, max_ratio=10)
    (tmp_path / "bad.zip").write_bytes(b"not a zip at all")
    with pytest.raises(aq.AcquisitionError, match="not a readable zip"):
        aq.zip_members(tmp_path / "bad.zip")
    folder = _zip(tmp_path / "f.zip", {"d/": b""})
    with pytest.raises(aq.AcquisitionError, match="directory"):
        aq.extract_member(folder, "d/", tmp_path / "out", max_bytes=100, max_ratio=10)


def _single_member_zip(tmp_path, text: bytes, method):
    import zipfile

    path = tmp_path / "one.zip"
    with zipfile.ZipFile(path, "w", method) as archive:
        archive.writestr("data.jsonl", text)
    return path.read_bytes()


def test_zip_prefixes_decode_the_first_member_of_a_cut_archive_line_by_line(tmp_path):
    import zipfile

    text = "".join(f'{{"n": {i}}}\n' for i in range(5000)).encode()
    blob = _single_member_zip(tmp_path, text, zipfile.ZIP_DEFLATED)
    full = aq.zip_prefix_lines(blob, max_output=10**7)
    assert (
        len(full["lines"]) == 5000 and full["complete"] is True and full["member"] == "data.jsonl"
    )
    cut = aq.zip_prefix_lines(blob[: len(blob) // 3], max_output=10**7)
    assert cut["complete"] is False and 0 < len(cut["lines"]) < 5000
    assert cut["lines"] == [f'{{"n": {i}}}' for i in range(len(cut["lines"]))]
    small = aq.zip_prefix_lines(blob, max_output=100)
    assert (
        small["complete"] is False
        and small["output_bytes"] <= 100 + 64
        and len(small["lines"]) <= 12
    )


def test_zip_prefixes_refuse_non_zip_stored_and_encrypted_members(tmp_path):
    import zipfile

    with pytest.raises(aq.AcquisitionError, match="not a zip"):
        aq.zip_prefix_lines(b"x" * 100, max_output=10)
    stored = _single_member_zip(tmp_path, b"a\nb\n", zipfile.ZIP_STORED)
    with pytest.raises(aq.AcquisitionError, match="deflate"):
        aq.zip_prefix_lines(stored, max_output=100)
    deflated = bytearray(_single_member_zip(tmp_path, b"a\nb\n", zipfile.ZIP_DEFLATED))
    deflated[6] |= 1  # general purpose flag: encrypted
    with pytest.raises(aq.AcquisitionError, match="encrypted"):
        aq.zip_prefix_lines(bytes(deflated), max_output=100)
    with pytest.raises(aq.AcquisitionError, match="not a zip"):
        aq.zip_prefix_lines(b"PK\x03\x04short", max_output=10)


# --- exact behaviour of the range opener, boundaries and manifest of range fetches ---------------


def test_range_boundaries_accept_the_largest_allowed_fragment_and_a_single_byte(tmp_path):
    def snap(opener):
        return aq.Snapshot(tmp_path, RANGE_SPEC, "b", range_opener=opener, sleep=lambda s: None)

    one = snap(lambda u, s, n: _partial(s, b"z", 10)).fetch_range(
        "https://example.org/f", "one", start=3, length=1, observed=None
    )
    assert one["bytes"] == 1 and one["range"] == [3, 3]
    exact = snap(lambda u, s, n: _partial(s, b"y" * 50, 99)).fetch_range(
        "https://example.org/f", "exact", start=0, length=50, observed=None
    )
    assert exact["bytes"] == 50  # a fragment of exactly max_bytes is allowed


def test_a_range_fetch_writes_the_manifest_in_the_canonical_format_with_a_utc_timestamp(tmp_path):
    from datetime import datetime

    snap = aq.Snapshot(
        tmp_path, RANGE_SPEC, "m", range_opener=lambda u, s, n: _partial(s, b"abc", 7),
        sleep=lambda s: None,
    )  # fmt: skip
    entry = snap.fetch_range("https://example.org/f", "a", start=0, length=3, observed="2020")
    text = (tmp_path / "demo" / "m" / "manifest.json").read_text()
    manifest = json.loads(text)
    assert text == json.dumps(manifest, indent=1, sort_keys=True) + "\n"
    stamp = datetime.fromisoformat(entry["collected"])
    assert stamp.utcoffset().total_seconds() == 0 and stamp.microsecond == 0
    assert sorted(entry) == sorted(
        [
            "bytes",
            "collected",
            "name",
            "observed",
            "partial",
            "range",
            "sha256",
            "total_bytes",
            "url",
        ]
    )


def test_a_failed_range_request_reports_the_last_error_in_the_message(tmp_path):
    errors = [OSError("first"), OSError("second")]

    def failing(url, start, length):
        raise errors.pop(0)

    snap = aq.Snapshot(
        tmp_path, {**RANGE_SPEC, "retries": 1}, "r", range_opener=failing, sleep=lambda s: None
    )
    with pytest.raises(aq.AcquisitionError) as error:
        snap.fetch_range("https://example.org/f", "f", start=0, length=5, observed=None)
    assert str(error.value) == "https://example.org/f: failed after 2 attempts (OSError('second'))"


def test_the_range_request_object_carries_the_url_agent_and_range(monkeypatch):
    seen = {}

    class Response:
        status = 206
        headers = {"Content-Range": "bytes 0-1/9"}

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self, n):
            return b"ab"

    def fake(request, timeout):
        seen["url"] = request.full_url
        seen["headers"] = dict(request.header_items())
        return Response()

    monkeypatch.setattr(aq, "_opener", lambda hosts, url: types.SimpleNamespace(open=fake))
    aq.open_range("https://example.org/path?x=1", 0, 2)
    assert seen["url"] == "https://example.org/path?x=1"
    assert seen["headers"] == {"User-agent": aq.USER_AGENT, "Range": "bytes=0-1"}


# --- zip listing, extraction limits and prefix parsing: exact values and messages ----------------


def test_zip_listing_returns_exactly_the_documented_fields(tmp_path):
    path = _zip(tmp_path / "l.zip", {"d/": b"", "d/x.csv": b"a,b\n" * 100})
    listing = aq.zip_members(path)
    assert listing[1] == {
        "name": "d/x.csv",
        "bytes": 400,
        "compressed": listing[1]["compressed"],
        "directory": False,
    }
    assert listing[0]["directory"] is True and set(listing[0]) == {
        "name",
        "bytes",
        "compressed",
        "directory",
    }
    assert 0 < listing[1]["compressed"] < 400


def test_zip_extraction_boundaries_messages_and_destination_creation(tmp_path):
    path = _zip(tmp_path / "e.zip", {"d/x.bin": b"0" * 1000})
    out = aq.extract_member(
        path, "d/x.bin", tmp_path / "deep" / "new", max_bytes=1000, max_ratio=10**6
    )
    assert out["bytes"] == 1000 and out["path"].exists()  # a member of exactly max_bytes is allowed
    ratio = 1000 / aq.zip_members(path)[0]["compressed"]
    ok = aq.extract_member(path, "d/x.bin", tmp_path / "o2", max_bytes=1000, max_ratio=ratio)
    assert ok["bytes"] == 1000  # a ratio equal to the limit is allowed
    with pytest.raises(aq.AcquisitionError) as error:
        aq.extract_member(path, "d/x.bin", tmp_path / "o3", max_bytes=999, max_ratio=10**6)
    assert str(error.value) == f"{path}: member larger than 999 bytes"
    (tmp_path / "bad.zip").write_bytes(b"not a zip at all")
    with pytest.raises(aq.AcquisitionError) as error:
        aq.extract_member(tmp_path / "bad.zip", "x", tmp_path / "o4", max_bytes=10, max_ratio=10)
    assert str(error.value).startswith(f"{tmp_path / 'bad.zip'}: not a readable zip archive (")


def test_zip_extraction_of_a_member_with_a_lying_header_fails_cleanly_and_leaves_no_file(
    tmp_path, monkeypatch
):
    import zipfile

    path = _zip(tmp_path / "s.zip", {"x.bin": b"0" * (3 << 20)})
    real = zipfile.ZipFile.getinfo

    def understated(self, name):
        info = real(self, name)
        info.file_size = 10  # a lying header: the archive reader stops there and the checksum fails
        return info

    monkeypatch.setattr(zipfile.ZipFile, "getinfo", understated)
    with pytest.raises(aq.AcquisitionError, match="not a readable zip archive"):
        aq.extract_member(path, "x.bin", tmp_path / "o", max_bytes=2_000_000, max_ratio=10**9)
    assert not (tmp_path / "o" / "x.bin").exists()  # nothing is left behind


def test_the_prefix_reader_keeps_the_exact_limit_and_decodes_invalid_bytes_with_replacement():
    import gzip

    text = b"abc\n" * 10
    blob = gzip.compress(text)
    exact = aq.gzip_prefix_lines(blob, max_output=len(text))
    assert exact["complete"] is True and len(exact["lines"]) == 10 and exact["output_bytes"] == 40
    one_less = aq.gzip_prefix_lines(blob, max_output=len(text) - 1)
    assert one_less["complete"] is False and one_less["output_bytes"] == len(text) - 1
    assert len(one_less["lines"]) == 9  # the line cut by the limit is dropped
    broken = aq.gzip_prefix_lines(gzip.compress(b"ok\xff\xfe\n"), max_output=100)
    assert broken["lines"] == ["ok��"]
    with pytest.raises(aq.AcquisitionError) as error:
        aq.gzip_prefix_lines(b"not gzip, long enough to be read as a stream", max_output=10)
    assert str(error.value).startswith("not a readable gzip stream (")
    # a raw zlib stream has no gzip header: only the gzip window setting accepts gzip input
    import zlib

    with pytest.raises(aq.AcquisitionError):
        aq.gzip_prefix_lines(zlib.compress(b"abc\n"), max_output=100)


def test_the_prefix_reader_stops_early_on_a_stream_larger_than_the_limit_without_reading_it_all():
    import gzip

    blob = gzip.compress(b"0123456789\n" * 200_000)  # about 2 MB decoded from a few KB
    out = aq.gzip_prefix_lines(blob, max_output=1000)
    assert out["complete"] is False and out["output_bytes"] == 1000 and len(out["lines"]) == 90


def test_zip_prefix_header_checks_use_exact_thresholds_unsigned_fields_and_messages(tmp_path):
    import zipfile

    blob = _single_member_zip(tmp_path, b"a\nb\n", zipfile.ZIP_DEFLATED)
    with pytest.raises(aq.AcquisitionError) as error:
        aq.zip_prefix_lines(b"PK\x03\x04" + b"\x00" * 26, max_output=10)  # 30 bytes: header only
    assert "deflate" in str(error.value)  # a 30-byte header is long enough to be read
    with pytest.raises(aq.AcquisitionError) as error:
        aq.zip_prefix_lines(b"x" * 100, max_output=10)
    assert str(error.value) == "not a zip archive (no local file header at the start)"
    enc = bytearray(blob)
    enc[6] |= 1
    with pytest.raises(aq.AcquisitionError) as error:
        aq.zip_prefix_lines(bytes(enc), max_output=10)
    assert str(error.value) == "the first member is encrypted"
    stored = _single_member_zip(tmp_path, b"a\n", zipfile.ZIP_STORED)
    with pytest.raises(aq.AcquisitionError) as error:
        aq.zip_prefix_lines(stored, max_output=10)
    assert str(error.value) == "the first member is not deflate-compressed"
    high = bytearray(blob)
    high[27] = 0x80  # name length above 32767: a signed read would go negative
    high[26] = 0x00
    assert aq.zip_prefix_lines(bytes(blob), max_output=100)["member"] == "data.jsonl"
    skipped = aq.zip_prefix_lines(bytes(high), max_output=100)  # a name length read as unsigned
    assert skipped["lines"] == [] and skipped["complete"] is False
    named = aq.zip_prefix_lines(blob, max_output=100)
    assert named["lines"] == ["a", "b"] and named["member"] == "data.jsonl"


def test_zip_extraction_of_a_member_larger_than_one_read_chunk_sums_every_chunk(tmp_path):
    payload = bytes(range(256)) * (10 * 1024)  # 2.5 MiB: three reads of at most one MiB
    path = _zip(tmp_path / "big.zip", {"d/big.bin": payload})
    out = aq.extract_member(
        path, "d/big.bin", tmp_path / "o", max_bytes=len(payload), max_ratio=10**6
    )
    assert out["bytes"] == len(payload) and out["sha256"] == hashlib.sha256(payload).hexdigest()
    assert out["path"].read_bytes() == payload
    again = aq.extract_member(
        path, "d/big.bin", tmp_path / "o", max_bytes=len(payload), max_ratio=10**6
    )
    assert again["sha256"] == out["sha256"]  # extracting into an existing folder is allowed
    assert sorted(out) == ["bytes", "member", "path", "sha256"]


# --- redirect safety: a listed host may only send the client to https and to listed hosts --------


def _redirect(handler, url, newurl):
    import email.message

    request = aq.urllib.request.Request(url)
    return handler.redirect_request(request, None, 302, "Found", email.message.Message(), newurl)


def test_redirects_stay_on_https_and_on_listed_hosts_or_their_subdomains():
    handler = aq.GuardedRedirect(["data.4tu.nl", "files.example.org"])
    followed = _redirect(handler, "https://data.4tu.nl/file/x", "https://data.4tu.nl/other")
    assert followed.full_url == "https://data.4tu.nl/other"
    assert (
        _redirect(handler, "https://data.4tu.nl/f", "https://cdn.files.example.org/a").full_url
        == "https://cdn.files.example.org/a"
    )
    for bad in (
        "http://data.4tu.nl/f",
        "https://evil.example.net/a",
        "https://data.4tu.nl.evil.net/a",
        "ftp://data.4tu.nl/a",
    ):
        with pytest.raises(aq.urllib.error.URLError, match="redirect"):
            _redirect(handler, "https://data.4tu.nl/f", bad)
    with pytest.raises(aq.urllib.error.URLError, match="evil.example.net"):
        _redirect(handler, "https://data.4tu.nl/f", "https://evil.example.net/a")
    assert isinstance(
        aq.urllib.error.URLError("x"), OSError
    )  # so the retry loop treats it as a network error


def test_a_redirect_host_is_matched_by_whole_labels_not_by_suffix_text():
    handler = aq.GuardedRedirect(["archive.org"])
    assert _redirect(
        handler, "https://archive.org/d", "https://ia800702.us.archive.org/x"
    ).full_url.startswith("https://ia8")
    with pytest.raises(aq.urllib.error.URLError):
        _redirect(handler, "https://archive.org/d", "https://notarchive.org/x")


def test_the_default_openers_are_bound_to_the_listed_and_redirect_hosts(tmp_path, monkeypatch):
    seen = {}

    def fake_open_url(url, limit, hosts=None):
        seen["hosts"] = hosts
        return b"x"

    monkeypatch.setattr(aq, "open_url", fake_open_url)
    spec = {**SPEC, "hosts": ["example.org"], "redirect_hosts": ["cdn.example.net"]}
    snap = aq.Snapshot(tmp_path, spec, "r", sleep=lambda s: None)
    snap.fetch("https://example.org/a", "a.bin", None)
    assert sorted(seen["hosts"]) == ["cdn.example.net", "example.org"]


# --- opener construction, host binding and decompression bounds ---------------------------------


def test_the_opener_is_bound_to_the_given_hosts_or_to_the_host_of_the_url():
    default = aq._opener(None, "https://data.example.org/path")
    handler = next(h for h in default.handlers if isinstance(h, aq.GuardedRedirect))
    assert handler.hosts == ["data.example.org"]  # no list given: only the request's own host
    given = aq._opener(["a.org", "b.org"], "https://data.example.org/path")
    assert next(h for h in given.handlers if isinstance(h, aq.GuardedRedirect)).hosts == [
        "a.org",
        "b.org",
    ]
    empty = aq._opener(None, "not a url")
    assert next(h for h in empty.handlers if isinstance(h, aq.GuardedRedirect)).hosts == [""]
    assert (
        sum(isinstance(h, aq.urllib.request.HTTPRedirectHandler) for h in given.handlers) == 1
    )  # replaced, not added


def test_the_url_and_range_openers_pass_their_hosts_and_url_to_the_opener_factory(monkeypatch):
    calls = []

    class Reply:
        status = 206
        headers = {"Content-Range": "bytes 0-1/9"}

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self, n):
            return b"ab"

    monkeypatch.setattr(
        aq,
        "_opener",
        lambda hosts, url: (
            calls.append((hosts, url)) or types.SimpleNamespace(open=lambda r, timeout: Reply())
        ),
    )
    aq.open_url("https://h.org/a", 10, hosts=["h.org", "c.org"])
    aq.open_range("https://h.org/b", 0, 2, hosts=["h.org"])
    assert calls == [(["h.org", "c.org"], "https://h.org/a"), (["h.org"], "https://h.org/b")]
    request_seen = []
    monkeypatch.setattr(
        aq,
        "_opener",
        lambda hosts, url: types.SimpleNamespace(
            open=lambda r, timeout: request_seen.append(r) or Reply()
        ),
    )
    aq.open_range("https://h.org/b", 5, 3)
    assert request_seen[0].get_header("Range") == "bytes=5-7"  # the last byte is start + length - 1


def test_the_default_range_opener_receives_the_listed_and_redirect_hosts(tmp_path, monkeypatch):
    seen = {}

    def fake_range(url, start, length, hosts=None):
        seen["hosts"] = hosts
        return {
            "status": 206,
            "content_range": f"bytes {start}-{start + length - 1}/50",
            "body": b"x" * length,
        }

    monkeypatch.setattr(aq, "open_range", fake_range)
    spec = {**RANGE_SPEC, "hosts": ["example.org"], "redirect_hosts": ["cdn.example.net"]}
    aq.Snapshot(tmp_path, spec, "r", sleep=lambda s: None).fetch_range(
        "https://example.org/f", "f", start=0, length=3, observed=None
    )
    assert seen["hosts"] == ["example.org", "cdn.example.net"]


def test_decompression_never_produces_more_than_the_output_limit_plus_one_byte(monkeypatch):
    import gzip
    import zlib

    produced = []
    real = zlib.decompressobj

    class Spy:
        def __init__(self, wbits):
            self.inner = real(wbits=wbits)

        def decompress(self, data, max_length=0):
            out = self.inner.decompress(data, max_length)
            produced.append(len(out))
            return out

        def __getattr__(self, name):
            return getattr(self.inner, name)

    monkeypatch.setattr(zlib, "decompressobj", lambda wbits: Spy(wbits))
    bomb = gzip.compress(b"0" * 5_000_000)  # a few KB that expand to 5 MB
    result = aq.gzip_prefix_lines(bomb, max_output=1000)
    assert sum(produced) == 1001 and result["output_bytes"] == 1000 and result["complete"] is False


def test_a_zip_member_with_an_extra_field_is_read_from_the_right_offset():
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        info = zipfile.ZipInfo("data.jsonl")
        info.extra = b"\xfe\xca\x04\x00abcd"  # an unknown extra record of four bytes
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info, b"line one\nline two\n")
    out = aq.zip_prefix_lines(buffer.getvalue(), max_output=1000)
    assert (
        out["lines"] == ["line one", "line two"]
        and out["member"] == "data.jsonl"
        and out["complete"] is True
    )
