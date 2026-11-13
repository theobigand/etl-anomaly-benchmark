"""Each reason a published figure is not a faithful account of its run, stated alone and exactly."""

import json
import subprocess

import pytest

from verification import claims, evidence_schema

FINGERPRINT = "f" * 64
SCOPE = {"scientific": ["src/etl_benchmark/split.py", "research/"]}


def _git(root, *args):
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=True
    ).stdout.strip()


def _commit(root, message, files=None):
    for name, content in (files or {}).items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", message, "--allow-empty")
    return _git(root, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path):
    for command in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"]):
        _git(tmp_path, *command)
    return tmp_path


def _envelope(kind, revision, **result):
    results = {
        "fast": {
            "tests": {"total": 7},
            "coverage": {
                "line": {"covered": 90, "coverable": 100},
                "branch": {"covered": 8, "coverable": 10},
            },
        },
        "tools": {"coverage": {"line": {"covered": 50}, "branch": {"covered": 5}}},
        "deep": {"stats": {"killed": 3, "total": 5, "survived": 2}},
        "faults": {"faults": [{"d": 1}, {"d": 2}]},
    }.get(kind, {})
    return {
        "kind": kind,
        "status": "PASS",
        "source": {
            "revision": revision,
            "worktree_dirty": False,
            "scientific_fingerprint": FINGERPRINT,
        },
        "result": results,
    }


RESULTS = (
    "etl_benchmark.split.x_f__mutmut_1: killed\n"
    "etl_benchmark.split.x_f__mutmut_2: survived\n"
    "research.a.x_g__mutmut_1: killed\n"
    "tools.b.x_h__mutmut_1: killed\n"
    "tools.b.x_h__mutmut_2: timeout\n"
    "noise line\n"
    "etl_benchmark.config: killed\n"
)


def _sealed(repo, revision, name="run1", mutate=None):
    """Write a complete run directory and the claims that describe it."""
    directory = repo / "verification" / "evidence" / "runs" / name
    directory.mkdir(parents=True, exist_ok=True)
    for kind in claims.KINDS:
        doc = _envelope(kind, revision)
        if mutate:
            mutate(kind, doc)
        (directory / f"{kind}.json").write_text(json.dumps(doc))
    (directory / "results.txt").write_text(RESULTS)
    files = {p.name: claims._sha256(p) for p in sorted(directory.iterdir())}
    published = {
        "id": name,
        "revision": revision,
        "source": "local-unattested",
        "platform": "test",
        "captured": "2026-11-13",
        "historical": False,
        "evidence_dir": f"verification/evidence/runs/{name}",
        "files": files,
    }
    document = {"published_run": published, **claims.figures_from_run(directory, SCOPE)}
    return document, directory


def _check(doc, repo, **kwargs):
    kwargs.setdefault("scope", SCOPE)
    return claims.check_run(doc, root=repo, scientific_fingerprint=FINGERPRINT, **kwargs)


@pytest.fixture(autouse=True)
def _valid_envelopes(monkeypatch):
    monkeypatch.setattr(evidence_schema, "validate", lambda doc, root=None: [])


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("src/a.py", True),
        ("experiments/x.py", True),
        ("tests/t.py", True),
        (".github/w.yml", True),
        ("Makefile", True),
        ("pyproject.toml", True),
        ("environment.yml", True),
        ("verification/x.py", True),
        ("verification/release_policy.json", True),
        ("verification/mutation_scope.json", True),
        ("verification/mutation_risk_policy.json", True),
        ("verification/other.json", False),
        ("verification/sub/x.py", False),
        ("docs/a.md", False),
        ("README.md", False),
        ("research/a.py", False),
    ],
)
def test_only_files_that_can_change_what_a_run_measured_count_as_code(path, expected):
    assert claims.is_code(path) is expected


