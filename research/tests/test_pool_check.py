"""Pinned manifest of the pool and the check that every download still matches it."""

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pool_check as pc  # noqa: E402

INVENTORY = [
    {
        "name": "thyroid",
        "decision": "INCLUDE",
        "source_url": "https://raw.githubusercontent.com/x/t.npz",
        "sha256": "aa" * 32,
        "underlying_terms": "CC BY 4.0 (u)",
    },
    {
        "name": "celeba",
        "decision": "EXCLUDE",
        "source_url": "https://raw.githubusercontent.com/x/c.npz",
        "sha256": "bb" * 32,
        "underlying_terms": "no open licence",
    },
]
UCI = [
    {
        "uci_id": 7,
        "name": "Toy",
        "url": "https://archive.ics.uci.edu/static/public/7/data.csv",
        "sha256": "cc" * 32,
        "licence": "CC BY 4.0",
        "roles": ["carrier"],
    }
]


def test_manifest_lists_only_included_sets_with_url_digest_and_licence():
    manifest = pc.build_manifest(INVENTORY, UCI)
    assert [e["id"] for e in manifest] == ["adbench:thyroid", "uci:7"]
    assert manifest[1] == {
        "id": "uci:7",
        "url": UCI[0]["url"],
        "sha256": "cc" * 32,
        "licence": "CC BY 4.0",
    }


def test_verify_reports_unchanged_changed_and_unreachable_without_stopping(tmp_path):
    good = b"table"
    manifest = [
        {
            "id": "a",
            "url": "https://archive.ics.uci.edu/a",
            "sha256": hashlib.sha256(good).hexdigest(),
        },
        {"id": "b", "url": "https://archive.ics.uci.edu/b", "sha256": "00" * 32},
        {"id": "c", "url": "https://archive.ics.uci.edu/c", "sha256": "11" * 32},
        {"id": "d", "url": "https://example.org/d", "sha256": "22" * 32},
    ]

    def opener(url, limit):
        if url.endswith("/c"):
            raise OSError("down")
        return good

    report = pc.verify(manifest, opener=opener, sleep=lambda s: None)
    assert {r["id"]: r["status"] for r in report} == {
        "a": "ok",
        "b": "changed",
        "c": "unreachable",
        "d": "refused",
    }
    assert not list(tmp_path.iterdir())  # nothing is written next to the repository


def test_the_exit_code_is_nonzero_when_any_download_differs(tmp_path):
    manifest = tmp_path / "m.json"
    manifest.write_text(
        json.dumps([{"id": "a", "url": "https://archive.ics.uci.edu/a", "sha256": "00" * 32}])
    )
    assert (
        pc.main(
            ["--verify", str(manifest), "--output", str(tmp_path / "r.json")],
            opener=lambda u, n: b"x",
        )
        == 1
    )


