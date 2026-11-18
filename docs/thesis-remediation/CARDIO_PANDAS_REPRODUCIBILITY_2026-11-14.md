# Cardio archive replay: pandas parsing difference

The full suite in the mutation virtual environment failed
`test_cardio_is_reproduced_against_the_archive_with_the_local_data`: the
archive replay was STATISTICAL where the test expects NUMERICAL on this
platform. The same test passed in the canonical conda environment. The test
and archived results were not changed.

On macOS arm64, Python 3.11.17, the mutation environment uses NumPy 2.4.6,
pandas 3.1.1, SciPy 1.17.1, scikit-learn runtime 1.9.1, and PyOD 3.6.7. The
canonical conda interpreter has pandas 3.0.6, the same listed runtime versions
of NumPy, SciPy, scikit-learn and PyOD, and a different dependency/build stack.
The Cardio CSV SHA-256 is
`28bb4f67afca256f0cebe3cc6ca75a13be0bfc062e21efcaf40f1d3d80688eff`.

The following diagnostic replays used the same data, five archived seeds and
source. `verification.reproduce._level` compared non-timing metrics and the
archived split IDs:

| Replay | Archive comparison | Maximum non-timing absolute difference | Split IDs |
| --- | --- | ---: | --- |
| Mutation environment, pandas 3.1.1 | STATISTICAL, PASS | 0.7999853302421522 | identical bytes |
| Canonical conda, pandas 3.0.6 | NUMERICAL, PASS | 0 | identical bytes |
| Mutation interpreter with only canonical pandas 3.0.6 package on its import path | NUMERICAL, PASS | 0 | identical bytes |
| Mutation pandas 3.1.1, with only the loaded numeric values replaced by the canonical loaded values | NUMERICAL, PASS | 0 | identical bytes |

In the original mutation replay the changed metrics belonged to HBOS and IQR;
the largest absolute difference is the HBOS flagged-percentage standard
deviation, not an AUC difference. The archive comparator accepts the replay
as statistical, but the test explicitly requires numerical equality on this
platform and therefore fails.

Direct `pandas.read_csv` of the same file produced 17,081 differing float
values among the raw 1,831 by 22 cells; the largest absolute difference was
`1.7763568394002505e-15`. After dataset loading and duplicate removal, 17,001
numeric values differed among 1,822 by 23 cells, at the same maximum. For
example the first `f00` CSV decimal is `0.004912314661768384`: pandas 3.1.1
read `0.004912314661768384`, matching Python's float conversion, whereas the
canonical pandas 3.0.6 build read `0.0049123146617683`. Thus the discrepancy
is traced to differences in the parsed floating-point input in these builds;
the experiment does not isolate the underlying pandas parser implementation
or establish a universal version effect. Floating-point perturbations can
change rankings and histogram boundaries, so the nonzero downstream
metric differences are meaningful evidence, not timing noise.

Local diagnostic outputs, including parsed arrays, comparison tables and split
archives, are retained under `experiments/results/cardio-env-audit/` and are
not included in the commit; they include derived dataset values. Their raw
array SHA-256 digests are `2c8bf7149c7f2142c2ef74507d91e55469ebe4957c5b647888ef3afb7c92f4de`
(mutation) and `34217fc2317badc53a505feebc54333c6ebd93a29b1eb79d783f675226dec599`
(canonical pandas). The pandas substitution used a local import-path override
pointing to the existing conda package, without changing either environment.
The canonical-value experiment preserved the mutation interpreter and its
pandas version while replacing only the float columns returned by
`DatasetSpec.load`. Timings are excluded from numerical agreement.

This finding is separate from the full-rank synthetic PCA discrepancy. It
shows that platform identity alone does not establish identical numerical
inputs; no archive, threshold, reproducibility requirement, or release gate
was altered.

Proposed manuscript wording for owner review, following the existing Cardio
reproduction paragraph: “A separate same-platform replay using a different
pandas build parsed some CSV values to different floating-point numbers. Its
partitions were identical and its results met the statistical criterion, but
the HBOS and IQR metrics were not bit-identical. Platform identity alone is
therefore insufficient to guarantee numerical reproduction.” The historical
Linux comparison and the archived measurements should remain as recorded.

To repeat the input check with the retained interpreters, run the following
from the repository root (adjust the conda path if needed):

```sh
AUDIT_OVERRIDE=experiments/results/cardio-env-audit/pandas_override
AUDIT_OUTPUT=$(mktemp -d)
export AUDIT_OUTPUT
for mode in native overridden; do
  case "$mode" in
    native) audit_path="$PWD/src" ;;
    overridden) audit_path="$PWD/$AUDIT_OVERRIDE:$PWD/src" ;;
  esac
  PYTHONPATH="$audit_path" AUDIT_MODE="$mode" ~/.cache/etl-mutation-venv/bin/python - <<'PY'
import os
import numpy as np
import pandas as pd
from etl_benchmark.datasets import DATASETS
root = os.environ['AUDIT_OUTPUT'] + '/'
mode = os.environ['AUDIT_MODE']
np.save(root + mode + '-raw.npy', pd.read_csv('data/cardio.csv').to_numpy(dtype=float))
np.save(root + mode + '-loaded.npy', DATASETS['cardio'].load().to_numpy(dtype=float))
print(mode, pd.__version__)
PY
done
~/.cache/etl-mutation-venv/bin/python - <<'PY'
import os
import numpy as np
root = os.environ['AUDIT_OUTPUT'] + '/'
for name in ('raw', 'loaded'):
    a = np.load(root + 'native-' + name + '.npy')
    b = np.load(root + 'overridden-' + name + '.npy')
    print(name, a.shape, np.count_nonzero(a != b), np.max(np.abs(a - b)))
PY
```

`pandas_override` contains links to the existing conda `pandas` package and
its matching distribution metadata. For complete replay, use
`verification.reproduce.command_for('cardio', interpreter, output_directory)`
and compare each generated table and split archive with
`verification.reproduce._level`; preserve each run's own environment and
outputs. The package override and saved-array substitution are diagnostic
experiments and are not an approved change to the benchmark protocol.

The canonical-value replay was run in the mutation interpreter after the
input check. It replaced only float columns in the loaded DataFrame and then
ran the normal benchmark entry point; an equivalent diagnostic invocation is:

```sh
AUDIT_REPLAY=$(mktemp -d)
export AUDIT_REPLAY
~/.cache/etl-mutation-venv/bin/python - <<'PY'
import os
import runpy
import sys
from pathlib import Path
import numpy as np
from etl_benchmark.datasets import DATASETS, DatasetSpec
from verification import reproduce

frame = DATASETS['cardio'].load()
values = np.load(Path(os.environ['AUDIT_OUTPUT']) / 'overridden-loaded.npy')
for index, column in enumerate(frame.columns):
    if frame[column].dtype.kind == 'f':
        frame[column] = values[:, index]
DatasetSpec.load = lambda self: frame.copy()
out = Path(os.environ['AUDIT_REPLAY'])
sys.path.insert(0, str(Path('experiments').resolve()))
sys.argv = reproduce.command_for('cardio', sys.executable, out)[1:]
runpy.run_path('experiments/run_benchmark.py', run_name='__main__')
PY
```

This invocation intentionally overrides `DatasetSpec.load` only in the
experiment process; do not use it for a production benchmark or archive replay.