def test_a_module_is_scientific_when_named_by_its_file_or_by_a_directory_entry():
    scientific = ["src/etl_benchmark/split.py", "research/", "experiments"]
    assert claims._in_scientific("src/etl_benchmark/split", scientific) is True
    assert claims._in_scientific("research/a", scientific) is True
    assert claims._in_scientific("experiments/run", scientific) is True
    assert claims._in_scientific("experiments", scientific) is True
    assert claims._in_scientific("src/etl_benchmark/other", scientific) is False
    assert claims._in_scientific("researcher/a", scientific) is False
    assert claims._in_scientific("experimentsX/a", scientific) is False
    assert claims._in_scientific("anything", []) is False


def test_mutants_are_counted_as_scientific_or_other_and_only_killed_ones_as_killed():
    counts = claims.split_mutants(RESULTS, SCOPE)
    assert counts == {
        "scientific_killed": 2, "scientific_total": 3, "other_killed": 1, "other_total": 2,
    }  # fmt: skip
    padded = claims.split_mutants("  research.a.x_g__mutmut_1:   killed  \n", SCOPE)
    assert padded["scientific_killed"] == 1 and padded["scientific_total"] == 1
    assert claims.split_mutants("", SCOPE) == {
        "scientific_killed": 0, "scientific_total": 0, "other_killed": 0, "other_total": 0,
    }  # fmt: skip
    assert claims.split_mutants("a.b: killed\n", SCOPE)["other_total"] == 0


def test_the_manuscript_must_name_the_run_by_commit_and_attestation_whatever_the_line_breaks():
    doc = {"published_run": {"revision": "a" * 40, "source": "local-unattested"}}
    assert claims.paper_identity(doc) == f"commit {'a' * 8} (local run, not independently attested)"
    ci = {"published_run": {"revision": "b" * 40, "source": "ci-run:42"}}
    assert claims.paper_identity(ci) == f"commit {'b' * 8} (ci-run:42)"
    tex = f"see commit {'a' * 8}\n   (local run,\n not independently attested) here"
    assert claims.check_paper(doc, tex) == []
    assert claims.check_paper(doc, "nothing") == [
        f"the manuscript names no run: it must say {claims.paper_identity(doc)!r}"
    ]


def test_each_identity_field_and_the_revision_and_source_formats_are_checked_alone():
    full = {"revision": "a" * 40, "source": "local-unattested", "platform": "p", "captured": "d"}
    assert claims._check_identity(full) == []
    for key in claims.IDENTITY:
        broken = {**full, key: ""}
        assert f"published_run.{key} is missing" in claims._check_identity(broken)
    assert claims._check_identity({**full, "revision": "abc"}) == [
        "published_run.revision must be a 40-character commit hash"
    ]
    assert claims._check_identity({**full, "revision": "A" * 40}) == [
        "published_run.revision must be a 40-character commit hash"
    ]
    assert claims._check_identity({**full, "source": "ci-run:1"}) == []
    assert claims._check_identity({**full, "source": "elsewhere"}) == [
        "published_run.source must be local-unattested or ci-run:<id>"
    ]
    missing_source = {k: v for k, v in full.items() if k != "source"}
    assert claims._check_identity(missing_source) == ["published_run.source is missing"]


def test_an_envelope_must_pass_name_the_runs_revision_be_clean_and_match_the_fingerprint():
    ok = _envelope("fast", "a" * 40)
    assert claims._check_envelope("fast", ok, "a" * 40, FINGERPRINT) == []
    bad = _envelope("fast", "b" * 40)
    bad["status"] = "FAIL"
    bad["source"]["worktree_dirty"] = True
    bad["source"]["scientific_fingerprint"] = "0" * 64
    assert claims._check_envelope("fast", bad, "a" * 40, FINGERPRINT) == [
        "fast: status is FAIL",
        f"fast: revision {'b' * 8} is not the run's",
        "fast: produced from a dirty worktree",
        "fast: scientific fingerprint differs from the current source",
    ]
    assert (
        claims._check_envelope("fast", {}, "a" * 40, FINGERPRINT)[1]
        == "fast: revision None is not the run's"
    )


