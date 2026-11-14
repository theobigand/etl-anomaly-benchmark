"""Every refusal of the mutation policy states its own reason, and each condition acts alone."""

import copy
import hashlib
import json
from pathlib import PurePosixPath

import pytest

from verification import mutation_policy as mp

PATH = "pkg/a.py"
KEY = "pkg.a.x_f__mutmut_1"
OWNER = "the-owner"
SOURCE = "0" * 64


def _policy(**units):
    return {
        "version": 2,
        "thresholds": dict(mp.THRESHOLDS),
        "governance": {"review_mode": mp.REVIEW_MODE, "owner": OWNER},
        "roots": ["pkg"],
        "units": units or {PATH: {"level": "L4", "reason": "why"}},
    }


def _edit(change):
    policy = copy.deepcopy(_policy())
    change(policy)
    return policy


def _refused(call, message):
    with pytest.raises(ValueError) as refused:
        call()
    assert str(refused.value) == message


DECLARATIONS = [
    (lambda p: p.update(version=3), "mutation risk policy version must be 2"),
    (lambda p: p.update(version=True), "mutation risk policy version must be 2"),
    (lambda p: p.pop("version"), "mutation risk policy version must be 2"),
    (lambda p: p["thresholds"].update(L4=97), "thresholds must be L1=80 L2=90 L3=95 L4=98"),
    (lambda p: p["thresholds"].update(L4=98.0), "thresholds must be L1=80 L2=90 L3=95 L4=98"),
    (lambda p: p.update(governance="x"), "invalid governance declaration"),
    (lambda p: p["governance"].pop("owner"), "invalid governance declaration"),
    (lambda p: p["governance"].update(extra=1), "invalid governance declaration"),
    (lambda p: p["governance"].update(review_mode="other"), "invalid governance declaration"),
    (lambda p: p["governance"].update(owner="  "), "invalid governance declaration"),
    (lambda p: p.update(roots="pkg"), "policy roots must be a nonempty path list"),
    (lambda p: p.update(roots=[]), "policy roots must be a nonempty path list"),
    (lambda p: p.update(roots=["pkg", 3]), "policy roots must be a nonempty path list"),
    (
        lambda p: p.update(roots=["pkg", "pkg"]),
        "policy roots must be unique and units must be nonempty",
    ),
    (lambda p: p.update(units=[1]), "policy roots must be unique and units must be nonempty"),
    (lambda p: p.update(units={}), "policy roots must be unique and units must be nonempty"),
    (
        lambda p: p["units"].update({"other/b.py": {"level": "L1", "reason": "r"}}),
        "classification lies outside the policy roots: other/b.py",
    ),
    (lambda p: p["units"].update({PATH: "L4"}), f"invalid risk level for {PATH}"),
    (lambda p: p["units"][PATH].update(level=4), f"invalid risk level for {PATH}"),
    (lambda p: p["units"][PATH].update(level="L9"), f"invalid risk level for {PATH}"),
    (lambda p: p["units"][PATH].pop("reason"), f"classification for {PATH} requires a reason"),
    (lambda p: p["units"][PATH].update(reason=" "), f"classification for {PATH} requires a reason"),
    (lambda p: p["units"][PATH].update(reason=3), f"classification for {PATH} requires a reason"),
    (
        lambda p: p["units"][PATH].update(no_mutants=""),
        f"technical exclusion for {PATH} requires a reason",
    ),
    (
        lambda p: p["units"][PATH].update(no_mutants=7),
        f"technical exclusion for {PATH} requires a reason",
    ),
]


@pytest.mark.parametrize(("change", "message"), DECLARATIONS)
def test_each_declaration_fault_alone_is_refused_with_its_own_reason(change, message):
    _refused(lambda: mp._validate_declarations(_edit(change)), message)


def test_a_policy_with_a_governance_block_a_technical_reason_and_no_governance_is_accepted():
    mp._validate_declarations(_policy())
    plain = _policy()
    plain.pop("governance")
    mp._validate_declarations(plain)
    technical = _policy()
    technical["units"][PATH]["no_mutants"] = "constants only"
    mp._validate_declarations(technical)


@pytest.mark.parametrize("name", ["", "a\\b", "/abs", "a/./b", "a/../b", "a//b", "a/", 5, None])
def test_a_path_that_is_not_canonical_and_relative_is_refused(name):
    _refused(lambda: mp._canonical_name(name), "policy paths must be canonical relative paths")