def test_a_transient_failure_is_retried_with_a_pause_before_it_is_reported():
    data, calls, pauses = b"table", [], []

    def flaky(url, limit):
        calls.append(url)
        if len(calls) < 3:
            raise OSError("429")
        return data

    entry = {
        "id": "a",
        "url": "https://archive.ics.uci.edu/a",
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    assert pc.verify([entry], opener=flaky, sleep=pauses.append)[0]["status"] == "ok"
    assert len(calls) == 3 and len(pauses) >= 2 and pauses[1] > pauses[0]
    always = pc.verify(
        [entry], opener=lambda u, n: (_ for _ in ()).throw(OSError("x")), sleep=lambda s: None
    )
    assert always[0]["status"] == "unreachable"


def test_an_included_adbench_set_keeps_exactly_url_digest_and_underlying_terms():
    manifest = pc.build_manifest(INVENTORY, [])
    assert manifest == [
        {
            "id": "adbench:thyroid",
            "url": "https://raw.githubusercontent.com/x/t.npz",
            "sha256": "aa" * 32,
            "licence": "CC BY 4.0 (u)",
        }
    ]


def test_the_retry_policy_is_four_attempts_with_doubling_pauses_then_the_original_error():
    calls, pauses = [], []

    def down(url, limit):
        calls.append(url)
        raise OSError("503")

    try:
        pc._download("https://archive.ics.uci.edu/a", down, pauses.append)
    except OSError as error:
        assert str(error) == "503"
    else:
        raise AssertionError("the final transport error must propagate")
    assert len(calls) == 4
    assert pauses == [2.0, 4.0, 8.0]


def test_a_refused_download_is_never_attempted_and_never_retried():
    calls, pauses = [], []

    def opener(url, limit):
        calls.append(url)
        return b"x"

    report = pc.verify(
        [{"id": "x", "url": "http://example.org/x", "sha256": "00" * 32}],
        opener=opener,
        sleep=pauses.append,
    )
    assert report == [{"id": "x", "status": "refused"}]
    assert calls == [] and pauses == [0.3]


def test_a_download_loop_with_no_attempt_fails_loudly_instead_of_returning():
    try:
        pc._download("https://archive.ics.uci.edu/a", lambda u, n: b"", lambda s: None, attempts=0)
    except AssertionError as error:
        assert str(error) == "unreachable"
    else:
        raise AssertionError("zero attempts must not return data")


def test_every_entry_is_followed_by_a_short_politeness_pause():
    pauses = []
    manifest = [
        {"id": i, "url": "https://archive.ics.uci.edu/" + i, "sha256": "00" * 32} for i in "ab"
    ]
    pc.verify(manifest, opener=lambda u, n: b"x", sleep=pauses.append)
    assert pauses == [0.3, 0.3]


def test_build_reads_inventory_then_uci_rows_and_writes_a_sorted_indented_manifest(
    tmp_path, capsys
):
    inventory = tmp_path / "inventory.json"
    uci = tmp_path / "uci.json"
    out = tmp_path / "manifest.json"
    inventory.write_text(json.dumps(INVENTORY))
    uci.write_text(json.dumps({"rows": UCI}))
    assert pc.main(["--build", str(inventory), str(uci), "--output", str(out)]) == 0
    assert capsys.readouterr().out == "2 entries\n"
    expected = pc.build_manifest(INVENTORY, UCI)
    assert json.loads(out.read_text()) == expected
    assert out.read_text() == json.dumps(expected, indent=1, sort_keys=True) + "\n"
    assert out.read_text().startswith('[\n {\n  "id": "adbench:thyroid"')


def test_verify_exits_zero_only_when_every_entry_is_ok_and_reports_the_count(tmp_path, capsys):
    good = b"table"
    manifest = tmp_path / "m.json"
    manifest.write_text(
        json.dumps(
            [
                {
                    "id": "a",
                    "url": "https://archive.ics.uci.edu/a",
                    "sha256": hashlib.sha256(good).hexdigest(),
                }
            ]
        )
    )
    out = tmp_path / "r.json"
    pauses = []
    code = pc.main(
        ["--verify", str(manifest), "--output", str(out)],
        opener=lambda u, n: good,
        sleep=pauses.append,
    )
    assert code == 0
    assert pauses == [0.3]  # the injected sleep, not the real clock, paces the run
    assert capsys.readouterr().out == "1 entries\n"
    assert json.loads(out.read_text()) == [{"id": "a", "status": "ok"}]
    assert out.read_text() == json.dumps([{"id": "a", "status": "ok"}], indent=1) + "\n"


def test_an_unreachable_or_refused_entry_also_fails_the_run(tmp_path):
    manifest = tmp_path / "m.json"
    manifest.write_text(
        json.dumps([{"id": "d", "url": "https://example.org/d", "sha256": "00" * 32}])
    )
    code = pc.main(
        ["--verify", str(manifest), "--output", str(tmp_path / "r.json")], sleep=lambda s: None
    )
    assert code == 1


def test_the_command_line_requires_an_output_and_documents_its_arguments(capsys):
    try:
        pc.main(["--verify", "m.json"])
    except SystemExit as stop:
        assert stop.code == 2
    else:
        raise AssertionError("--output is required")
    capsys.readouterr()
    try:
        pc.main(["--help"])
    except SystemExit as stop:
        assert stop.code == 0
    text = capsys.readouterr().out
    assert "--build INVENTORY UCI_POOL\n" in text and "--verify MANIFEST\n" in text
    assert "Pinned manifest of the pooled" in text
