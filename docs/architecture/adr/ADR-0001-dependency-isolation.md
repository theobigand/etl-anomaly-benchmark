# ADR-0001: Dependency isolation and the scientific fingerprint

Status: accepted for planning, 2026-11-26.

**Decision.** No platform component enters the research core. The research core is `[project]` in
`pyproject.toml`, `environment.yml` and the locks under `verification/environment/`: the first two are hashed into the
scientific fingerprint (recipe 2, `experiments/provenance.py`, together with every `src/**/*.py` and top-level
`experiments/*.py`), and the locks are part of the release evidence. A component enters through an optional dependency
group (`[dependency-groups]`, as the PyArrow group already does), a separate virtual environment, or a container
profile, in the ticket that needs it, and never as a side effect of another change.

**Consequences.** Code under `src/` and top-level `experiments/` cannot import an optional component unconditionally.
Changing those files changes the fingerprint and needs a replay of the archived experiments, so platform code lives
in new modules outside the fingerprint and is adopted by the existing runners only through a separate, replayed
decision. The research core installs and passes its tests with no optional component present
(`tests/test_architecture_records.py` checks the declared dependencies).
