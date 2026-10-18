"""Every published verification figure names the run it describes and is checked against it."""

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.test_evidence_schema import (
    ENVIRONMENT,
    SOURCE,
    _deep,
    _fast,
    _matrix,
    _real,
    _reproduction,
    _tools,
    _types,
)
from verification import claims, evidence_schema, mutation_scope

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "experiments"))
import verify_real  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
GIT = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t"}
GIT |= {"GIT_COMMITTER_EMAIL": "t@x", "PATH": "/usr/bin:/bin"}


def _git(root, *args):
    done = subprocess.run(
        ["git", *args], cwd=root, env=GIT, check=True, capture_output=True, text=True
    )
    return done.stdout.strip()


@pytest.fixture(autouse=True)
def _two_datasets(monkeypatch):
    monkeypatch.setattr(evidence_schema, "REQUIRED_DATASETS", ("a", "b"))


def _repo(tmp_path):
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    (root / "src/m.py").write_text("x = 1\n")
    (root / "README.md").write_text("doc\n")
    _git(root, "init", "-q")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "first")
    return root


def _run_dir(root, revision, fingerprint=SOURCE["scientific_fingerprint"], name="run1"):
    """Envelopes of one run, written with the real builders."""
    scratch = root.parent / f"scratch-{name}"
    scratch.mkdir(exist_ok=True)
    source = {"revision": revision, "worktree_dirty": False, "scientific_fingerprint": fingerprint}
    docs = {
        "fast": _fast(scratch),
        "deep": _deep(scratch),
        "faults": _matrix(scratch),
        "real": _real(scratch),
        "tools": _tools(scratch),
        "types": _types(scratch),
        "reproduction": _reproduction(scratch),
    }
    target = root / "verification" / "evidence" / "runs" / name
    target.mkdir(parents=True)
    for kind, doc in docs.items():
        doc["source"] = copy.deepcopy(source)
        (target / f"{kind}.json").write_text(json.dumps(doc))
    (target / "results.txt").write_text(
        "    etl_benchmark.split.x_f__mutmut_1: killed\n"
        "    etl_benchmark.split.x_f__mutmut_2: survived\n"
        "    experiments.run_benchmark.x_main__mutmut_1: killed\n"
        "    experiments.run_benchmark.x_main__mutmut_2: killed\n"
    )
    return target


def _claims(root, revision, **run):
    block = {
        "id": "run1",
        "revision": revision,
        "source": "local-unattested",
        "platform": "macOS-arm64",
        "captured": "2026-10-17",
        "historical": False,
        "evidence_dir": "verification/evidence/runs/run1",
    }
    block.update(run)
    return {"schema_version": 2, "published_run": block}


def _seal(root, claims_doc):
    """Record the hashes of the run files and the figures they give."""
    directory = root / claims_doc["published_run"]["evidence_dir"]
    claims_doc["published_run"]["files"] = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(directory.iterdir())
    }
    claims_doc.update(
        claims.figures_from_run(directory, {"scientific": ["src/etl_benchmark/split.py"]})
    )
    return claims_doc


def _valid(tmp_path):
    root = _repo(tmp_path)
    revision = _git(root, "rev-parse", "HEAD")
    _run_dir(root, revision)
    return root, revision, _seal(root, _claims(root, revision))


def _check(root, doc, scope=None):
    scope = scope or {"scientific": ["src/etl_benchmark/split.py"]}
    return claims.check_run(
        doc, root=root, scientific_fingerprint=SOURCE["scientific_fingerprint"], scope=scope
    )


def test_a_sealed_run_of_the_current_code_is_consistent(tmp_path):
    root, _, doc = _valid(tmp_path)
    assert _check(root, doc) == []


def test_the_figures_are_read_from_the_envelopes_not_typed(tmp_path):
    root, _, doc = _valid(tmp_path)
    assert doc["fast"]["tests"] == 5 and doc["fast"]["line_coverable"] == 10
    assert doc["verifier"] == {"line": 10, "branch": 4}
    assert doc["faults"] == 3
    # the split comes from the mutant listing: split.py has 1 of 2 killed, the others 2 of 2
    assert doc["mutation"] == {
        "killed": 98,
        "total": 100,
        "survived": 2,
        "scientific_killed": 1,
        "scientific_total": 2,
        "other_killed": 2,
        "other_total": 2,
    }