def test_the_figures_are_read_from_the_envelopes_and_the_mutant_listing(repo):
    revision = _commit(repo, "one")
    _, directory = _sealed(repo, revision)
    assert claims.figures_from_run(directory, SCOPE) == {
        "fast": {
            "tests": 7,
            "line_covered": 90,
            "line_coverable": 100,
            "branch_covered": 8,
            "branch_coverable": 10,
        },
        "verifier": {"line": 50, "branch": 5},
        "mutation": {
            "killed": 3,
            "total": 5,
            "survived": 2,
            "scientific_killed": 2,
            "scientific_total": 3,
            "other_killed": 1,
            "other_total": 2,
        },
        "faults": 2,
    }


def test_a_complete_faithful_run_has_no_problem_and_the_run_is_missing_or_unidentified_otherwise(
    repo,
):
    revision = _commit(repo, "one")
    doc, _ = _sealed(repo, revision)
    assert _check(doc, repo) == []
    assert _check({}, repo) == [
        "published_run is missing: the figures do not say which run they describe"
    ]
    assert _check({"published_run": "x"}, repo) == [
        "published_run is missing: the figures do not say which run they describe"
    ]
    broken = {"published_run": {**doc["published_run"], "revision": ""}}
    assert _check(broken, repo) == ["published_run.revision is missing"]


def test_a_revision_outside_the_history_is_named_by_its_first_eight_characters(repo):
    _commit(repo, "one")
    doc, _ = _sealed(repo, "1" * 40)
    assert _check(doc, repo) == [f"revision {'1' * 8} is not in the history of HEAD"]


def test_a_historical_run_needs_only_a_note_and_nothing_else_is_checked(repo):
    revision = _commit(repo, "one")
    historical = {
        "published_run": {**_sealed(repo, revision)[0]["published_run"], "historical": True}
    }
    assert _check(historical, repo) == ["a historical run needs a note saying why"]
    historical["published_run"]["note"] = "   "
    assert _check(historical, repo) == ["a historical run needs a note saying why"]
    historical["published_run"]["note"] = "kept for history"
    assert _check(historical, repo) == []


def test_a_run_needs_an_existing_evidence_directory_with_every_sealed_file_intact(repo):
    revision = _commit(repo, "one")
    doc, directory = _sealed(repo, revision)
    gone = {**doc, "published_run": {**doc["published_run"], "evidence_dir": "nowhere"}}
    assert _check(gone, repo) == ["the run has no evidence_dir with its envelopes"]
    none = {
        **doc,
        "published_run": {k: v for k, v in doc["published_run"].items() if k != "evidence_dir"},
    }
    assert _check(none, repo) == ["the run has no evidence_dir with its envelopes"]
    (directory / "fast.json").write_text("{}")
    (directory / "tools.json").unlink()
    problems = _check(doc, repo)
    assert "run file fast.json hash differs from the sealed one" in problems
    assert "run file tools.json is missing" in problems
    assert len(problems) == 2


def test_every_kind_must_be_among_the_sealed_files(repo):
    revision = _commit(repo, "one")
    doc, _ = _sealed(repo, revision)
    del doc["published_run"]["files"]["deep.json"]
    assert _check(doc, repo) == ["the run has no deep envelope"]
    no_files = {"published_run": {**doc["published_run"], "files": {}}}
    assert _check(no_files, repo) == [f"the run has no {kind} envelope" for kind in claims.KINDS]


def test_each_envelope_is_validated_and_checked_against_the_run(repo, monkeypatch):
    revision = _commit(repo, "one")
    doc, _ = _sealed(
        repo, revision, mutate=lambda kind, d: d.update(status="FAIL") if kind == "real" else None
    )
    assert _check(doc, repo) == ["real: status is FAIL"]
    monkeypatch.setattr(
        evidence_schema,
        "validate",
        lambda envelope, root=None: ["odd"] if envelope["kind"] == "faults" else [],
    )
    clean, _ = _sealed(repo, revision, name="run2")
    assert _check(clean, repo) == ["faults: odd"]


def test_code_changed_since_the_run_makes_its_figures_stale_unless_currency_is_not_asked(repo):
    revision = _commit(repo, "one")
    doc, _ = _sealed(repo, revision)
    _commit(repo, "docs", {"docs/a.md": "x"})
    assert _check(doc, repo) == []
    _commit(repo, "code", {"src/x.py": "x = 1\n", "verification/y.py": "y = 1\n"})
    assert _check(doc, repo) == [
        "src/x.py changed since the run, so its figures may be stale",
        "verification/y.py changed since the run, so its figures may be stale",
    ]
    assert _check(doc, repo, current=False) == []


