"""The release command wires every input into the decision and reports its verdict."""

import json

import pytest

from verification import release


def test_load_docs_returns_each_kind_or_none_for_unreadable_evidence(tmp_path):
    (tmp_path / "fast.json").write_text(json.dumps({"kind": "fast"}))
    (tmp_path / "deep.json").write_text("not json")
    docs = release.load_docs(tmp_path, ["fast", "deep", "faults"])
    assert docs == {"fast": {"kind": "fast"}, "deep": None, "faults": None}


def _wire(monkeypatch, tmp_path, status="CERTIFIED", reasons=()):
    seen = {}
    policy = {"required": ["fast", "deep"], "version": 2}
    current = {"revision": "r" * 40, "scientific_fingerprint": "f" * 64}
    monkeypatch.setattr(release.mutation_scope, "load", lambda: {"roots": ["x"]})
    monkeypatch.setattr(release.mutation_scope, "inventory", lambda root, config: ["x/a.py"])
    monkeypatch.setattr(release, "load_policy", lambda: policy)
    monkeypatch.setattr(release.evidence_schema, "collect_source", lambda: current)
    monkeypatch.setattr(release.claims, "load", lambda: {"claims": "published"})

    def check_run(published, *, root, scientific_fingerprint, scope):
        seen["run"] = (published, root, scientific_fingerprint, scope)
        return ["run problem"]

    monkeypatch.setattr(release.claims, "check_run", check_run)
    monkeypatch.setattr(release.claims, "check_paper", lambda published, tex: ["paper problem"])
    monkeypatch.setattr(release, "reference_hashes", lambda: {"d": "h"})
    monkeypatch.setattr(release, "archive_lineage", lambda: {"legacy": []})
    monkeypatch.setattr(release, "locked_versions", lambda: {"numpy": "1"})
    monkeypatch.setattr(release, "freshness", lambda: "fresh-callable")

    def assess(docs, **kwargs):
        seen["docs"], seen["kwargs"] = docs, kwargs
        return {"status": status, "attestation": "local-unattested", "reasons": list(reasons)}

    monkeypatch.setattr(release, "assess", assess)
    return seen, policy, current


def test_the_command_passes_every_input_to_the_decision_and_writes_the_report(
    monkeypatch, tmp_path, capsys
):
    seen, policy, current = _wire(monkeypatch, tmp_path)
    (tmp_path / "fast.json").write_text(json.dumps({"kind": "fast"}))
    output = tmp_path / "out" / "release.json"
    code = release.main(["--evidence", str(tmp_path), "--output", str(output)])
    assert code == 0
    assert seen["docs"] == {"fast": {"kind": "fast"}, "deep": None}
    kwargs = seen["kwargs"]
    assert kwargs["current"] == current and kwargs["root"] == release.ROOT
    assert kwargs["manifest"] == {"d": "h"} and kwargs["lineage"] == {"legacy": []}
    assert kwargs["locked"] == {"numpy": "1"} and kwargs["policy"] == policy
    assert kwargs["fresh"] == "fresh-callable"
    assert kwargs["scope"] == {"inventory": ["x/a.py"], "config": {"roots": ["x"]}}
    assert kwargs["claims"] == ["run problem", "paper problem"]
    assert seen["run"] == (
        {"claims": "published"}, release.ROOT, "f" * 64, {"roots": ["x"]},
    )  # fmt: skip
    text = output.read_text()
    assert text == json.dumps(json.loads(text), indent=2, sort_keys=True) + "\n"
    assert capsys.readouterr().out.strip() == "release: CERTIFIED (local-unattested)"


@pytest.mark.parametrize("status", ["REJECTED", "INCOMPLETE"])
def test_any_verdict_but_certified_fails_and_lists_every_reason(
    monkeypatch, tmp_path, capsys, status
):
    _wire(monkeypatch, tmp_path, status=status, reasons=("first", "second"))
    code = release.main(["--evidence", str(tmp_path), "--output", str(tmp_path / "r.json")])
    assert code == 1
    lines = capsys.readouterr().out.splitlines()
    assert lines == [f"release: {status} (local-unattested)", "  - first", "  - second"]