def test_a_figure_that_differs_from_its_envelope_is_rejected(tmp_path):
    root, _, doc = _valid(tmp_path)
    doc["fast"]["tests"] = 6
    assert any("fast.tests" in p for p in _check(root, doc))
    doc = _seal(root, _claims(root, doc["published_run"]["revision"]))
    doc["mutation"]["killed"] += 1
    assert any("mutation.killed" in p for p in _check(root, doc))


def test_a_run_without_identity_is_unscoped(tmp_path):
    root, _, doc = _valid(tmp_path)
    for key in ("revision", "source", "platform", "captured"):
        broken = copy.deepcopy(doc)
        del broken["published_run"][key]
        assert any(key in p for p in _check(root, broken)), key
    broken = copy.deepcopy(doc)
    broken["published_run"]["source"] = "somewhere"
    assert any("source" in p for p in _check(root, broken))
    broken = copy.deepcopy(doc)
    del broken["published_run"]
    assert any("published_run" in p for p in _check(root, broken))


def test_a_run_that_is_not_in_the_history_is_rejected(tmp_path):
    root, _, doc = _valid(tmp_path)
    doc["published_run"]["revision"] = "d" * 40
    assert any("history" in p for p in _check(root, doc))


def test_a_changed_run_file_is_rejected(tmp_path):
    root, _, doc = _valid(tmp_path)
    path = root / doc["published_run"]["evidence_dir"] / "fast.json"
    path.write_text(path.read_text() + " ")
    assert any("fast.json" in p and "hash" in p for p in _check(root, doc))
    path.unlink()
    assert any("fast.json" in p and "missing" in p for p in _check(root, doc))


def test_a_run_of_other_science_is_stale(tmp_path):
    root, _, doc = _valid(tmp_path)
    problems = claims.check_run(
        doc, root=root, scientific_fingerprint="e" * 64, scope={"scientific": []}
    )
    assert any("scientific fingerprint" in p for p in problems)


def test_code_changed_since_the_run_makes_its_figures_stale(tmp_path):
    root, _, doc = _valid(tmp_path)
    (root / "README.md").write_text("more documentation\n")
    _git(root, "commit", "-qam", "docs")
    assert _check(root, doc) == [], "documentation does not age a run"
    (root / "src/m.py").write_text("x = 2\n")
    _git(root, "commit", "-qam", "code")
    assert any("src/m.py" in p and "since" in p for p in _check(root, doc))


def test_a_historical_run_may_be_behind_the_code_but_must_say_why(tmp_path):
    root, _, doc = _valid(tmp_path)
    (root / "src/m.py").write_text("x = 2\n")
    _git(root, "commit", "-qam", "code")
    doc["published_run"]["historical"] = True
    assert any("note" in p for p in _check(root, doc))
    doc["published_run"]["note"] = "figures of the thesis submission; superseded by later runs"
    assert _check(root, doc) == []


def test_a_run_with_a_failed_or_dirty_envelope_is_rejected(tmp_path):
    root, revision, doc = _valid(tmp_path)
    path = root / doc["published_run"]["evidence_dir"] / "fast.json"
    envelope = json.loads(path.read_text())
    envelope["source"]["worktree_dirty"] = True
    path.write_text(json.dumps(envelope))
    doc = _seal(root, _claims(root, revision))
    assert any("dirty" in p for p in _check(root, doc))
    envelope["source"]["worktree_dirty"] = False
    envelope["source"]["revision"] = "c" * 40
    path.write_text(json.dumps(envelope))
    doc = _seal(root, _claims(root, revision))
    assert any("revision" in p for p in _check(root, doc))


def test_the_paper_must_name_the_run_it_reports(tmp_path):
    root, revision, doc = _valid(tmp_path)
    name = claims.paper_identity(doc)
    assert revision[:8] in name and "local" in name
    assert claims.check_paper(doc, f"... {name} ...") == []
    assert any("names" in p for p in claims.check_paper(doc, "At the current revision ..."))


