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
