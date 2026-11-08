# Independent review packet — LSTM equivalence candidates

Status: **awaiting an independent reviewer. No verdict below is filled in and none may be filled in by the author
of the candidates.** The repository has a single collaborator (the project owner), so no reviewer other than the
owner is available to this process; the owner can review, or name a reviewer, and record the verdicts here.

Source revision of the candidates: d296f2f (`research/lstm_detector.py`; the same file at later commits). Candidate
list and the author's arguments: `EQUIVALENCE_CANDIDATES_LSTM_2026-11-08.md`. Differential evidence for the
arguments (not an acceptance): `research/tests/test_equivalence_claims.py` (14 tests, run with
`pytest research/tests/test_equivalence_claims.py`); it records the dependency versions on which the arguments rest
(pandas 3.0.6, numpy 2.4.6, torch 2.15.0).

## How to review one candidate

1. `python -m mutmut show 'research.lstm_detector.xǁLSTMAutoencoderǁ<function>__mutmut_<n>'` prints the diff.
2. Decide whether original and mutated code give the same result for every supported input and every supported
   environment (not only the tested ones); consider boundary sizes, dtypes, empty and single-row inputs, and other
   package versions allowed by `pyproject.toml` (the ranges are open).
3. Record ACCEPT, REJECT (give a counterexample or a missing contract) or INCONCLUSIVE. INCONCLUSIVE counts as not accepted.
4. For an ACCEPT, create a record in `verification/mutation_equivalence.json` (version 1) with the fields required by
   `verification/mutation_policy.accepted_equivalents`: id, path, function, diff, original and mutated behavior, risk,
   reason, evidence, `source_sha256`, `catalog_sha256` (`mutation_policy.catalog_digest` of the module catalog), author,
   the reviewer's own identity, approved true, ISO review date and policy version 2. A record whose reviewer equals its
   author, or whose digests are stale, is rejected by the gate.

## Verdict table (to be completed by the reviewer)

| Mutant | Diff | Verdict | Reviewer | Date | Counterexample or note |
| --- | --- | --- | --- | --- | --- |
| `_reconstruction_error__mutmut_31` | `dim=-1` to `dim=+1` (2-D tensor) | | | | |
| `_reconstruction_error__mutmut_35` | `.astype(float)` to `.astype(None)` | | | | |
| `_windows__mutmut_2` | `.astype(float)` to `.astype(None)` | | | | |
| `fit__mutmut_16` | `.astype(float)` to `.astype(None)` | | | | |
| `fit__mutmut_43` | `replace=False` to `replace=None` | | | | |
| `fit__mutmut_55` | `replace=False` to `replace=None` | | | | |
| `fit__mutmut_50` | `>` to `>=` (validation cap) | | | | |
| `settings__mutmut_41` | `version("torch")` to `version("TORCH")` | | | | |
| `settings__mutmut_46` | `version("numpy")` to `version("NUMPY")` | | | | |

## Points the reviewer should weigh

- The three `astype(None)` candidates rely on `astype(None)` meaning float64 in the installed pandas and numpy; the
  dependency ranges are open, so a future release could change that. A reviewer may reasonably reject them for that
  reason, in which case a test that pins `astype(float)` behavior (for example a string or datetime column) is needed.
- `replace=None` relies on truthiness inside numpy; `fit__mutmut_43` and `_55` are the least version-stable.
- The arithmetic: with 377 mutants L4 needs 370 kills; 368 are expected; two or more accepted exclusions would be needed
  only if no further behavior is found. That is a consequence, not a reason to accept.