def test_archiving_a_run_copies_the_envelopes_and_seals_the_claims(tmp_path):
    root = _repo(tmp_path)
    revision = _git(root, "rev-parse", "HEAD")
    source = _run_dir(root, revision, name="staged")
    evidence, listing = root / "evidence_in", root / "results.txt"
    evidence.mkdir()
    for path in source.glob("*.json"):
        (evidence / path.name).write_text(path.read_text())
    listing.write_text((source / "results.txt").read_text())
    out = root / "claims.json"
    out.write_text(json.dumps({"schema_version": 2}))
    done = claims.archive(
        run_id="run9",
        source_label="local-unattested",
        platform="macOS-arm64",
        evidence=evidence,
        results=listing,
        root=root,
        claims_path=out,
        scope={"scientific": ["src/etl_benchmark/split.py"]},
        captured="2026-10-17",
    )
    assert done["published_run"]["revision"] == revision
    assert done["published_run"]["files"].keys() == {
        "fast.json", "deep.json", "faults.json", "real.json", "tools.json", "types.json",
        "reproduction.json", "results.txt",
    }  # fmt: skip
    assert (root / "verification/evidence/runs/run9/results.txt").is_file()
    assert json.loads(out.read_text()) == done
    assert claims.check_run(
        done, root=root, scientific_fingerprint=SOURCE["scientific_fingerprint"],
        scope={"scientific": ["src/etl_benchmark/split.py"]},
    ) == []  # fmt: skip


def test_archiving_refuses_envelopes_from_different_revisions(tmp_path):
    root = _repo(tmp_path)
    revision = _git(root, "rev-parse", "HEAD")
    source = _run_dir(root, revision, name="staged")
    evidence = root / "evidence_in"
    evidence.mkdir()
    for path in source.glob("*.json"):
        doc = json.loads(path.read_text())
        if path.name == "deep.json":
            doc["source"]["revision"] = "f" * 40
        (evidence / path.name).write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="revision"):
        claims.archive(
            run_id="run9", source_label="local-unattested", platform="p", evidence=evidence,
            results=source / "results.txt", root=root, claims_path=root / "claims.json",
            scope={"scientific": []}, captured="2026-10-17",
        )  # fmt: skip


def test_the_repository_claims_name_a_run_that_exists_in_the_history(monkeypatch):
    monkeypatch.setattr(evidence_schema, "REQUIRED_DATASETS", verify_real.REQUIRED_DATASETS)
    doc = claims.load()
    run = doc["published_run"]
    fingerprint = evidence_schema.collect_source()["scientific_fingerprint"]
    scope = mutation_scope.load()
    problems = claims.check_run(
        doc, root=ROOT, scientific_fingerprint=fingerprint, scope=scope, current=False
    )
    assert problems == [], run


def test_the_paper_of_this_repository_names_its_run():
    doc = claims.load()
    tex = (ROOT / "paper" / "main.tex").read_text()
    assert claims.check_paper(doc, tex) == []
    assert ENVIRONMENT  # fixtures imported for the shared builders


@pytest.mark.parametrize(
    ("path", "code"),
    [
        ("src/etl_benchmark/split.py", True),
        ("experiments/run_benchmark.py", True),
        ("tests/test_x.py", True),
        (".github/workflows/ci.yml", True),
        ("Makefile", True),
        ("pyproject.toml", True),
        ("verification/release.py", True),
        ("verification/mutation_scope.json", True),
        ("verification/claims.json", False),
        ("verification/report.md", False),
        ("verification/evidence/runs/x/fast.json", False),
        ("paper/main.tex", False),
        ("README.md", False),
    ],
)
def test_only_code_and_configuration_age_a_run(path, code):
    assert claims.is_code(path) is code


def test_the_scientific_split_accepts_files_and_directories_and_skips_noise():
    scope = {"scientific": ["src/etl_benchmark/split.py", "src/etl_benchmark/quality/"]}
    text = (
        "    etl_benchmark.split.x_f__mutmut_1: killed\n"
        "    etl_benchmark.quality.ml.x_g__mutmut_1: survived\n"
        "    etl_benchmark.quality.xǁMLǁfit__mutmut_2: killed\n"
        "    etl_benchmark.load.x_h__mutmut_1: killed\n"
        "not a mutant line\n"
        "    other: killed\n"
    )
    assert claims.split_mutants(text, scope) == {
        "scientific_killed": 2,
        "scientific_total": 3,
        "other_killed": 1,
        "other_total": 1,
    }


