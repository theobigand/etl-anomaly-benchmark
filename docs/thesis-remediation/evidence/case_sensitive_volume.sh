#!/bin/bash
# Recreate the case-sensitive macOS measurement environment used for the adopted verdicts.
#
#   docs/thesis-remediation/evidence/case_sensitive_volume.sh setup            # create, mount, copy the repository
#   docs/thesis-remediation/evidence/case_sensitive_volume.sh run UNIT [UNIT]  # measure units there, keep survivor dumps
#   docs/thesis-remediation/evidence/case_sensitive_volume.sh sync             # copy the current repository again
#   docs/thesis-remediation/evidence/case_sensitive_volume.sh teardown         # unmount (the image is kept)
#
# Why: pytest's temporary folders live on the default macOS volume, which compares file names without case, so a
# mutant that only changes the case of a path survives. The runs below put the repository AND TMPDIR on a
# case-sensitive APFS volume, as on the Linux CI runner. Nothing here changes a policy file or the main checkout.
#
# Variables: CS_IMAGE (default ~/.cache/etl-case-sensitive.sparseimage), CS_SIZE (default 24g), CS_VENV
# (default ~/.cache/etl-mutation-venv, the mutation venv: mutmut 3.8.0, pandas 3.1.1, numpy 2.4.6), CS_NAME (etlcs).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
IMAGE="${CS_IMAGE:-$HOME/.cache/etl-case-sensitive.sparseimage}"
SIZE="${CS_SIZE:-24g}"
NAME="${CS_NAME:-etlcs}"
VENV="${CS_VENV:-$HOME/.cache/etl-mutation-venv}"
MOUNT="/Volumes/$NAME"
COPY="$MOUNT/repo"

sync_copy() {
  mkdir -p "$COPY" "$MOUNT/tmp"
  rsync -a --exclude mutants --exclude __pycache__ --exclude .venv --exclude .git "$ROOT"/ "$COPY"/
  rsync -a "$ROOT"/.git/ "$COPY"/.git/
}

case "${1:-}" in
  setup)
    if [ ! -f "$IMAGE" ]; then
      hdiutil create -size "$SIZE" -fs "Case-sensitive APFS" -type SPARSE -volname "$NAME" "${IMAGE%.sparseimage}"
    fi
    [ -d "$MOUNT" ] || hdiutil attach "$IMAGE" >/dev/null
    sync_copy
    echo "case-sensitive copy ready at $COPY (TMPDIR=$MOUNT/tmp)"
    ;;
  sync) sync_copy ;;
  run)
    shift
    cd "$COPY"
    export TMPDIR="$MOUNT/tmp" OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
    mkdir -p "$ROOT/docs/thesis-remediation/evidence/l4-campaign-2026-11-13/survivors"
    rm -f mutants/mutmut-stats.json   # collect the test map once, for the tests as synced
    for unit in "$@"; do
      # mutmut re-runs only mutants without a verdict: re-open every verdict that is not a kill, so the tests
      # as synced decide them again (kills are kept; reset all of them for a complete re-measurement)
      python3 - "$unit" <<'PY'
import json, sys
path = f"mutants/{sys.argv[1]}.meta"
try:
    data = json.load(open(path))
except FileNotFoundError:
    sys.exit()
for key, code in data["exit_code_by_key"].items():
    if code != 1:
        data["exit_code_by_key"][key] = None
json.dump(data, open(path, "w"))
PY
      "$VENV/bin/python" docs/thesis-remediation/evidence/run_l4_campaign.py \
        docs/thesis-remediation/evidence/l4-campaign-2026-11-13/state.json --rerun --only "$unit"
      # the generated copy of the unit is a mutated source only right now
      python3 docs/thesis-remediation/evidence/mutdiff.py mutants "$unit" \
        > "$ROOT/docs/thesis-remediation/evidence/l4-campaign-2026-11-13/survivors/${unit//\//__}.txt"
      mkdir -p "$ROOT/mutants/$(dirname "$unit")"
      cp "mutants/$unit.meta" "$ROOT/mutants/$unit.meta.cs"
    done
    echo "next: merge_case_sensitive.py, consolidate_l4_campaign.py, build_owner_packet.py, build_l4_campaign_report.py, archive_verdicts.py"
    ;;
  teardown) hdiutil detach "$MOUNT" ;;
  *) sed -n '2,12p' "$0"; exit 2 ;;
esac
