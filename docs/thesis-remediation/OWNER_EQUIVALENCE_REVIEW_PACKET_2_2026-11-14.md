# Second owner-review packet, 2026-11-14 (PROPOSED, NOT APPROVED)

Prepared after the behavioral remediation of `L4_CAMPAIGN_REPORT_2026-11-13.md`, as the user's priority 4 asks: tests first, equivalence only for what remains. It approves nothing, adds
nothing to `verification/mutation_equivalence.json` and leaves the 43 candidates of the first packet (`OWNER_EQUIVALENCE_REVIEW_2026-11-12.md`) as they were. The four `lstm_detector`
records stay subject to the repository validator (their `torch 2.15.0+cpu` pin is not met on this machine).

Source: `8707ea4`, policy digest `fc19388775ea`. Machine-readable form: `equivalence/owner_review_candidates_2026-11-14.json` (exact mutant identities, textual change, source and
catalog digests per unit; survivor dumps in `evidence/l4-campaign-2026-11-13/survivors/`).

## How to read it

For each unit that still fails or is incomplete, survivors are split four ways.

- **Candidate classes**: survivors whose one-line change matches a recognised pattern (below). Each class lists the counterexample searches of `tests/test_mutation_equivalence_probes.py` that back it; they ran on
  the environments listed in the entry and found no input that tells the mutant from the original. That is evidence for the owner, not proof across the supported dependency range.
- **Already decided or in the first packet**: mutants that carry an owner verdict in `verification/mutation_equivalence.json` (accepted or inconclusive, 2026-11-11) or sit in the first packet. They are listed with their
  verdict and not re-proposed here; the packet does not reopen a decision.
- **Unclassified**: no pattern matches. Not proposed as equivalent. Some are equivalent in a way the patterns do not recognise (for example an attribute initialised with an empty string that every reader overwrites),
  others can be killed by a test not written yet; telling them apart is the remaining per-mutant work. Two patterns are named in the JSON (`noted_patterns_not_proposed`) but not proposed, see below.
- Missing kills = the kills still needed to reach the threshold. For most units accepting every candidate class would still leave kills missing (compare the two columns).

| Unit | Level | Killed / eligible | Missing kills | Candidate classes | Decided / first packet | Unclassified | Passes if every candidate were accepted | Measured on |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `experiments/run_severity.py` | L4 | 320/329 | 3 | 2 | 0 | 7 | no | case-sensitive APFS volume |
| `research/injection.py` | L4 | 325/336 | 5 | 2 | 0 | 9 | no | case-sensitive APFS volume |
| `research/lstm_detector.py` | L4 | 368/377 | 2 | 0 | 9 | 0 | no | case-sensitive APFS volume |
| `research/multi_schema.py` | L4 | 1057/1093 | 15 | 4 | 0 | 32 | no | case-sensitive APFS volume |
| `research/normalise.py` | L4 | 191/197 | 3 | 0 | 6 | 0 | no | case-sensitive APFS volume |
| `research/pool_chrono.py` | L4 | 300/316 | 10 | 3 | 0 | 13 | no | case-sensitive APFS volume |
| `research/pool_preprocessing.py` | L4 | 241/248 | 3 | 1 | 0 | 6 | no | case-sensitive APFS volume |
| `research/temporal_decision.py` | L4 | 810/836 | 10 | 6 | 0 | 20 | no | case-sensitive APFS volume |
| `research/typed_benchmark.py` | L4 | 175/180 | 2 | 1 | 0 | 4 | no | case-sensitive APFS volume |
| `research/uci_loader.py` | L4 | 180/186 | 3 | 1 | 0 | 5 | no | case-sensitive APFS volume |
| `src/etl_benchmark/load.py` | L4 | 13/14 | 1 | 0 | 1 | 0 | no | case-sensitive APFS volume |
| `src/etl_benchmark/quality/_torch_models.py` | L4 | 58/65 | 6 | 0 | 0 | 7 | no | case-sensitive APFS volume |
| `src/etl_benchmark/quality/autoencoder.py` | L4 | 112/117 | 3 | 2 | 0 | 3 | no | case-sensitive APFS volume |
| `src/etl_benchmark/quality/base.py` | L4 | 30/31 | 1 | 0 | 1 | 0 | no | case-sensitive APFS volume |
| `src/etl_benchmark/quality/deep.py` | L4 | 60/62 | 1 | 2 | 0 | 0 | yes | case-sensitive APFS volume |
| `src/etl_benchmark/quality/drift.py` | L4 | 119/129 | 8 | 0 | 0 | 10 | no | case-sensitive APFS volume |
| `src/etl_benchmark/quality/gx.py` | L4 | 87/98 | 10 | 0 | 0 | 11 | no | case-sensitive APFS volume |
| `src/etl_benchmark/quality/ml.py` | L4 | 239/259 | 15 | 1 | 0 | 19 | no | case-sensitive APFS volume |
| `src/etl_benchmark/quality/rules.py` | L4 | 112/119 | 5 | 0 | 0 | 7 | no | case-sensitive APFS volume |
| `src/etl_benchmark/quality/window_drift.py` | L4 | 225/233 | 4 | 1 | 0 | 7 | no | case-sensitive APFS volume |
| `src/etl_benchmark/quality/windows.py` | L4 | 54/57 | 2 | 1 | 0 | 2 | no | case-sensitive APFS volume |
| `verification/mutation_scope.py` | L4 | 240/246 | 2 | 6 | 0 | 0 | yes | case-sensitive APFS volume |