def test_a_revision_that_is_not_a_commit_hash_or_a_source_that_is_unknown_is_rejected(tmp_path):
    root, _, doc = _valid(tmp_path)
    bad = copy.deepcopy(doc)
    bad["published_run"]["revision"] = "abc123"
    assert any("40-character" in p for p in _check(root, bad))
    bad = copy.deepcopy(doc)
    bad["published_run"]["source"] = "somebody's laptop"
    assert any("local-unattested or ci-run" in p for p in _check(root, bad))
    ci = copy.deepcopy(doc)
    ci["published_run"]["source"] = "ci-run:123"
    assert _check(root, ci) == []


def test_a_current_run_needs_its_evidence_directory_and_every_envelope(tmp_path):
    root, revision, doc = _valid(tmp_path)
    missing = copy.deepcopy(doc)
    del missing["published_run"]["evidence_dir"]
    assert any("evidence_dir" in p for p in _check(root, missing))
    path = root / doc["published_run"]["evidence_dir"] / "types.json"
    path.unlink()
    unsealed = _seal(root, _claims(root, revision))
    assert any("no types envelope" in p for p in _check(root, unsealed))


def test_a_run_whose_profile_did_not_pass_is_rejected(tmp_path):
    root, revision, doc = _valid(tmp_path)
    path = root / doc["published_run"]["evidence_dir"] / "faults.json"
    envelope = json.loads(path.read_text())
    envelope["status"] = "INCOMPLETE"
    path.write_text(json.dumps(envelope))
    sealed = _seal(root, _claims(root, revision))
    assert any("faults" in p and "INCOMPLETE" in p for p in _check(root, sealed))


def _command(monkeypatch, root):
    monkeypatch.setattr(claims, "ROOT", root)
    monkeypatch.setattr(claims, "CLAIMS", root / "claims.json")
    monkeypatch.setattr(claims.mutation_scope, "load", lambda: {"scientific": []})


def test_the_command_seals_a_run_and_then_checks_it(tmp_path, monkeypatch, capsys):
    root = _repo(tmp_path)
    revision = _git(root, "rev-parse", "HEAD")
    source = _run_dir(root, revision, name="staged")
    evidence = root / "in"
    evidence.mkdir()
    for path in source.glob("*.json"):
        (evidence / path.name).write_text(path.read_text())
    _command(monkeypatch, root)
    assert (
        claims.main(
            [
                "archive",
                "--id",
                "r1",
                "--platform",
                "p",
                "--evidence",
                str(evidence),
                "--results",
                str(source / "results.txt"),
            ]  # fmt: skip
        )
        == 0
    )
    assert f"sealed run r1 at {revision[:8]}" in capsys.readouterr().out
    monkeypatch.setattr(
        claims.evidence_schema,
        "collect_source",
        lambda: {"scientific_fingerprint": SOURCE["scientific_fingerprint"]},
    )
    (root / "paper").mkdir()
    (root / "paper" / "main.tex").write_text("no run named")
    assert claims.main(["check"]) == 1
    assert "names no run" in capsys.readouterr().out
    (root / "paper" / "main.tex").write_text(
        claims.paper_identity(json.loads((root / "claims.json").read_text()))
    )
    assert claims.main(["check"]) == 0
    assert "claims: PASS" in capsys.readouterr().out


def test_the_module_checks_the_repository_claims_from_the_command_line():
    import sys

    done = subprocess.run(
        [sys.executable, "-m", "verification.claims", "check", "--structure-only"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stdout
    assert "claims: PASS" in done.stdout


def test_fast_does_not_ask_whether_code_changed_since_the_run(tmp_path):
    root, _, doc = _valid(tmp_path)
    (root / "src/m.py").write_text("x = 2\n")
    _git(root, "commit", "-qam", "code")
    scope = {"scientific": ["src/etl_benchmark/split.py"]}
    fingerprint = SOURCE["scientific_fingerprint"]
    assert (
        claims.check_run(
            doc, root=root, scientific_fingerprint=fingerprint, scope=scope, current=False
        )
        == []
    )
    assert claims.check_run(doc, root=root, scientific_fingerprint=fingerprint, scope=scope)