def test_a_canonical_relative_path_is_returned_as_a_posix_path():
    assert mp._canonical_name("a/b.py") == PurePosixPath("a/b.py")
    assert mp._canonical_name("a") == PurePosixPath("a")


@pytest.mark.parametrize(
    ("key", "message"),
    [
        (5, "mutant identity does not belong to its source module"),
        ("other.a.x_f__mutmut_1", "mutant identity does not belong to its source module"),
        ("pkg.ax_f__mutmut_1", "mutant identity does not belong to its source module"),
        ("pkg.a.x_f", "invalid mutant identity"),
        ("pkg.a.__mutmut_1", "invalid native mutant function identity"),
        ("pkg.a.x_f__mutmut_", "invalid mutant identity"),
        ("pkg.a.x_f__mutmut_x", "invalid mutant identity"),
        ("pkg.a.x_f__mutmut_0", "invalid mutant identity"),
        ("pkg.a.y_f__mutmut_1", "invalid native mutant function identity"),
        ("pkg.a.xǁAǁ__mutmut_1", "invalid native mutant function identity"),
        ("pkg.a.xǁAǁm__mutmut_1".replace("x", "z", 1), "invalid native mutant function identity"),
        ("pkg.a.xǁA.1ǁm__mutmut_1", "invalid native mutant function identity"),
        ("pkg.a.xǁAǁ1m__mutmut_1", "invalid native mutant function identity"),
        ("pkg.a.xǁAǁm1ǁz__mutmut_1", "invalid native mutant function identity"),
        ("pkg.a.xǁAǁmǁ__mutmut_1", "invalid native mutant function identity"),
    ],
)
def test_a_mutant_identity_must_match_the_native_naming_exactly(key, message):
    _refused(lambda: mp._identity(key, PATH), message)


@pytest.mark.parametrize(
    "key",
    [
        "pkg.a.x_f__mutmut_1",
        "pkg.a.x_f__mutmut_12",
        "pkg.a.xǁAǁm__mutmut_3",
        "pkg.a.xǁA.Bǁm__mutmut_3",
    ],
)
def test_well_formed_identities_are_accepted(key):
    mp._identity(key, PATH)
    mp._identity(
        "pkg.__init__.x_f__mutmut_1".replace("__init__", "sub"), "pkg/sub/__init__.py"
    ) if False else None


def test_an_init_module_is_named_after_its_package_and_src_is_dropped():
    assert mp._module("src/pkg/a.py") == "pkg.a"
    assert mp._module("src/pkg/__init__.py") == "pkg"
    assert mp._module("pkg/sub/b.py") == "pkg.sub.b"
    mp._identity("pkg.x_f__mutmut_1", "src/pkg/__init__.py")


def test_the_digests_are_canonical_and_the_policy_digest_refuses_non_finite_numbers():
    assert mp.catalog_digest(["b", "a"]) == hashlib.sha256(b'["a","b"]').hexdigest()
    assert mp.catalog_digest([]) == hashlib.sha256(b"[]").hexdigest()
    policy = {"b": 1, "a": [1, 2]}
    assert mp.policy_digest(policy) == hashlib.sha256(b'{"a":[1,2],"b":1}').hexdigest()
    with pytest.raises(ValueError):
        mp.policy_digest({"x": float("nan")})


def _snapshot(policy=None, catalog=None, records=None, sources=None, equivalence=None, env=None):
    policy = policy or _policy()
    catalog = {PATH: [KEY]} if catalog is None else catalog
    records = [{"id": KEY, "path": PATH, "outcome": "survived"}] if records is None else records
    sources = {PATH: SOURCE} if sources is None else sources
    return mp.evaluate_snapshot(policy, sources, catalog, records, equivalence, env)


