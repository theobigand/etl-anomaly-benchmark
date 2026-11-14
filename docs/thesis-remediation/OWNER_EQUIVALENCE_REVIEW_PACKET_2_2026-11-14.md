# Second owner-review packet, 2026-11-14 (PROPOSED, NOT APPROVED)

Prepared after the behavioral remediation of `L4_CAMPAIGN_REPORT_2026-11-13.md`, as the user's priority 4 asks: tests first, equivalence only for what remains. It approves nothing, adds
nothing to `verification/mutation_equivalence.json` and leaves the 43 candidates of the first packet (`OWNER_EQUIVALENCE_REVIEW_2026-11-12.md`) as they were. The four `lstm_detector`
records stay subject to the repository validator (their `torch 2.15.0+cpu` pin is not met on this machine).

Source: `38897c2`, policy digest `fc19388775ea`. Machine-readable form: `equivalence/owner_review_candidates_2026-11-14.json` (exact mutant keys, textual change, source and
catalog digests per unit; survivor dumps in `evidence/l4-campaign-2026-11-13/survivors/`).

## How to read it

For each unit that still fails or is incomplete, survivors are split in two. **Candidate classes** are survivors whose one-line change matches a recognised pattern (below); each class cites a counterexample search in
`tests/test_mutation_equivalence_probes.py`, which passed: no input was found that tells the mutant from the original. **Unclassified** survivors match no pattern: they are not proposed as equivalent. Some of them are equivalent in a way the
patterns do not recognise, others can be killed by a test not written yet; telling them apart is the remaining per-mutant work. Missing kills = the kills still needed to reach the threshold.

| Unit | Level | Killed / eligible | Missing kills | In candidate classes | Unclassified | Measured on |
| --- | --- | --- | --- | --- | --- | --- |
| `experiments/run_severity.py` | L4 | 320/329 | 3 | 2 | 7 | case-insensitive APFS |
| `research/cost_study.py` | L3 | 817/825 | 0 | 2 | 6 | case-sensitive APFS volume |
| `research/injection.py` | L4 | 325/336 | 5 | 5 | 6 | case-sensitive APFS volume |
| `research/lstm_detector.py` | L4 | 368/377 | 2 | 7 | 2 | case-insensitive APFS |
| `research/lstm_pilot.py` | L4 | 460/506 | 36 | 2 | 44 | case-insensitive APFS |
| `research/multi_schema.py` | L4 | 1000/1093 | 72 | 8 | 85 | case-insensitive APFS |
| `research/normalise.py` | L4 | 191/197 | 3 | 2 | 4 | case-insensitive APFS |
| `research/paper_appendix.py` | L3 | 134/171 | 29 | 0 | 37 | case-insensitive APFS |
| `research/paper_tables.py` | L3 | 469/511 | 17 | 0 | 42 | case-insensitive APFS |
| `research/pool_chrono.py` | L4 | 300/316 | 10 | 6 | 10 | case-sensitive APFS volume |
| `research/pool_etl.py` | L4 | 292/317 | 19 | 1 | 24 | case-insensitive APFS |
| `research/pool_preprocessing.py` | L4 | 241/248 | 3 | 2 | 5 | case-insensitive APFS |
| `research/temporal_decision.py` | L4 | 810/836 | 10 | 8 | 18 | case-sensitive APFS volume |
| `research/typed_benchmark.py` | L4 | 175/180 | 2 | 3 | 2 | case-insensitive APFS |
| `research/typed_figures.py` | L3 | 133/240 | 95 | 2 | 105 | case-insensitive APFS |
| `research/uci_loader.py` | L4 | 180/186 | 3 | 1 | 5 | case-insensitive APFS |
| `research/uci_pool.py` | L3 | 386/423 | 16 | 0 | 37 | case-insensitive APFS |
| `src/etl_benchmark/load.py` | L4 | 13/14 | 1 | 1 | 0 | case-insensitive APFS |
| `src/etl_benchmark/quality/_torch_models.py` | L4 | 58/65 | 6 | 0 | 7 | case-insensitive APFS |
| `src/etl_benchmark/quality/autoencoder.py` | L4 | 112/117 | 3 | 4 | 1 | case-insensitive APFS |
| `src/etl_benchmark/quality/base.py` | L4 | 30/31 | 1 | 1 | 0 | case-insensitive APFS |
| `src/etl_benchmark/quality/deep.py` | L4 | 60/62 | 1 | 2 | 0 | case-insensitive APFS |
| `src/etl_benchmark/quality/drift.py` | L4 | 119/129 | 8 | 3 | 7 | case-insensitive APFS |
| `src/etl_benchmark/quality/gx.py` | L4 | 87/98 | 10 | 0 | 11 | case-insensitive APFS |
| `src/etl_benchmark/quality/ml.py` | L4 | 238/259 | 16 | 7 | 14 | case-insensitive APFS |
| `src/etl_benchmark/quality/rules.py` | L4 | 112/119 | 5 | 5 | 2 | case-sensitive APFS volume |
| `src/etl_benchmark/quality/window_drift.py` | L4 | 225/233 | 4 | 6 | 2 | case-insensitive APFS |
| `src/etl_benchmark/quality/windows.py` | L4 | 54/57 | 2 | 2 | 1 | case-insensitive APFS |
| `verification/archive_evidence.py` | L3 | 207/249 | 30 | 0 | 42 | case-insensitive APFS |
| `verification/bundles.py` | L3 | 249/264 | 2 | 0 | 15 | case-insensitive APFS |
| `verification/lock_environment.py` | L3 | 247/346 | 82 | 0 | 99 | case-insensitive APFS |
| `verification/mutation_cache.py` | L4 | 1088/1110 | 0 | 5 | 17 | case-sensitive APFS volume |
| `verification/mutation_scope.py` | L4 | 240/246 | 2 | 6 | 0 | case-sensitive APFS volume |
| `verification/pool_contract.py` | L4 | 184/187 | 0 | 0 | 3 | case-insensitive APFS |
| `verification/protection.py` | L3 | 235/294 | 45 | 1 | 58 | case-insensitive APFS |
| `verification/real_preflight.py` | L3 | 543/790 | 208 | 1 | 246 | case-insensitive APFS |
| `verification/refresh_profile.py` | L3 | 105/147 | 35 | 0 | 42 | case-insensitive APFS |
| `verification/scaling.py` | L3 | 183/307 | 109 | 1 | 123 | case-insensitive APFS |

