# Logging, telemetry and error-handling audit (#155)

Scope: inventory and classification only. No code was changed by this audit. The classification
sets the boundaries for the logging tickets that follow (#156 central configuration, #157 and the
observability issues #158-#168).

Counts come from an AST scan of the Python sources (tests, archived evidence and generated results
excluded) on the tree that integrates the acquisition work of #132 (2026-11-26). They are static counts of call sites, not runtime volumes.

## Inventory

| Module group | Files | `print` | `logging` calls | `except Exception` | Other notes |
|---|---:|---:|---:|---:|---|
| `src/etl_benchmark` (pipeline, CLI, load/extract/transform, `logging_setup`) | 14 | 0 | 7 | 0 | Only place with a shared configuration: `logging_setup.setup_logging` (basicConfig, `%(asctime)s [%(name)s] %(levelname)s`). Called from `__main__` only. `pipeline.py` logs one `log.info` per ETL stage. |
| `src/etl_benchmark/quality` (detectors) | 11 | 0 | 0 | 0 | `ml.py` restores detector state with `except BaseException` and re-raises (failed-fit contract). No logging. |
| `experiments/` (runners) | 10 | 11 | 19 | 0 | Runners import `logging_setup`/`logging` and use `log.info`; `print` is used for end-of-run summaries. |
| `research/` (studies, harnesses) | 83 | 76 | 4 | 19 | 73 of 76 prints are in `main()` or at module level (CLI output). `logging` appears only in `temporal_pilot.py` and `lstm_pilot.py`. |
| `verification/` (gates, evidence tools) | 22 | 40 | 0 | 1 | Prints are the output of checkers; exit codes carry the verdict. |

Findings that matter for the next tickets:

1. There is no central logging configuration beyond `basicConfig`. Library modules in `research/`
   and `verification/` do not log at all; they print or stay silent.
2. No module emits structured (key-value) events, run identifiers, or correlation identifiers.
3. Per-stage durations exist as data (`pipeline.py` measures with `time.perf_counter` and returns
   them in the result object, for example `detect_s`) but are not emitted as telemetry events.
   They are scientific measurements, not log lines.
4. All 19 broad `except Exception` handlers in `research/` and the one in `verification/scaling.py`
   convert a failure into a recorded outcome (`error`, `failed`, `status: FAIL`, `eligible: false`
   with a reason) inside the result JSON. None swallows silently; none emits a log record.
5. No bare `except:` and no `except ...: pass` was found.

## Classification

Legend: **keep** (intentional, must not change), **convert** (candidate for the logging tickets),
**leave** (out of scope for logging work).

| Group | Item | Class | Reason and boundary |
|---|---|---|---|
| CLI | `argparse` entry points, `--help`, exit codes | keep | Public interface. |
| CLI | `print` of results and summaries in `research/*.py` `main()` (73) | keep | Intentional stdout output, sometimes the machine-readable result (`json.dumps` to stdout). A logger must never replace it. |
| CLI | `print` in `verification/*.py` and `experiments/*.py` checkers and runners (51) | keep | Verdict and report output consumed by humans and by the release gates. |
| Library | `print` outside `main()`/module level (4: 3 in `research/`, 1 in `verification/`) | convert | Progress or diagnostic output from library code; candidate for a logger in #156/#157. Individually reviewed then, not here. |
| Library | `src/etl_benchmark/pipeline.py` stage `log.info` calls | convert | Already stdlib logging; move to the central configuration and structured fields. |
| Library | `experiments/*.py` `log.info` calls (19) | convert | Same: adopt the central configuration and run identifiers. |
| Library | `temporal_pilot.py`, `lstm_pilot.py` `logging` use (4 calls) | convert | Same. |
| Configuration | `src/etl_benchmark/logging_setup.py` | convert | Becomes the single configuration point (stdlib `logging` plus `structlog`, #156). |
| Configuration | `logging.getLogger("great_expectations"/"matplotlib").setLevel(WARNING)` in runners | keep | Third-party noise control; carried into the central configuration. |
| Errors | `except Exception` converting a failure into a recorded outcome (19 in `research/`, 1 in `verification/`) | keep | The failure is scientific data (disclosed errors, ineligibility reasons). Do not turn into raise-only or log-only. Optionally add a log record beside the recorded outcome later; never instead of it. |
| Errors | `ml.py` `except BaseException` + re-raise | keep | Behavioural contract of `PyODDetector.fit`; covered by tests and mutation evidence. |
| Errors | `except ImportError`, `(TypeError, ValueError)` narrow handlers | leave | Specific, already handled. |
| Serialization | Scientific results, evidence JSON, manifests, fingerprints | keep | Byte-stable artifacts; sealed archives and digests depend on them. Logging must not write into or reorder them. |
| Serialization | `atomic_path` writes | keep | Integrity mechanism, unrelated to logging. |
| Telemetry | Durations returned in result objects (`detect_s`, timing fields in archived runs) | keep | Measurements that archived evidence records; changes would alter replays. Telemetry events (#158 onward) are a separate, additional channel. |
| Telemetry | Emission of run, stage and failure events | convert (new) | Does not exist today; belongs to #157/#158, not to this audit. |
| Pipeline reporting | `Pipeline` result object and CLI summary | keep | Part of the public pipeline contract. |

## Boundaries for the follow-up tickets

- #156 may change `logging_setup.py`, the stage logs in `pipeline.py`, and the runner logs listed
  as convert. It must keep every `keep` row byte-for-byte (stdout of the CLIs, result JSON).
- Broad refactors of `research/` CLI output are out of scope for the logging tickets.
- Any logging that runs inside a scientific code path must not change numeric results, random
  state, or serialization order. A replay check on the existing archived experiments protects this.
- Log files, telemetry stores and service volumes stay out of the repository.

## Not checked

- Runtime log volumes and the actual content of log messages.
- Modules under `slides/`, `paper/` build scripts and shell scripts.
- Whether every `print` in `research/` main functions is the machine-readable result or a progress
  line; the 73 are kept as a group because the audit does not change them.