SNAPSHOT_FAULTS = [
    ({"sources": {}}, "recorded sources must map every classified unit to its SHA-256"),
    ({"sources": {PATH: "xyz"}}, "recorded sources must map every classified unit to its SHA-256"),
    ({"sources": {PATH: 5}}, "recorded sources must map every classified unit to its SHA-256"),
    (
        {"sources": {PATH: SOURCE.upper().replace("0", "A")}},
        "recorded sources must map every classified unit to its SHA-256",
    ),
    ({"sources": "text"}, "recorded sources must map every classified unit to its SHA-256"),
    ({"catalog": []}, "catalog must be a mapping and records a list"),
    ({"records": {}}, "catalog must be a mapping and records a list"),
    ({"catalog": {"pkg/z.py": []}}, "catalog contains unclassified modules"),
    ({"catalog": {PATH: "x"}}, "catalog identities must be lists"),
    ({"catalog": {PATH: [KEY, KEY]}}, "duplicate or technically excluded mutant identity"),
    ({"records": [{"id": KEY}]}, "invalid mutant record shape"),
    ({"records": ["x"]}, "invalid mutant record shape"),
    (
        {"records": [{"id": KEY, "path": PATH, "outcome": "survived"}] * 2},
        "duplicate or unknown mutant record",
    ),
    (
        {"records": [{"id": "pkg.a.x_g__mutmut_1", "path": PATH, "outcome": "killed"}]},
        "duplicate or unknown mutant record",
    ),
    (
        {"records": [{"id": 3, "path": PATH, "outcome": "killed"}]},
        "duplicate or unknown mutant record",
    ),
    (
        {"records": [{"id": KEY, "path": "pkg/b.py", "outcome": "killed"}]},
        "mutant path or outcome differs from catalog",
    ),
    (
        {"records": [{"id": KEY, "path": PATH, "outcome": "bogus"}]},
        "mutant path or outcome differs from catalog",
    ),
]


@pytest.mark.parametrize(("arguments", "message"), SNAPSHOT_FAULTS)
def test_each_snapshot_fault_alone_is_refused_with_its_own_reason(arguments, message):
    _refused(lambda: _snapshot(**arguments), message)


def test_a_module_declared_without_mutants_cannot_hold_an_identity():
    policy = _policy()
    policy["units"][PATH]["no_mutants"] = "constants only"
    _refused(lambda: _snapshot(policy=policy), "duplicate or technically excluded mutant identity")


def test_a_level_holding_only_a_technical_module_is_not_applicable_and_the_total_counts_all():
    policy = _policy(
        **{
            PATH: {"level": "L4", "reason": "r"},
            "pkg/c.py": {"level": "L3", "reason": "r", "no_mutants": "constants"},
        }
    )
    result = _snapshot(policy=policy, catalog={PATH: [KEY], "pkg/c.py": []},
                       sources={PATH: SOURCE, "pkg/c.py": SOURCE})  # fmt: skip
    assert result["levels"]["L3"]["status"] == "NOT_APPLICABLE"
    assert result["levels"]["L4"]["status"] == "FAIL"
    assert result["modules"]["pkg/c.py"]["status"] == "NO_MUTANTS_TECHNICAL"
    assert result["modules"]["pkg/c.py"]["exclusions"] == ["constants"]
    assert result["total"]["eligible"] == 1 and result["total"]["adjusted_eligible"] == 1
    assert result["total"]["equivalent_accepted"] == 0 and "threshold" not in result["total"]
    assert result["status"] == "FAIL"


def _record(**change):
    base = {
        "id": KEY, "path": PATH, "function": "f", "diff": "d", "original_behavior": "o",
        "mutated_behavior": "m", "risk": "L4", "reason": "r", "source_sha256": SOURCE,
        "catalog_sha256": mp.catalog_digest([KEY]), "author": "a", "evidence": ["e"],
        "verdict": "accepted", "approver": OWNER, "decision_date": "2026-11-11",
        "policy_version": 2, "environment": {"pandas": "3.0.6"}, "assessments": [],
    }  # fmt: skip
    base.update(change)
    return base


def _document(*items):
    return {"version": 2, "review_mode": mp.REVIEW_MODE, "owner": OWNER, "records": list(items)}


def _accepted(document, governance=None, environment=None, outcome="survived"):
    return mp.accepted_equivalents(
        document,
        {PATH: {"level": "L4"}},
        {PATH: SOURCE},
        {PATH: [KEY]},
        [{"id": KEY, "outcome": outcome}],
        governance if governance is not None else {"review_mode": mp.REVIEW_MODE, "owner": OWNER},
        environment if environment is not None else {"pandas": "3.0.6"},
    )


