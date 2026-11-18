"""One canonical dependency environment for every release profile.

These checks fail before an expensive mutation campaign starts if a profile can resolve its own
packages, if the locks disagree with each other, or if an equivalence record binds a dependency
version that is not the canonical one.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from verification import real_preflight, release

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / "verification" / "environment"
WORKFLOWS = ROOT / ".github" / "workflows"
EXTRAS = ENV / "linux-x86_64-py311.extras.lock.txt"


def _pins(path: Path) -> dict[str, str]:
    return real_preflight.linux_lock_pins(path)


def test_no_workflow_resolves_dependencies_at_run_time():
    for workflow in sorted(WORKFLOWS.glob("*.yml")):
        for number, line in enumerate(workflow.read_text().splitlines(), 1):
            if "pip install" not in line:
                continue
            assert "playwright" in line and "pandas" not in line, f"{workflow.name}:{number}"


def test_every_install_goes_through_the_locked_script():
    for name in ("verify-release.yml", "mutation-shards.yml", "ci.yml", "pool-check.yml"):
        text = (WORKFLOWS / name).read_text()
        assert "verification/runner/install_locked.sh" in text, name
        assert "pip install --extra-index-url" not in text, name


def test_the_result_affecting_pins_of_the_linux_lock_are_the_canonical_versions():
    pins = _pins(real_preflight.LINUX_LOCK)
    for name, version in release.locked_versions().items():
        assert pins[name] == version, name
    assert pins["pandas"] == "3.0.6" and pins["pyod"] == "3.6.7"


def test_the_extras_lock_is_hash_pinned_and_agrees_with_the_base_lock():
    base = _pins(real_preflight.LINUX_LOCK)
    extras = _pins(EXTRAS)
    assert set(base).isdisjoint(extras)
    for line in EXTRAS.read_text().splitlines():
        if line and not line.startswith("#"):
            assert re.fullmatch(r"[a-z0-9-]+==\S+ --hash=sha256:[0-9a-f]{64}", line), line


def test_torch_is_the_build_that_the_owner_approved_lstm_records_bind():
    # PyTorch is outside the numerical lock: no archived result of the lock uses it, and the
    # owner-approved LSTM records bind this exact build, so the supplement must provide it.
    records = json.loads((ROOT / "verification/mutation_equivalence.json").read_text())["records"]
    bound = {r["environment"]["torch"] for r in records if "torch" in r["environment"]}
    assert bound == {_pins(EXTRAS)["torch"]}


def test_the_installer_script_checks_the_environment_it_built():
    body = (ROOT / "verification/runner/install_locked.sh").read_text()
    assert "def problems" in body
    assert body.index("--require-hashes") < body.index("def problems")


def _check_module() -> dict:
    body = (ROOT / "verification/runner/install_locked.sh").read_text()
    code = body.split("<<'PY'\n", 1)[1].split("\nPY", 1)[0]
    namespace: dict = {"__name__": "check_lock"}
    exec(compile(code, "install_locked.sh", "exec"), namespace)
    return namespace


def test_the_lock_check_reports_a_drifted_package():
    module = _check_module()
    wanted = module["pins"](str(real_preflight.LINUX_LOCK)) | module["pins"](str(EXTRAS))
    assert module["problems"](wanted, dict(wanted)) == []
    drifted = dict(wanted) | {"pandas": "3.1.1", "torch": None}
    found = " ".join(module["problems"](wanted, drifted))
    assert "pandas 3.1.1 != 3.0.6" in found and "torch not installed" in found
    canonical = release.locked_versions()
    assert all(wanted[name] == version for name, version in canonical.items())


def test_the_shard_evidence_binds_the_packages_that_equivalence_records_rely_on():
    from verification import evidence_schema, mutation_shards

    # Great Expectations and SciPy behaviour backs several records; unbound, the validator
    # could not tell that a record outlived the version it was argued on.
    for name in ("scipy", "great-expectations", "pandas", "pyod", "numpy", "torch"):
        assert name in mutation_shards.PACKAGES
    assert set(mutation_shards.PACKAGES) == set(evidence_schema.PACKAGES)
    pins = _pins(real_preflight.LINUX_LOCK)
    assert pins["scipy"] == "1.17.1" and pins["great-expectations"] == "1.24.0"


def test_every_accepted_equivalence_record_binds_only_canonical_versions():
    canonical = _pins(real_preflight.LINUX_LOCK) | _pins(EXTRAS)
    records = json.loads((ROOT / "verification/mutation_equivalence.json").read_text())["records"]
    stale = {
        record["id"]: {
            name: version
            for name, version in record["environment"].items()
            if canonical.get(name) != version
        }
        for record in records
        if record["verdict"] == "accepted"
    }
    stale = {key: value for key, value in stale.items() if value}
    assert stale == {}, f"{len(stale)} accepted record(s) bind a non-canonical dependency version"
