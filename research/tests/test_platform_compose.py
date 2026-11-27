"""Contract of the local runtime profiles (#142): isolation, loopback ports, limits, no secret."""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = yaml.safe_load((ROOT / "platform" / "compose.yaml").read_text())
SERVICES = COMPOSE["services"]
EXPECTED = set(
    [
        "core",
        "etl",
        "elt",
        "relational",
        "orchestration",
        "mlops",
        "observability",
        "aiops",
        "analytics",
    ]
)


def test_every_service_belongs_to_exactly_one_profile_and_none_starts_by_default():
    assert all(len(s["profiles"]) == 1 for s in SERVICES.values())
    assert {s["profiles"][0] for s in SERVICES.values()} == EXPECTED


def test_every_published_port_is_bound_to_the_loopback_interface():
    ports = [p for s in SERVICES.values() for p in s.get("ports", [])]
    assert ports and all(str(p).startswith("127.0.0.1:") for p in ports)


def test_every_service_has_a_memory_limit_and_drops_privilege_escalation():
    for name, service in SERVICES.items():
        assert service.get("mem_limit"), name
        assert "no-new-privileges:true" in service["security_opt"], name


def test_no_credential_is_written_in_the_tracked_files():
    for name, service in SERVICES.items():
        for key, value in (service.get("environment") or {}).items():
            if re.search(r"PASSWORD|SECRET|TOKEN|KEY", key):
                assert str(value).startswith("${") and ":?" in str(value), f"{name}.{key}"


def test_a_profile_depends_only_on_services_of_its_own_profile():
    for name, service in SERVICES.items():
        for dependency in service.get("depends_on", {}):
            assert SERVICES[dependency]["profiles"] == service["profiles"], name


def test_the_smoke_script_covers_every_profile():
    script = (ROOT / "platform" / "smoke.sh").read_text()
    assert all(re.search(rf"^{profile}\)", script, re.MULTILINE) for profile in EXPECTED)