RECORD_FAULTS = [
    (_record(extra=1), "invalid equivalence record shape"),
    ({k: v for k, v in _record().items() if k != "diff"}, "invalid equivalence record shape"),
    ("x", "invalid equivalence record shape"),
    (_record(diff=""), "equivalence record fields must be nonempty text"),
    (_record(author=3), "equivalence record fields must be nonempty text"),
    (_record(evidence="e"), "equivalence record needs supporting evidence"),
    (_record(evidence=[]), "equivalence record needs supporting evidence"),
    (_record(evidence=[" "]), "equivalence record needs supporting evidence"),
    (_record(assessments="x"), "invalid equivalence assessments"),
    (_record(assessments=["x"]), "invalid equivalence assessments"),
    (
        _record(assessments=[{"assessor": "a", "verdict": "ACCEPT"}]),
        "invalid equivalence assessments",
    ),
    (
        _record(assessments=[{"assessor": " ", "verdict": "ACCEPT", "note": "n"}]),
        "invalid equivalence assessments",
    ),
    (
        _record(assessments=[{"assessor": "a", "verdict": "accept", "note": "n"}]),
        "invalid equivalence assessments",
    ),
    (
        _record(assessments=[{"assessor": "a", "verdict": "ACCEPT", "note": ""}]),
        "invalid equivalence assessments",
    ),
    (_record(id="pkg.a.x_g__mutmut_1"), "duplicate or unknown equivalence identity"),
    (_record(path="pkg/b.py"), "duplicate or unknown equivalence identity"),
    (_record(verdict="approved"), "invalid equivalence verdict"),
    (_record(approver="someone"), "an equivalence decision must be recorded by the declared owner"),
    (_record(decision_date="not a date"), "equivalence decision date must be ISO 8601"),
    (_record(decision_date=None), "equivalence decision date must be ISO 8601"),
    (
        _record(verdict="proposed", approver=OWNER, decision_date=""),
        "a proposed equivalence must not carry an approver or decision date",
    ),
    (
        _record(verdict="proposed", approver="", decision_date="2026-11-11"),
        "a proposed equivalence must not carry an approver or decision date",
    ),
    (
        _record(policy_version=1),
        "equivalence record does not match the policy version or risk level",
    ),
    (_record(risk="L3"), "equivalence record does not match the policy version or risk level"),
    (
        _record(source_sha256="1" * 64),
        "equivalence record is stale for the current source or catalog",
    ),
    (
        _record(catalog_sha256="1" * 64),
        "equivalence record is stale for the current source or catalog",
    ),
    (
        _record(environment="x"),
        "equivalence record must state the dependency versions it relies on",
    ),
    (_record(environment={}), "equivalence record must state the dependency versions it relies on"),
    (
        _record(environment={"": "1"}),
        "equivalence record must state the dependency versions it relies on",
    ),
    (
        _record(environment={"pandas": " "}),
        "equivalence record must state the dependency versions it relies on",
    ),
]


@pytest.mark.parametrize(("item", "message"), RECORD_FAULTS)
def test_each_record_fault_alone_is_refused_with_its_own_reason(item, message):
    _refused(lambda: _accepted(_document(item)), message)


def test_the_four_verdicts_are_validated_but_only_an_accepted_survivor_excludes_a_mutant():
    assert _accepted(_document(_record())) == {PATH: {KEY}}
    for verdict in ("rejected", "inconclusive"):
        assert _accepted(_document(_record(verdict=verdict))) == {}
    proposed = _record(verdict="proposed", approver="", decision_date="")
    assert _accepted(_document(proposed)) == {}
    assert _accepted(None) == {}
    reject = {"assessor": "a", "verdict": "REJECT", "note": "n"}
    assert _accepted(_document(_record(assessments=[reject]))) == {PATH: {KEY}}


def test_a_proposed_record_may_name_a_mutant_that_no_longer_survives_and_any_environment():
    proposed = _record(verdict="proposed", approver="", decision_date="")
    assert _accepted(_document(proposed), outcome="killed", environment={"pandas": "9"}) == {}
    inconclusive = _record(verdict="inconclusive")
    assert _accepted(_document(inconclusive), outcome="killed", environment={}) == {}