def test_a_figure_that_differs_from_the_run_is_reported_with_both_values(repo):
    revision = _commit(repo, "one")
    doc, _ = _sealed(repo, revision)
    doc["fast"]["tests"] = 8
    del doc["verifier"]
    doc["faults"] = 3
    problems = _check(doc, repo)
    assert "fast.tests is 8 in the claims but 7 in the run" in problems
    assert "verifier.line is None in the claims but 50 in the run" in problems
    assert "verifier.branch is None in the claims but 5 in the run" in problems
    assert "faults is 3 in the claims but 2 in the run" in problems
    assert len(problems) == 4


def test_archiving_copies_the_envelopes_and_seals_the_claims_on_them(repo):
    revision = _commit(repo, "one")
    evidence = repo / "ev"
    evidence.mkdir()
    for kind in claims.KINDS:
        (evidence / f"{kind}.json").write_text(json.dumps(_envelope(kind, revision)))
    results = repo / "r.txt"
    results.write_text(RESULTS)
    claims_path = repo / "claims.json"
    claims_path.write_text(json.dumps({"keep": "me", "schema_version": 1}))
    doc = claims.archive(
        run_id="r1", source_label="local-unattested", platform="mac", evidence=evidence,
        results=results, root=repo, claims_path=claims_path, scope=SCOPE, captured="2026-11-13",
    )  # fmt: skip
    target = repo / claims.RUNS / "r1"
    assert sorted(p.name for p in target.iterdir()) == sorted(
        [*(f"{k}.json" for k in claims.KINDS), "results.txt"]
    )
    assert (target / "results.txt").read_text() == RESULTS
    assert doc["keep"] == "me" and doc["schema_version"] == 2
    run = doc["published_run"]
    assert run["id"] == "r1" and run["revision"] == revision and run["source"] == "local-unattested"
    assert (
        run["platform"] == "mac" and run["captured"] == "2026-11-13" and run["historical"] is False
    )
    assert run["evidence_dir"] == f"{claims.RUNS}/r1"
    assert run["files"] == {p.name: claims._sha256(p) for p in sorted(target.iterdir())}
    assert doc["faults"] == 2 and doc["mutation"]["killed"] == 3
    assert claims_path.read_text() == json.dumps(doc, indent=2) + "\n"
    assert _check(doc, repo) == []


def test_archiving_without_a_claims_file_starts_one_and_refuses_envelopes_of_different_revisions(
    repo,
):
    revision = _commit(repo, "one")
    evidence = repo / "ev"
    evidence.mkdir()
    for kind in claims.KINDS:
        (evidence / f"{kind}.json").write_text(json.dumps(_envelope(kind, revision)))
    results = repo / "r.txt"
    results.write_text(RESULTS)
    fresh = repo / "new" / "claims.json"
    fresh.parent.mkdir()
    doc = claims.archive(
        run_id="r2", source_label="ci-run:9", platform="p", evidence=evidence, results=results,
        root=repo, claims_path=fresh, scope=SCOPE, captured="d",
    )  # fmt: skip
    assert doc["schema_version"] == 2 and doc["published_run"]["source"] == "ci-run:9"
    (evidence / "faults.json").write_text(json.dumps(_envelope("faults", "9" * 40)))
    with pytest.raises(ValueError) as refused:
        claims.archive(
            run_id="r3", source_label="x", platform="p", evidence=evidence, results=results,
            root=repo, claims_path=fresh, scope=SCOPE, captured="d",
        )  # fmt: skip
    assert (
        str(refused.value)
        == f"the envelopes come from different revisions: {sorted([revision, '9' * 40])}"
    )
    assert not (repo / claims.RUNS / "r3").exists()