## Classes

- **split-limit** (limit of a split whose first part is read): `text.split(sep, n)[0]` is the part before the first separator for any limit n >= 1 or none; the class holds only when the new limit is at least 1 or absent. Searches: `test_the_first_part_of_a_split_does_not_depend_on_a_limit_of_one_or_more`.
- **falsy-flag** (False replaced by None for a flag read as a truth value): Only `False` -> `None` for allow_nan, annotate_fields, sort, index, replace, check or ignore_index. `True` -> `None` (for example `exist_ok`, `parents`) is not in the class. Searches: `test_json_with_allow_nan_none_refuses_non_finite_numbers_like_false`, `test_ast_dump_without_field_names_is_the_same_for_false_and_none`, `test_a_missing_sort_flag_in_a_groupby_means_no_sorting_like_false`, `test_a_missing_index_flag_in_to_csv_writes_no_index_like_false`, `test_a_missing_replace_flag_in_a_choice_samples_without_replacement_like_false`, `test_a_missing_check_flag_in_a_subprocess_run_behaves_like_false`.
- **name-case** (case of a name the library reads without case): Only a quoted name of three letters or more that changes case alone, in `version(...)`, `tz_localize(...)`/`tz=` (utc), `kind=` (stable), `unit=` (min) or `decode(...)`. One-letter units are not in the class (`m` and `M` differ). It says nothing about the dependency range: the owner's reason for `inconclusive` on 2026-11-11 was exactly that. Searches: `test_a_package_version_is_looked_up_without_regard_to_case`, `test_a_timezone_name_is_read_without_case_for_utc`, `test_a_sort_kind_is_read_without_case`, `test_the_minute_unit_is_read_without_case`, `test_a_codec_name_is_read_without_case`.
- **signed-division** (division by -1 for a multiplication by -1): Holds when the operand is a float array or a float; an integer operand gives float for `/` and integer for `*`. The operand's type is not checked by this builder: it must be read per mutant. Searches: `test_a_division_by_minus_one_is_a_multiplication_by_minus_one_for_floats`.

Noted but not proposed (no probe, needs reading per mutant):

- **unset-state**: an initial attribute value changed from None to an empty string; equivalence needs every reader of the attribute read, per unit.
- **default-dtype**: `astype(int)`/`dtype=int` replaced by None gives float64; previously judged inconclusive by the owner for `astype(None)`.

## What the owner would be deciding

A class is not an approval of a mutant. If the owner accepts a class, the next step is a record in `verification/mutation_equivalence.json` per mutant, with the exact identity, the source and catalog
digests listed in the JSON, the environment, and the review fields the validator requires. Not before. Where a unit's missing kills exceed its candidate-class survivors, accepting every class still would not
make it pass: those units need tests or a change of level, which is not proposed here.
