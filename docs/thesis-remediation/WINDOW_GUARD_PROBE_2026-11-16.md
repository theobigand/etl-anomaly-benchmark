# Window-monitor failed-fit guards

The generated methods for `etl_benchmark.quality.window_drift.xǁWindowDriftMonitorǁevaluate__mutmut_1` and `...__mutmut_2` were read from the archived Linux diagnostic shard. The current source SHA-256 is `7369796bac2ada0ee25c125b383752c8d40d7f683e287767dfb6b373108ea8d7`; the generated file SHA-256 is `a13c8afb6e8500babc75039c9479cdca53e6853bc7a64cdac36e14292031fdfe`. The probe and full output are `evidence/continuation-2026-11-15/window-guard-probe.py.txt` and `window-guard-output.txt`.

On macOS arm64, Python 3.11.17, NumPy 2.4.6 and pandas 3.1.1, the original and both mutants agreed for a fresh monitor, successful ordinary fit, and a rejected nonfinite reference. With the caller's NumPy overflow mode set to `raise`, finite values `1e308` and `-1e308` made fitting fail during variance computation after the reference timestamp and mean had been assigned. The original rejected subsequent evaluation with `RuntimeError: monitor not fitted`. Mutant 1 instead attempted arithmetic with an absent scale and raised `TypeError`. This is a demonstrated behavioral gap in failed-fit handling; a regression and native verdict are still required.

Mutant 2 matched all tested cases. A successful assignment of `_scale` follows assignment of `reference_end` in `fit`, and the timestamp validator rejects missing timestamps. This suggests an invariant for ordinary sequential use, but the public `reference_end` attribute is mutable and exceptional or concurrent mutation of object state was not exhaustively studied. Therefore mutant 2 remains inconclusive rather than approved or presumed equivalent.

The scripts read the extracted diagnostic tree. Restore the recorded generated
file without changing the live mutation cache with:

```sh
mkdir -p docs/thesis-remediation/evidence/diagnostic-43744898804/shard/mutants/src/etl_benchmark/quality
test ! -e docs/thesis-remediation/evidence/diagnostic-43744898804/shard/mutants/src/etl_benchmark/quality/window_drift.py && gzip -dc docs/thesis-remediation/evidence/continuation-2026-11-15/window-diagnostic-generated.py.gz > docs/thesis-remediation/evidence/diagnostic-43744898804/shard/mutants/src/etl_benchmark/quality/window_drift.py
~/.cache/etl-mutation-venv/bin/python docs/thesis-remediation/evidence/continuation-2026-11-15/window-guard-probe.py.txt
```
