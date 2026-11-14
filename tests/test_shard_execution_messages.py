"""Exact refusal messages and reported fields of the shard execution proof."""

from __future__ import annotations

import json

import pytest

from tests.test_shard_execution_binding import MODULE, _build, _setup
from tests.test_shard_execution_binding import _tool_versions as _tool_versions  # noqa: F401
from verification import mutation_cache
from verification import mutation_shards as shards


def _refuse(tmp_path, mutate=None, names=("pkg.a.*",), reseal=True, raw=None):
    policy, document, attempt = _setup(tmp_path, names=names)
    record = json.loads(attempt.read_text())
    proof = record["proof"]
    if mutate:
        mutate(record, proof)
    if reseal:
        proof["sha256"] = mutation_cache._digest(
            {key: value for key, value in proof.items() if key != "sha256"}
        )
        record["admission"]["context_sha256"] = mutation_cache._digest(proof["context"])
    attempt.write_text(json.dumps(record) if raw is None else raw)
    with pytest.raises(ValueError) as refused:
        _build(tmp_path, policy, document, attempt)
    return str(refused.value)


def _command(record, proof, command):
    proof["context"]["runtime"]["native_command"] = command


def test_each_refusal_states_its_exact_reason(tmp_path):
    cases = {
        "invalid attempt record": dict(raw=json.dumps({"proof": {}})),
        "execution proof digest differs from its content": dict(
            mutate=lambda r, p: p.__setitem__("settled", 99), reseal=False
        ),
        "attempt admission does not match the execution proof": dict(
            mutate=lambda r, p: r["admission"].__setitem__("context_sha256", "0" * 64),
            reseal=False,
        ),
        "native log differs from the attempt record": dict(
            mutate=lambda r, p: r.__setitem__("native_log_sha256", "0" * 64), reseal=False
        ),
        "execution proof does not describe this shard's native run": dict(
            mutate=lambda r, p: p.__setitem__("native_exit_code", 7)
        ),
        "execution proof is stale for the shard sources": dict(
            mutate=lambda r, p: p["context"]["sources"][MODULE].__setitem__("sha256", "0" * 64)
        ),
        "execution proof does not bind the shard verdict metadata": dict(
            mutate=lambda r, p: p["metadata_sha256"].__setitem__(f"{MODULE}.meta", "0" * 64)
        ),
    }
    for index, (message, arguments) in enumerate(cases.items()):
        folder = tmp_path / str(index)
        folder.mkdir()
        assert _refuse(folder, **arguments) == message


@pytest.mark.parametrize(
    "edit",
    [
        lambda command: None,
        lambda command: command[:6],
        lambda command: command[:6] + ["x"] + command[7:],
        lambda command: command[:1] + ["-m"] + command[2:],
    ],
    ids=["not a list", "no worker count", "non numeric worker count", "wrong prefix"],
)
def test_a_native_command_of_the_wrong_shape_is_never_accepted(tmp_path, edit):
    policy, document, attempt = _setup(tmp_path)
    original = json.loads(attempt.read_text())["proof"]["context"]["runtime"]["native_command"]

    def mutate(record, proof):
        proof["context"]["runtime"]["native_command"] = edit(list(original))

    folder = tmp_path / "case"
    folder.mkdir()
    assert _refuse(folder, mutate) == "execution proof does not describe this shard's native run"


def test_the_shard_summary_reports_the_digests_runtime_and_metadata_it_verified(tmp_path):
    policy, document, attempt = _setup(tmp_path)
    summary = _build(tmp_path, policy, document, attempt)["execution"]
    proof = json.loads(attempt.read_text())["proof"]
    context = proof["context"]
    assert summary["context_sha256"] == mutation_cache._digest(context)
    assert summary["tests_sha256"] == mutation_cache._digest(context["tests"])
    assert summary["dependencies_sha256"] == mutation_cache._digest(context["dependencies"])
    assert summary["metadata_sha256"] == {
        f"{MODULE}.meta": proof["metadata_sha256"][f"{MODULE}.meta"]
    }
    assert None not in summary["metadata_sha256"].values()
    assert summary["runtime"]["packages"] == {
        name: context["runtime"]["packages"].get(name) for name in shards.PACKAGES
    }


def test_a_runtime_without_packages_reports_each_package_as_unknown(tmp_path):
    def mutate(record, proof):
        proof["context"]["runtime"].pop("packages", None)

    policy, document, attempt = _setup(tmp_path, mutate=mutate)
    summary = _build(tmp_path, policy, document, attempt)["execution"]
    assert summary["runtime"]["packages"] == dict.fromkeys(shards.PACKAGES)


def test_the_digest_is_canonical_and_refuses_non_finite_numbers():
    import hashlib

    assert shards._digest({"b": 1, "a": [1, 2]}) == hashlib.sha256(b'{"a":[1,2],"b":1}').hexdigest()
    with pytest.raises(ValueError):
        shards._digest({"x": float("nan")})
    with pytest.raises(ValueError):
        shards._digest(float("inf"))