def test_a_killed_or_absent_or_foreign_environment_blocks_an_accepted_record():
    _refused(
        lambda: _accepted(_document(_record()), outcome="killed"),
        "only a surviving mutant can be accepted as equivalent",
    )
    for environment in ({"pandas": "9"}, {"numpy": "1"}):
        _refused(
            lambda e=environment: _accepted(_document(_record()), environment=e),
            "equivalence record is incompatible with the campaign environment",
        )
    _refused(
        lambda: mp.accepted_equivalents(
            _document(_record()), {PATH: {"level": "L4"}}, {PATH: SOURCE}, {PATH: [KEY]},
            [{"id": KEY, "outcome": "survived"}],
            {"review_mode": mp.REVIEW_MODE, "owner": OWNER},
            None,
        ),
        "equivalence record is incompatible with the campaign environment",
    )  # fmt: skip


@pytest.mark.parametrize(
    "governance",
    [
        None,
        "x",
        {"owner": OWNER},
        {"review_mode": "other", "owner": OWNER},
        {"review_mode": mp.REVIEW_MODE, "owner": " "},
    ],
)
def test_an_equivalence_document_needs_a_declared_owner_review_mode(governance):
    _refused(
        lambda: mp.accepted_equivalents(_document(), {}, {}, {}, [], governance, {}),
        "the policy does not declare the sole-author owner review mode",
    )


@pytest.mark.parametrize(
    "document",
    [
        "x",
        {"version": 2, "review_mode": mp.REVIEW_MODE, "owner": OWNER},
        {"version": 1, "review_mode": mp.REVIEW_MODE, "owner": OWNER, "records": []},
        {"version": 2, "review_mode": mp.REVIEW_MODE, "owner": OWNER, "records": "x"},
    ],
)
def test_an_equivalence_document_must_be_version_two_with_a_record_list(document):
    _refused(
        lambda: _accepted(document),
        "equivalence document must be version 2 with a record list",
    )


@pytest.mark.parametrize("change", [{"review_mode": "other"}, {"owner": "someone"}])
def test_the_document_must_name_the_declared_mode_and_owner(change):
    _refused(
        lambda: _accepted({**_document(), **change}),
        "equivalence document does not match the declared review mode and owner",
    )


def test_a_duplicate_record_is_refused_and_the_document_is_a_plain_json_value():
    _refused(
        lambda: _accepted(_document(_record(), _record())),
        "duplicate or unknown equivalence identity",
    )
    json.dumps(_document(_record()))


def test_the_evidence_tree_ignores_test_folders_and_bytecode_and_names_every_difference(tmp_path):
    (tmp_path / "pkg" / "tests").mkdir(parents=True)
    (tmp_path / "pkg" / "__pycache__").mkdir()
    (tmp_path / "pkg" / "a.py").write_text("X = 1\n")
    (tmp_path / "pkg" / "tests" / "t.py").write_text("def test(): pass\n")
    (tmp_path / "pkg" / "__pycache__" / "c.py").write_text("")
    (tmp_path / "pkg" / "z.py").write_text("Y = 2\n")
    policy = _policy(
        **{PATH: {"level": "L4", "reason": "r"}, "pkg/z.py": {"level": "L4", "reason": "r"}}
    )
    mp.validate_policy(policy, tmp_path)
    missing = _policy(**{PATH: {"level": "L4", "reason": "r"}})
    _refused(
        lambda: mp.validate_policy(missing, tmp_path),
        "unclassified sources: ['pkg/z.py']; stale classifications: []",
    )
    entry = {"level": "L4", "reason": "r"}
    stale = _policy(**{PATH: entry, "pkg/z.py": entry, "pkg/gone.py": entry})
    _refused(
        lambda: mp.validate_policy(stale, tmp_path),
        "unclassified sources: []; stale classifications: ['pkg/gone.py']",
    )
    absent = _policy()
    absent["roots"] = ["pkg", "nowhere"]
    _refused(lambda: mp.validate_policy(absent, tmp_path), "policy root does not exist: nowhere")


def test_a_technical_exclusion_may_not_hide_a_function(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "a.py").write_text("def f():\n    return 1\n")
    policy = _policy(**{PATH: {"level": "L4", "reason": "r", "no_mutants": "constants"}})
    _refused(
        lambda: mp.validate_policy(policy, tmp_path),
        f"technical no-mutant declaration contains functions: {PATH}",
    )
    (tmp_path / "pkg" / "a.py").write_text("X = 1\n")
    mp.validate_policy(policy, tmp_path)