def _wire(monkeypatch, tmp_path, problems_run=(), problems_paper=()):
    seen = {}
    monkeypatch.setattr(claims, "ROOT", tmp_path)
    monkeypatch.setattr(claims, "CLAIMS", tmp_path / "claims.json")
    monkeypatch.setattr(claims.mutation_scope, "load", lambda: {"scientific": []})
    monkeypatch.setattr(claims, "load", lambda path=None: {"published_run": {}})
    monkeypatch.setattr(
        evidence_schema, "collect_source", lambda: {"scientific_fingerprint": FINGERPRINT}
    )

    def check_run(doc, **kwargs):
        seen.update(run=kwargs)
        return list(problems_run)

    monkeypatch.setattr(claims, "check_run", check_run)
    monkeypatch.setattr(claims, "check_paper", lambda doc, tex: list(problems_paper))
    (tmp_path / "paper").mkdir(exist_ok=True)
    (tmp_path / "paper" / "main.tex").write_text("tex")
    return seen


def test_the_check_command_prints_each_problem_then_pass_or_fail(tmp_path, monkeypatch, capsys):
    seen = _wire(monkeypatch, tmp_path)
    assert claims.main(["check"]) == 0
    assert capsys.readouterr().out == "claims: PASS\n"
    assert seen["run"]["root"] == tmp_path and seen["run"]["current"] is True
    assert seen["run"]["scientific_fingerprint"] == FINGERPRINT and seen["run"]["scope"] == {
        "scientific": []
    }
    _wire(monkeypatch, tmp_path, problems_run=["run p"], problems_paper=["paper p"])
    assert claims.main(["check"]) == 1
    assert capsys.readouterr().out == "claims: run p\nclaims: paper p\nclaims: FAIL\n"


def test_the_structure_only_option_skips_the_currency_check(tmp_path, monkeypatch):
    seen = _wire(monkeypatch, tmp_path)
    assert claims.main(["check", "--structure-only"]) == 0
    assert seen["run"]["current"] is False


def test_the_archive_command_seals_a_run_and_reports_its_short_revision(
    tmp_path, monkeypatch, capsys
):
    seen = {}
    monkeypatch.setattr(claims, "ROOT", tmp_path)
    monkeypatch.setattr(claims, "CLAIMS", tmp_path / "claims.json")
    monkeypatch.setattr(claims.mutation_scope, "load", lambda: {"s": 1})
    monkeypatch.setattr(
        claims,
        "archive",
        lambda **kw: seen.update(kw) or {"published_run": {"revision": "d" * 40}},
    )
    argv = ["archive", "--id", "r9", "--platform", "mac"]
    assert claims.main(argv) == 0
    assert capsys.readouterr().out == f"sealed run r9 at {'d' * 8}\n"
    assert seen["run_id"] == "r9" and seen["source_label"] == "local-unattested"
    assert seen["platform"] == "mac" and seen["root"] == tmp_path and seen["scope"] == {"s": 1}
    assert seen["evidence"] == tmp_path / "experiments/results/evidence"
    assert seen["results"] == tmp_path / "mutants/results.txt"
    assert seen["claims_path"] == tmp_path / "claims.json" and len(seen["captured"]) == 10
    claims.main([*argv, "--source", "ci-run:3", "--evidence", "e", "--results", "r"])
    assert seen["source_label"] == "ci-run:3"
    assert seen["evidence"].name == "e" and seen["results"].name == "r"


def test_the_commands_are_required_and_described(capsys):
    with pytest.raises(SystemExit) as stop:
        claims.main([])
    assert stop.value.code == 2
    with pytest.raises(SystemExit) as stop:
        claims.main(["archive", "--platform", "p"])
    assert stop.value.code == 2
    with pytest.raises(SystemExit) as stop:
        claims.main(["archive", "--id", "x"])
    assert stop.value.code == 2
    capsys.readouterr()
    with pytest.raises(SystemExit):
        claims.main(["--help"])
    text = " ".join(capsys.readouterr().out.split())
    assert "check claims.json against its run and the manuscript" in text
    assert "seal a finished run into the repository" in text
    with pytest.raises(SystemExit):
        claims.main(["check", "--help"])
    assert "do not ask whether code changed since the run (the release gate does)" in " ".join(
        capsys.readouterr().out.split()
    )
