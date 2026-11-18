#!/usr/bin/env bash
# Supervised, resumable run of the neural alert-budget study (T163, T164).
# usage: research/run_alert_budget_neural.sh <python> <workers> [threads-per-worker]
# Writes into verification/evidence/alert_budgets/neural: manifest.json (fingerprints),
# run.pid, run.log, run.exit (exit status, only when the run has ended), cells/ (one file per
# problem, detector and seed, published atomically) and runs/ (one file per problem).
# Restarting the script resumes: valid cells are reused, corrupt or missing ones are recomputed.
set -u
python_bin=${1:?python}; workers=${2:?workers}; threads=${3:-4}
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
out=$root/verification/evidence/alert_budgets/neural
mkdir -p "$out/runs" "$out/cells"
cd "$root" || exit 2
export OMP_NUM_THREADS=$threads MKL_NUM_THREADS=$threads OPENBLAS_NUM_THREADS=$threads
export VECLIB_MAXIMUM_THREADS=$threads PYTHONHASHSEED=0
"$python_bin" - "$out/manifest.json" "$workers" "$threads" <<'PY'
import hashlib, json, subprocess, sys
from importlib.metadata import version
files = ["research/alert_budget.py", "research/pool_full.py", "research/normalise.py",
         "research/deep_support.py", "research/labelled_benchmark.py",
         "src/etl_benchmark/registry.py", "src/etl_benchmark/quality/deep.py",
         "src/etl_benchmark/quality/_torch_models.py", "src/etl_benchmark/pipeline.py"]
sha = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
manifest = {
    "head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
    "dirty": bool(subprocess.check_output(["git", "status", "--porcelain", "--"] + files, text=True)),
    "sources": {p: sha(p) for p in files},
    "registry_sha256": sha("verification/evidence/dataset_registry/pool_manifest.json"),
    "versions": {p: version(p) for p in ("numpy", "pandas", "pyod", "scikit-learn", "torch")},
    "python": sys.version.split()[0], "workers": int(sys.argv[2]), "threads": int(sys.argv[3]),
    "budgets": [0.005, 0.01, 0.02, 0.05, 0.10],
}
open(sys.argv[1], "w").write(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
PY
[ $? -eq 0 ] || exit 3
echo $$ > "$out/run.pid"
rm -f "$out/run.exit"
"$python_bin" research/alert_budget.py --methods deep --workers "$workers" --resume \
  --output "$out/runs" --cells "$out/cells" >> "$out/run.log" 2>&1
status=$?
echo "$status" > "$out/run.exit"
exit $status