## Classes

- **split-limit** (limit of a split whose first part is read): `text.split(sep, n)[0]` is the part before the first separator for any n >= 1 or no limit. Search: test_the_first_part_of_a_split_does_not_depend_on_a_limit_of_one_or_more.
- **falsy-flag** (None for a flag whose value is False): `allow_nan`, `annotate_fields`, `sort`, `index`, `replace`, `check`, `exist_ok`, `parents` read their value as a truth value; None and False act alike. Search: test_json_with_allow_nan_none_*, test_ast_dump_*, test_a_missing_sort_flag_*, test_a_missing_index_flag_*, test_a_missing_replace_flag_*.
- **name-case** (case of a name the library reads without case): package names (`version`), time-zone names, sort kinds, time units, HTTP header names and codec names are matched without case. Search: test_a_package_version_*, test_a_timezone_name_*, test_a_sort_kind_*, test_http_header_names_*, test_a_codec_name_*.
- **unset-state** (initial value of an attribute that a fit sets before any read): the attribute is assigned in `fit`; every reader first checks the other attribute of the pair or is only reached after `fit`. Search: per-unit reading of the readers; not mechanised.
- **default-argument** (argument dropped or set to its default): the callee's default equals the original value, or the argument is overridden afterwards. Search: per-unit reading; the owner left `astype(None)` and `replace=None` inconclusive on 2026-11-11.
- **signed-division** (division by -1 for a multiplication by -1): x / -1 and x * -1 give identical floats. Search: test_a_division_by_minus_one_is_a_multiplication_by_minus_one.

## What the owner would be deciding

A class is not an approval of a mutant. If the owner accepts a class, the next step is a record in `verification/mutation_equivalence.json` per mutant, with the exact key, the source and catalog
digests listed in the JSON, the environment, and the review fields the validator requires. Not before. Where a unit's missing kills exceed its candidate-class survivors, accepting every class still would not
make it pass: those units need tests or a change of level, which is not proposed here.
