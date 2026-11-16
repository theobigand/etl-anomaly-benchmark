# Mutation campaign input provenance gap

The current mutation execution contract does not by itself bind every test
input required by the requested fresh campaign. In `verification/mutation_cache.py`,
`hash_tests` records `conftest.py` and `*.py` under `tests` and
`research/tests`. `capture_context` binds these hashes, Python sources and a
specified list of configuration/environment files. Separately,
`verification/mutation_shards.py::current_context` hashes only `*.py` under
`tests` and `research/tests` for its test-tree digest. Neither inventory is a
complete list of non-Python files read by tests. The recorded Git revision
identifies tracked files in a clean checkout, but these digest functions do
not independently establish that the working files remained clean and
unchanged during execution or bind ignored and external inputs. For example,
`tests/test_owner_review_packet.py` reads
`docs/thesis-remediation/evidence/mutation-survivors-2026-11-12.json`,
`docs/thesis-remediation/equivalence/owner_review_candidates_2026-11-12.json`
and `verification/mutation_equivalence.json`; other tests read workflow and
scientific artifact files. This is a provenance coverage limitation, not a
claim that any given historical verdict is wrong.

A run with fresh native mutants avoids reusing old verdicts, but does not by
itself prove the contents of these additional inputs were immutable and
captured throughout execution. Future shard uploads have been amended to retain
the native log and metadata, but that does not close the input-inventory gap.
Before representing a full run as meeting the requested provenance standard,
the campaign needs a complete, justified test-input inventory and immutable
per-shard bindings for those files, including applicable local data and
non-Python artifacts, with checks for missing, changed or added inputs. The
resulting verification-infrastructure change requires tests for stale and
missing inputs and independent review under project governance; this session
has no remaining independent-review authorization. Do not narrow mutation
scope or invent data to satisfy the gap.

Inspect the current contracts and examples with:

```sh
rg -n 'def hash_tests|def capture_context' verification/mutation_cache.py
rg -n 'def current_context|rglob\("\*\.py"\)' verification/mutation_shards.py
rg -n 'read_text|EVIDENCE|CANDIDATES|LIVE' tests/test_owner_review_packet.py
```

This gap, the still-incomplete mutant investigations, the missing Linux-side
LSTM validator result and the lack of an independent review prevent a claim of
certification readiness. It does not authorize changing a release gate or owner
decision.

Update: the scoped Linux LSTM validator subsequently accepted the four
existing owner records at commit `d4d21895d3c6addf75218b67bdb8ccd11b4c7b7e`;
see [the diagnostic record](DIAGNOSTIC_43744898804.md). That result does not
close this full-campaign input-provenance gap or establish a result for a later
commit.

## Resolution of the tracked-input gap (2026-11-16)

The shard context now carries `inputs_sha256`, the digest of the names and working
bytes of every Git-tracked file (`verification/mutation_shards.py::_tracked_inputs`).
Non-Python inputs such as data, documentation and workflows, and any modified or
deleted tracked file, change the binding, and the aggregation rejects a shard whose
binding differs. Remaining limits, stated plainly:

- Untracked files, ignored files and data outside the repository are not bound.
- The digest is taken when the manifest is built, not inside the execution proof.
- Tests run from the ignored `mutants/` copy tree, which mutmut never prunes. Campaign
  evidence therefore must come from `fresh_mutants=true`; a restored cache can hold
  copies of files that were deleted, or of non-Python files under source paths outside
  `also_copy` that changed, since the cached run. Pull-request-label runs always restore the
  cache, and no manifest records freshness: check the GitHub run's event and
  `fresh_mutants` input.
